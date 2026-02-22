#!/usr/bin/env python3
"""Rotate critical P0 secrets in .env.

This script updates these keys:
- AUTH_SECRET
- ACP_SECRET
- TELEGRAM_WEBHOOK_SECRET
- AUTH_TRANSITION_MODE=false
- AUTH_ALLOW_HEADER_FALLBACK=false
"""

from __future__ import annotations

import secrets
from pathlib import Path


TARGET_KEYS = {
    "AUTH_SECRET": lambda: secrets.token_urlsafe(48),
    "ACP_SECRET": lambda: secrets.token_urlsafe(32),
    "TELEGRAM_WEBHOOK_SECRET": lambda: secrets.token_urlsafe(32),
    "AUTH_TRANSITION_MODE": lambda: "false",
    "AUTH_ALLOW_HEADER_FALLBACK": lambda: "false",
}


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    return path.read_text(encoding="utf-8").splitlines()


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_env(lines: list[str]) -> tuple[list[str], dict[str, str]]:
    generated = {key: gen() for key, gen in TARGET_KEYS.items()}
    pending = set(generated.keys())
    updated: list[str] = []

    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            updated.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in generated:
            updated.append(f"{key}={generated[key]}")
            pending.discard(key)
        else:
            updated.append(line)

    for key in sorted(pending):
        updated.append(f"{key}={generated[key]}")

    return updated, generated


def fingerprint(value: str) -> str:
    if len(value) < 12:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def main() -> None:
    env_path = Path(".env")
    lines = load_lines(env_path)
    updated_lines, generated = update_env(lines)
    write_lines(env_path, updated_lines)

    print("rotation_status=ok")
    for key, value in generated.items():
        print(f"{key}={fingerprint(value)}")


if __name__ == "__main__":
    main()
