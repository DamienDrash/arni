"""
Docker Container Management Router
===================================
Provides a secure REST API for managing Docker containers from the
ARIIA System-Admin web interface.  Only accessible by system_admin users.

Requires the Docker socket to be mounted read-only into the container:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import AuthContext, get_current_user

logger = structlog.get_logger()

router = APIRouter(
    prefix="/admin/docker",
    tags=["docker-management"],
    dependencies=[Depends(get_current_user)],
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _require_system_admin(user: AuthContext) -> None:
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")


def _get_docker_client():
    """Lazy-import docker and return a client connected to the local socket."""
    try:
        import docker
        return docker.from_env()
    except Exception as exc:
        logger.error("docker_client_init_failed", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail=f"Docker daemon not available: {exc}",
        )


def _parse_uptime(started_at: str | None) -> str:
    """Convert ISO started_at to a human-readable uptime string."""
    if not started_at:
        return "–"
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - start
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, _ = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)
    except Exception:
        return started_at


def _container_to_dict(c) -> dict[str, Any]:
    """Normalise a docker container object into a JSON-friendly dict."""
    attrs = c.attrs or {}
    state = attrs.get("State", {})
    config = attrs.get("Config", {})
    host_config = attrs.get("HostConfig", {})
    network_settings = attrs.get("NetworkSettings", {})

    # Port mappings
    ports_raw = network_settings.get("Ports") or {}
    port_list = []
    for container_port, bindings in ports_raw.items():
        if bindings:
            for b in bindings:
                host_port = b.get("HostPort", "")
                host_ip = b.get("HostIp", "0.0.0.0")
                port_list.append(f"{host_ip}:{host_port}->{container_port}")
        else:
            port_list.append(container_port)

    # Health
    health = state.get("Health", {})
    health_status = health.get("Status", "none")

    # Memory limit
    mem_limit = host_config.get("Memory", 0)

    return {
        "id": c.short_id,
        "full_id": c.id,
        "name": c.name,
        "image": (config.get("Image") or c.image.tags[0] if c.image.tags else c.image.short_id),
        "status": c.status,
        "state": state.get("Status", c.status),
        "started_at": state.get("StartedAt"),
        "uptime": _parse_uptime(state.get("StartedAt") if c.status == "running" else None),
        "health": health_status,
        "ports": port_list,
        "restart_policy": host_config.get("RestartPolicy", {}).get("Name", "no"),
        "memory_limit": mem_limit,
        "labels": dict(c.labels) if c.labels else {},
        "created": attrs.get("Created", ""),
    }


# ── Schemas ──────────────────────────────────────────────────────────────

class ContainerAction(BaseModel):
    timeout: int = 10


class ContainerStatsResponse(BaseModel):
    cpu_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    network_rx_mb: float
    network_tx_mb: float
    pids: int


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/containers")
async def list_containers(
    all: bool = Query(False, description="Include stopped containers"),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return a list of all Docker containers with status, ports, health, etc."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        containers = client.containers.list(all=all)
        result = [_container_to_dict(c) for c in containers]
        # Sort: running first, then by name
        result.sort(key=lambda x: (0 if x["status"] == "running" else 1, x["name"]))
        return {
            "containers": result,
            "total": len(result),
            "running": sum(1 for c in result if c["status"] == "running"),
            "stopped": sum(1 for c in result if c["status"] != "running"),
        }
    finally:
        client.close()


@router.get("/containers/{container_id}/stats")
async def get_container_stats(
    container_id: str,
    user: AuthContext = Depends(get_current_user),
) -> ContainerStatsResponse:
    """Return current CPU, memory, and network stats for a single container."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        container = client.containers.get(container_id)
        if container.status != "running":
            raise HTTPException(status_code=400, detail="Container is not running")

        # stream=False returns a single snapshot
        stats = container.stats(stream=False)

        # CPU calculation
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"].get("system_cpu_usage", 0)
            - stats["precpu_stats"].get("system_cpu_usage", 0)
        )
        online_cpus = stats["cpu_stats"].get("online_cpus", 1)
        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = round((cpu_delta / system_delta) * online_cpus * 100.0, 2)

        # Memory calculation
        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_cache = stats["memory_stats"].get("stats", {}).get("cache", 0)
        mem_actual = mem_usage - mem_cache
        mem_limit = stats["memory_stats"].get("limit", 1)
        mem_percent = round((mem_actual / mem_limit) * 100.0, 2) if mem_limit > 0 else 0.0

        # Network calculation
        networks = stats.get("networks", {})
        rx_bytes = sum(n.get("rx_bytes", 0) for n in networks.values())
        tx_bytes = sum(n.get("tx_bytes", 0) for n in networks.values())

        # PIDs
        pids = stats.get("pids_stats", {}).get("current", 0)

        return ContainerStatsResponse(
            cpu_percent=cpu_percent,
            memory_usage_mb=round(mem_actual / (1024 * 1024), 2),
            memory_limit_mb=round(mem_limit / (1024 * 1024), 2),
            memory_percent=mem_percent,
            network_rx_mb=round(rx_bytes / (1024 * 1024), 2),
            network_tx_mb=round(tx_bytes / (1024 * 1024), 2),
            pids=pids,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("container_stats_failed", container=container_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        client.close()


@router.get("/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    tail: int = Query(200, ge=1, le=5000, description="Number of log lines"),
    since: Optional[int] = Query(None, description="Unix timestamp to start from"),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the last N log lines of a container."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        container = client.containers.get(container_id)
        kwargs: dict[str, Any] = {
            "stdout": True,
            "stderr": True,
            "tail": tail,
            "timestamps": True,
        }
        if since is not None:
            kwargs["since"] = since

        logs = container.logs(**kwargs)
        if isinstance(logs, bytes):
            log_text = logs.decode("utf-8", errors="replace")
        else:
            log_text = str(logs)

        lines = log_text.strip().split("\n") if log_text.strip() else []
        return {
            "container": container.name,
            "lines": lines,
            "total_lines": len(lines),
        }
    except Exception as exc:
        logger.error("container_logs_failed", container=container_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        client.close()


@router.post("/containers/{container_id}/start")
async def start_container(
    container_id: str,
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Start a stopped container."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        container = client.containers.get(container_id)
        if container.status == "running":
            return {"status": "already_running", "container": container.name}
        container.start()
        logger.info("container_started", container=container.name, by=user.email)
        return {"status": "started", "container": container.name}
    except Exception as exc:
        logger.error("container_start_failed", container=container_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        client.close()


@router.post("/containers/{container_id}/stop")
async def stop_container(
    container_id: str,
    body: ContainerAction = ContainerAction(),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Stop a running container with a configurable timeout."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        container = client.containers.get(container_id)
        if container.status != "running":
            return {"status": "already_stopped", "container": container.name}

        # Safety: prevent stopping the core container from within itself
        import socket
        hostname = socket.gethostname()
        if container.id.startswith(hostname) or container.name == "ariia_core":
            raise HTTPException(
                status_code=400,
                detail="Cannot stop the core API container from within itself",
            )

        container.stop(timeout=body.timeout)
        logger.info("container_stopped", container=container.name, by=user.email)
        return {"status": "stopped", "container": container.name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("container_stop_failed", container=container_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        client.close()


@router.post("/containers/{container_id}/restart")
async def restart_container(
    container_id: str,
    body: ContainerAction = ContainerAction(),
    user: AuthContext = Depends(get_current_user),
) -> dict[str, str]:
    """Restart a container with a configurable timeout."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        container = client.containers.get(container_id)

        # Safety: prevent restarting the core container from within
        import socket
        hostname = socket.gethostname()
        if container.id.startswith(hostname) or container.name == "ariia_core":
            raise HTTPException(
                status_code=400,
                detail="Cannot restart the core API container from within itself. Use docker compose restart ariia-core from the host.",
            )

        container.restart(timeout=body.timeout)
        logger.info("container_restarted", container=container.name, by=user.email)
        return {"status": "restarted", "container": container.name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("container_restart_failed", container=container_id, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        client.close()


@router.get("/system-info")
async def get_system_info(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return Docker host system information (version, OS, resources)."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        info = client.info()
        version = client.version()
        return {
            "docker_version": version.get("Version", "unknown"),
            "api_version": version.get("ApiVersion", "unknown"),
            "os": info.get("OperatingSystem", "unknown"),
            "kernel": info.get("KernelVersion", "unknown"),
            "architecture": info.get("Architecture", "unknown"),
            "cpus": info.get("NCPU", 0),
            "memory_total_gb": round(info.get("MemTotal", 0) / (1024 ** 3), 2),
            "containers_total": info.get("Containers", 0),
            "containers_running": info.get("ContainersRunning", 0),
            "containers_stopped": info.get("ContainersStopped", 0),
            "containers_paused": info.get("ContainersPaused", 0),
            "images": info.get("Images", 0),
            "storage_driver": info.get("Driver", "unknown"),
            "server_time": info.get("SystemTime", ""),
        }
    finally:
        client.close()


@router.get("/images")
async def list_images(
    user: AuthContext = Depends(get_current_user),
) -> dict[str, Any]:
    """Return a list of Docker images on the host."""
    _require_system_admin(user)
    client = _get_docker_client()
    try:
        images = client.images.list()
        result = []
        for img in images:
            tags = img.tags or ["<none>:<none>"]
            size_mb = round((img.attrs.get("Size", 0)) / (1024 * 1024), 1)
            result.append({
                "id": img.short_id.replace("sha256:", ""),
                "tags": tags,
                "size_mb": size_mb,
                "created": img.attrs.get("Created", ""),
            })
        result.sort(key=lambda x: x["tags"][0])
        return {"images": result, "total": len(result)}
    finally:
        client.close()
