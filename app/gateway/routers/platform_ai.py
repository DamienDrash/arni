import httpx
import structlog
import time
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from app.core.auth import AuthContext, get_current_user
from app.gateway.persistence import persistence
from typing import List, Optional, Any

logger = structlog.get_logger()
router = APIRouter(prefix="/admin/platform/llm", tags=["platform-ai"])

SUPPORTED_PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1", "type": "openai"},
    {"id": "mistral", "name": "Mistral AI", "base_url": "https://api.mistral.ai/v1", "type": "openai"},
    {"id": "groq", "name": "Groq", "base_url": "https://api.groq.com/openai/v1", "type": "openai"},
    {"id": "anthropic", "name": "Anthropic", "base_url": "https://api.anthropic.com/v1", "type": "anthropic"},
    {"id": "gemini", "name": "Google Gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta", "type": "gemini"},
]

class FetchModelsRequest(BaseModel):
    provider_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None

class FetchModelsStoredRequest(BaseModel):
    provider_id: str

class TestConnectionRequest(BaseModel):
    provider_id: str
    api_key: str
    model: str
    base_url: Optional[str] = None

@router.get("/providers/available")
async def list_available_providers(user: AuthContext = Depends(get_current_user)):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return SUPPORTED_PROVIDERS

@router.post("/fetch-models")
async def fetch_provider_models(
    req: FetchModelsRequest,
    user: AuthContext = Depends(get_current_user)
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return await _fetch_models_internal(req.provider_id, req.api_key, req.base_url)

@router.post("/fetch-models-stored")
async def fetch_provider_models_stored(
    req: FetchModelsStoredRequest,
    user: AuthContext = Depends(get_current_user)
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    stored_key = persistence.get_setting(f"platform_llm_key_{req.provider_id}", "", tenant_id=1)
    if not stored_key or stored_key == "__REDACTED__":
        raise HTTPException(status_code=404, detail="Kein gespeicherter API-Key gefunden.")
        
    return await _fetch_models_internal(req.provider_id, stored_key, None)

async def _fetch_models_internal(provider_id: str, api_key: str, base_url: Optional[str]):
    provider = next((p for p in SUPPORTED_PROVIDERS if p["id"] == provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider nicht unterstützt.")

    url = base_url or provider["base_url"]
    ptype = provider["type"]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if ptype == "openai":
                resp = await client.get(f"{url.rstrip('/')}/models", headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code != 200:
                    detail = _extract_error(resp)
                    raise HTTPException(status_code=400, detail=f"Provider API Fehler: {detail}")
                data = resp.json()
                models = [m["id"] for m in data.get("data", [])]
                return sorted(models)
            elif ptype == "gemini":
                resp = await client.get(f"{url.rstrip('/')}/models?key={api_key}")
                if resp.status_code != 200:
                    detail = _extract_error(resp)
                    raise HTTPException(status_code=400, detail=f"Gemini API Fehler: {detail}")
                data = resp.json()
                models = [m["name"].split("/")[-1] for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
                return sorted(models)
            elif ptype == "anthropic":
                return ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest"]
            return []
    except HTTPException:
        raise
    except Exception as e:
        logger.error("platform_ai.fetch_models_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

def _extract_error(resp):
    try:
        err_data = resp.json()
        if isinstance(err_data, dict):
            return err_data.get("error", {}).get("message", resp.text[:200])
        return resp.text[:200]
    except:
        return resp.text[:200]

@router.post("/test-connection")
async def test_ai_connection(
    req: TestConnectionRequest,
    user: AuthContext = Depends(get_current_user)
):
    if user.role != "system_admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    effective_key = req.api_key
    if req.api_key == "__REDACTED__":
        effective_key = persistence.get_setting(f"platform_llm_key_{req.provider_id}", "", tenant_id=1)

    provider = next((p for p in SUPPORTED_PROVIDERS if p["id"] == req.provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider nicht unterstützt.")

    url = req.base_url or provider["base_url"]
    ptype = provider["type"]
    
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if ptype in ("openai", "anthropic"):
                resp = await client.post(
                    f"{url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {effective_key}", "Content-Type": "application/json"},
                    json={"model": req.model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}
                )
            elif ptype == "gemini":
                resp = await client.post(
                    f"{url.rstrip('/')}/models/{req.model}:generateContent?key={effective_key}",
                    json={"contents": [{"parts": [{"text": "ping"}]}]}
                )
            else:
                return {"status": "error", "detail": "Test-Typ nicht unterstützt."}

            latency = int((time.perf_counter() - start) * 1000)
            if resp.status_code == 200:
                return {"status": "ok", "latency_ms": latency}
            else:
                return {"status": "error", "code": resp.status_code, "detail": _extract_error(resp)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
