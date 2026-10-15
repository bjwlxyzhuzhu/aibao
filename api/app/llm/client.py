"""OpenAI 兼容客户端（tokenone.work / 阿里云百炼）。只接受网关产出的 RedactedPayload。"""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

import httpx

from .. import config
from ..gateway import RedactedPayload


class LLMUnavailable(RuntimeError):
    pass


def llm_enabled(db=None) -> bool:
    return bool(get_runtime(db)["api_key"])


def get_runtime(db=None) -> dict:
    base = config.LLM_BASE_URL
    if db is not None:
        from ..models import Setting
        s = db.get(Setting, "llm_base_url")
        if s and isinstance(s.value, str) and s.value:
            base = s.value
    return {"base_url": base.rstrip("/"), "api_key": config.LLM_API_KEY}


def model_for(db, agent: str, default_tier: str) -> str:
    tier = default_tier
    if db is not None:
        from ..models import Setting
        s = db.get(Setting, "agent_models")
        if s and isinstance(s.value, dict) and s.value.get(agent):
            tier = s.value[agent]
    return config.LLM_MODEL_STRONG if tier == "max" else config.LLM_MODEL_FAST


def thinking_for(db, agent: str) -> bool:
    """深度思考默认关闭（关闭后单次调用约快 3 倍，满足 60 秒出结论）；管理员可按智能体开启。"""
    if db is not None:
        from ..models import Setting
        s = db.get(Setting, "agent_thinking")
        if s and isinstance(s.value, dict):
            return bool(s.value.get(agent, False))
    return False


def _img_part(path: str) -> dict:
    b = Path(path).read_bytes()
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}}


def _extract_json(s: str) -> dict:
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def chat_json(db, *, agent: str, system: str, payload: RedactedPayload, tier: str = "flash",
              run_id: int | None = None, retries: int = 2, temperature: float = 0.3) -> dict:
    if not isinstance(payload, RedactedPayload):
        raise TypeError("所有云端调用必须先经过脱敏网关")
    rt = get_runtime(db)
    if not rt["api_key"]:
        raise LLMUnavailable("未配置 LLM_API_KEY")
    model = model_for(db, agent, tier)
    content: list | str = payload.text
    if payload.image_paths:
        content = [{"type": "text", "text": payload.text}] + [_img_part(p) for p in payload.image_paths]
    body = {"model": model, "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "response_format": {"type": "json_object"}, "enable_thinking": thinking_for(db, agent)}
    from ..models import ModelCall
    last_err = ""
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            with httpx.Client(timeout=httpx.Timeout(config.LLM_TIMEOUT, connect=10)) as c:
                r = c.post(f"{rt['base_url']}/chat/completions", json=body,
                           headers={"Authorization": f"Bearer {rt['api_key']}"})
            if r.status_code == 400 and "response_format" in r.text and attempt == 0:
                body.pop("response_format", None)
                continue
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            out = _extract_json(text)
            u = data.get("usage") or {}
            db.add(ModelCall(run_id=run_id, agent=agent, model=model, tokens_in=u.get("prompt_tokens", 0),
                             tokens_out=u.get("completion_tokens", 0), latency_ms=int((time.time() - t0) * 1000), ok=True))
            db.flush()
            return out
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:500]
            db.add(ModelCall(run_id=run_id, agent=agent, model=model, latency_ms=int((time.time() - t0) * 1000),
                             ok=False, error=last_err))
            db.flush()
    raise LLMUnavailable(last_err)


def embed(texts: list[str]) -> list[list[float]] | None:
    if not (config.LLM_API_KEY and config.EMBED_MODEL):
        return None
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(f"{config.LLM_BASE_URL.rstrip('/')}/embeddings", json={"model": config.EMBED_MODEL, "input": texts},
                       headers={"Authorization": f"Bearer {config.LLM_API_KEY}"})
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]
    except Exception:  # noqa: BLE001
        return None
