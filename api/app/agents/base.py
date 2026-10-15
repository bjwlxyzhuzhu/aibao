"""智能体基类：提示词版本、JSON 结构校验、重试、写 agent_messages（驱动 SSE 与 3D 回放）。"""
from __future__ import annotations

import re
import threading
import time
import traceback
from typing import Callable

from pydantic import BaseModel, ValidationError

from ..config import PROMPTS_DIR
from ..db import SessionLocal
from ..gateway import GatewayError, pass_through_gateway
from ..llm.client import LLMUnavailable, chat_json, llm_enabled
from ..models import AgentMessage, AgentRun
from ..timeutil import now_local

# 智能体名册（与 assets/avatars 目录一致）
AGENTS = {
    "aibao": {"name": "爱宝", "role": "调度官 / 答疑员 / 综合员", "color": "#E2603A"},
    "xingbao": {"name": "星宝", "role": "巡查诊断员", "color": "#2F7BE0"},
    "humiao": {"name": "护苗", "role": "一线质询员 · 小熊", "color": "#B7773D"},
    "mingli": {"name": "明理", "role": "条款裁判员 · 猫头鹰", "color": "#7A5C3E"},
    "xiaobu": {"name": "小步", "role": "整改跟踪员 · 小乌龟", "color": "#3E9B5B"},
    "weishi": {"name": "小卫士", "role": "风险审查员 · 柴犬", "color": "#D98B2B"},
    "xiaoyi": {"name": "小医", "role": "保健视角 · 小白兔", "color": "#E68AA6"},
    "xiaoshi": {"name": "小师", "role": "教师视角 · 小熊猫", "color": "#C2562F"},
    "xiaojia": {"name": "小家", "role": "家长视角 · 小袋鼠", "color": "#C99A5B"},
    "xiaodun": {"name": "小盾", "role": "安全视角 · 小象", "color": "#5D7EA8"},
}


def load_prompt(name: str) -> tuple[str, str]:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    m = re.search(r"version:\s*([\d.]+)", text)
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    return body, (m.group(1) if m else "0")


# 生成演示数据时强制离线，避免消耗模型额度；演示数据不作为参赛证据
FORCE_OFFLINE = False


class ChainContext:
    """一次链路运行的上下文：自带数据库会话，在后台线程里执行。"""

    def __init__(self, run_id: int, pace: float = 0.0):
        self.db = SessionLocal()
        self.run = self.db.get(AgentRun, run_id)
        self.pace = pace  # 离线引擎下给 3D 演示留出节奏
        self.online = llm_enabled(self.db) and not FORCE_OFFLINE

    def emit(self, agent: str, action: str, text: str, *, round: int = 1, target: str | None = None,
             finding_key: str | None = None, cited: list[int] | None = None, confidence: float | None = None,
             emotion: str = "cheer", content: dict | None = None) -> AgentMessage:
        m = AgentMessage(run_id=self.run.id, round=round, agent=agent, action=action, target_agent=target,
                         finding_key=finding_key, text=text, cited_chunk_ids=cited or [], confidence=confidence,
                         emotion=emotion, content_json=content or {})
        self.db.add(m)
        self.db.commit()
        if self.pace:
            time.sleep(self.pace)
        return m

    def think(self, agent: str, round: int = 1):
        self.emit(agent, "think", "思考中…", round=round, emotion="doubt")

    def call(self, agent_key: str, prompt_name: str, user_text: str, schema: type[BaseModel] | None,
             tier: str, offline: Callable[[], dict], images: list[str] | None = None) -> tuple[dict, str]:
        """先走网关再调模型；未配置模型或连续失败时使用离线规则引擎（结果标注 engine=offline）。"""
        if self.online:
            system, ver = load_prompt(prompt_name)
            try:
                payload = pass_through_gateway(self.db, user_text, images, agent=agent_key)
                for _ in range(2):
                    out = chat_json(self.db, agent=agent_key, system=system, payload=payload, tier=tier, run_id=self.run.id)
                    if schema is None:
                        return out, f"llm:{ver}"
                    try:
                        return schema.model_validate(out).model_dump(), f"llm:{ver}"
                    except ValidationError:
                        continue
            except GatewayError:
                raise
            except LLMUnavailable:
                pass
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        else:
            # 离线也记录一次网关处理，保证"所有模型输入都经过脱敏"可审计
            pass_through_gateway(self.db, user_text, images, agent=agent_key)
        return offline(), "offline"

    def finish(self, status: str = "done"):
        self.run.status = status
        self.run.finished_at = now_local()
        self.db.commit()

    def close(self):
        self.db.close()


def run_in_background(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()
