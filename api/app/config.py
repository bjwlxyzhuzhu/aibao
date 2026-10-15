"""运行配置：全部来自环境变量（服务器 .env），密钥不进前端、不进代码包。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # api/
ROOT_DIR = BASE_DIR.parent                                  # 项目根
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    for p in (BASE_DIR / ".env", ROOT_DIR / ".env"):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.split("  #")[0].strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(), v)


_load_dotenv()


def env(key: str, default: str = "") -> str:
    v = os.getenv(key, default)
    return default if v.startswith("__") else v


DATABASE_URL = env("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'aibao.db').as_posix()}")
if DATABASE_URL.startswith("postgresql") and "__pwd__" in DATABASE_URL:
    DATABASE_URL = f"sqlite:///{(DATA_DIR / 'aibao.db').as_posix()}"

JWT_SECRET = env("JWT_SECRET") or "dev-only-secret-change-on-server"
LLM_BASE_URL = env("LLM_BASE_URL", "https://tokenone.work/v1").split("#")[0].strip()
LLM_API_KEY = env("LLM_API_KEY")
LLM_MODEL_FAST = env("LLM_MODEL_FAST", "qwen3.8-flash")
LLM_MODEL_STRONG = env("LLM_MODEL_STRONG", "qwen3.8-max")
EMBED_MODEL = env("EMBED_MODEL")
LLM_TIMEOUT = float(env("LLM_TIMEOUT", "45"))  # 单次调用超时，超时自动重试，避免个别慢请求拖住整条链
REVIEW_CONFIDENCE_THRESHOLD = float(env("REVIEW_CONFIDENCE_THRESHOLD", "0.7"))
DEBATE_MAX_ROUNDS = int(env("DEBATE_MAX_ROUNDS", "2"))
FORCE_REVIEW_CATEGORIES = [c for c in env("FORCE_REVIEW_CATEGORIES", "安全,卫生,健康").split(",") if c]
DEMO_MODE = env("DEMO_MODE", "true").lower() == "true"
DEMO_PASSWORD = env("DEMO_PASSWORD", "Aibao@2026")
# 演示用"今天"：比赛演示时固定在 2026-10-15，生产环境留空即用真实日期
DEMO_TODAY = env("DEMO_TODAY", "")

UPLOAD_DIR = DATA_DIR / "uploads"
RAW_DIR = UPLOAD_DIR / "raw"          # 原始件：只在园内
REDACTED_DIR = UPLOAD_DIR / "redacted"  # 脱敏件：可发往模型
for d in (RAW_DIR, REDACTED_DIR):
    d.mkdir(parents=True, exist_ok=True)

ASSETS_DIR = Path(os.getenv("ASSETS_DIR", str(ROOT_DIR / "assets")))
PROMPTS_DIR = BASE_DIR / "prompts"
SEED_DIR = BASE_DIR / "seed_data"
