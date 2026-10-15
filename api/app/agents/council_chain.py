"""③ 园务议事链：四视角陈述 → 交叉质询（每方至少质疑一方）→ 爱宝综合简报（保留分歧，不替园长下结论）。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import kb
from ..models import CouncilTopic
from . import offline_rules as R
from .base import ChainContext

VIEW_AGENT = {"health": "xiaoyi", "teacher": "xiaoshi", "parent": "xiaojia", "safety": "xiaodun"}
VIEW_CN = {"health": "保健", "teacher": "教师", "parent": "家长", "safety": "安全"}


class ViewOut(BaseModel):
    round: int = 1
    position: str = ""
    evidence: list[str] = Field(default_factory=list)
    challenge_to: str | None = None
    challenge: str = ""


class _D(BaseModel):
    between: list[str]
    point: str


class _O(BaseModel):
    name: str
    pros: str = ""
    cons: str = ""


class BriefOut(BaseModel):
    consensus: list[str]
    disagreements: list[_D]
    risks: list[str] = Field(default_factory=list)
    options: list[_O] = Field(default_factory=list)


def run_council(run_id: int, topic_id: int, pace: float | None = None) -> None:
    ctx = ChainContext(run_id)
    db = ctx.db
    try:
        topic = db.get(CouncilTopic, topic_id)
        ctx.pace = pace if pace is not None else (0.0 if ctx.online else 1.0)
        t = f"{topic.title}\n{topic.detail or ''}".strip()
        ctx.emit("aibao", "route", f"今天的议题：「{topic.title}」。请保健、教师、家长、安全四位依次陈述。", emotion="cheer")
        statements: dict[str, dict] = {}
        for view, agent in VIEW_AGENT.items():
            hits = kb.search(db, f"{VIEW_CN[view]} {t}", k=3)
            ctx.think(agent)
            ref = "\n".join(f"[{h['id']}]《{h['doc_title']}》{h['clause_no']}：{h['text'][:160]}" for h in hits)
            out, _ = ctx.call(agent, f"council_{view}", f"第一轮陈述。议题：{t}\n可参考条款：\n{ref}", ViewOut, "flash",
                              lambda: R.council_statement(view, topic.title, hits))
            statements[view] = out
            ctx.emit(agent, "statement", out["position"], cited=[h["id"] for h in hits[:1]], emotion="cheer",
                     content={**out, "view": view})
        others = "\n".join(f"{VIEW_CN[v]}（{v}）：{s['position']}" for v, s in statements.items())
        challenges = {}
        for view, agent in VIEW_AGENT.items():
            ctx.think(agent, round=2)
            out, _ = ctx.call(agent, f"council_{view}", f"第二轮交叉质询。议题：{t}\n各方第一轮立场：\n{others}\n请至少质疑一个其他视角。",
                              ViewOut, "flash", lambda: R.council_challenge(view, topic.title))
            tgt = out.get("challenge_to") if out.get("challenge_to") in VIEW_AGENT and out.get("challenge_to") != view else R.CHALLENGE_PLAN[view]
            challenges[view] = out
            ctx.emit(agent, "challenge", out.get("challenge") or out.get("position", ""), round=2, target=VIEW_AGENT[tgt],
                     emotion="surprised", content={**out, "view": view, "challenge_to": tgt})
        ctx.think("aibao", round=3)
        allc = "\n".join(f"{VIEW_CN[v]} 质疑 {VIEW_CN.get(c.get('challenge_to') or '', '')}：{c.get('challenge', '')}" for v, c in challenges.items())
        brief, eng = ctx.call("aibao", "synthesizer", f"议题：{t}\n\n第一轮：\n{others}\n\n第二轮：\n{allc}", BriefOut, "max",
                              lambda: R.council_brief(topic.title))
        ctx.run.engine = "llm" if eng.startswith("llm") else "offline"
        topic.brief_json = brief
        topic.status = "briefed"
        ctx.emit("aibao", "brief", "决策简报已生成：共识 {} 条，保留分歧 {} 处，备选方案 {} 个。最终决定请园长记录。".format(
            len(brief["consensus"]), len(brief["disagreements"]), len(brief["options"])), round=3, emotion="happy", content=brief)
        ctx.finish()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        ctx.db.rollback()
        ctx.emit("aibao", "state", f"议事出错：{e}", emotion="sad")
        ctx.finish("failed")
    finally:
        ctx.close()
