"""② 家园沟通链：调度官路由 → 爱宝起草（只用公开知识）↔ 红队审查 → 发送 / 改写一次 / 转教师。"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .. import kb
from ..models import ParentMessage, ParentThread
from ..services.workorders import create_work_order, suggest_assignee
from . import offline_rules as R
from .base import ChainContext


class RouteOut(BaseModel):
    route: str
    reason: str = ""


class AnsOut(BaseModel):
    reply: str
    sources: list[int] = Field(default_factory=list)


class _I(BaseModel):
    type: str
    quote: str = ""
    suggestion: str = ""


class RedOut(BaseModel):
    risk_level: str
    issues: list[_I] = Field(default_factory=list)


def run_parent(run_id: int, msg_id: int, test_draft: str | None = None) -> None:
    """test_draft：管理员可注入一条测试用草稿，验证红队能否拦截（验收项）。"""
    ctx = ChainContext(run_id, pace=0.0)
    db = ctx.db
    try:
        q = db.get(ParentMessage, msg_id)
        thread = db.get(ParentThread, q.thread_id)
        question = q.content

        def transfer(reason: str, risk: str | None = None):
            assignee, _ = suggest_assignee(db, thread.class_id, "保教", "教学")
            db.add(ParentMessage(thread_id=thread.id, role="aibao", content="这个问题爱宝已经转给班级老师啦，老师会尽快回复您～",
                                 route="transfer", risk_level=risk, routed_to_staff_id=assignee, run_id=run_id, reply_to_id=q.id))
            q.status, q.route, q.routed_to_staff_id = "pending", "transfer", assignee
            db.flush()
            create_work_order(db, "parent", q.id, f"家长转人工：{question[:30]}", assignee, "中", thread.class_id, q.is_demo)
            ctx.emit("aibao", "route", f"转教师：{reason}", emotion="bye")

        # 1. 调度官判断是否涉及具体孩子
        hard = re.search(R.TRANSFER_RE, question)
        if test_draft:  # 红队验收：直接审查注入的测试草稿，不走路由
            hard = None
            route = {"route": "parent_auto"}
        else:
            route, _ = ctx.call("aibao", "dispatcher", f"家长提问：{question}", RouteOut, "flash",
                                lambda: {"route": "transfer" if hard else "parent_auto", "reason": "涉及具体孩子或个案" if hard else "公开知识可答"})
        if hard or route["route"] == "transfer":
            transfer(route.get("reason") or "涉及具体孩子")
            ctx.finish()
            return
        ctx.emit("aibao", "route", "公开知识类问题，爱宝来起草回复。", emotion="cheer")

        # 2. 爱宝起草：只检索公开知识库
        hits = kb.search(db, question, k=5, visibility="public")
        chunk_txt = "\n".join(f"[{h['id']}] 《{h['doc_title']}》{h['clause_no']}：{h['text']}" for h in hits)
        ctx.think("aibao")
        if test_draft:
            draft = {"reply": test_draft, "sources": []}
        else:
            draft, _ = ctx.call("aibao", "answerer", f"家长问：{question}\n\n公开知识：\n{chunk_txt}", AnsOut, "flash",
                                lambda: R.answer(question, hits))
        ctx.emit("aibao", "statement", draft["reply"], cited=draft.get("sources", []), emotion="cheer")

        # 3. 红队审查，中风险改写一次再审
        final, risk = draft["reply"], "low"
        for attempt in range(2):
            ctx.think("weishi")
            red, _ = ctx.call("weishi", "redteam", f"家长问：{question}\n爱宝草稿：{final}\n依据切片：\n{chunk_txt}", RedOut, "max",
                              lambda: R.redteam(final))
            risk = red["risk_level"] if red["risk_level"] in ("low", "medium", "high") else "high"
            issues = "；".join(f"{i['type']}：{i.get('quote', '')}" for i in red["issues"]) or "未发现风险"
            emo = {"low": "support", "medium": "surprised", "high": "angry"}[risk]
            ctx.emit("weishi", "redteam", f"风险{ {'low': '低', 'medium': '中', 'high': '高'}[risk] }：{issues}", target="aibao",
                     emotion=emo, content=red)
            if risk == "medium" and attempt == 0:
                fb = "；".join(f"{i['type']}：{i.get('quote', '')} → {i.get('suggestion', '')}" for i in red["issues"])
                rw, _ = ctx.call("aibao", "answerer", f"家长问：{question}\n\n公开知识：\n{chunk_txt}\n\n你上一版回复：{final}\n"
                                 f"风险审查意见：{fb}\n请按审查意见改写，只说切片里有依据的内容。", AnsOut, "flash",
                                 lambda: {"reply": R.rewrite(final, red["issues"]), "sources": draft.get("sources", [])})
                final = rw["reply"]
                ctx.emit("aibao", "statement", f"按审查意见改写：{final}", round=2, emotion="please")
                continue
            break
        if risk == "low":
            db.add(ParentMessage(thread_id=thread.id, role="aibao", content=final, risk_level=risk, route="auto",
                                 sources=[{"id": h["id"], "title": h["doc_title"], "clause": h["clause_no"]}
                                          for h in hits if h["id"] in (draft.get("sources") or [h["id"] for h in hits[:1]])],
                                 run_id=run_id, reply_to_id=q.id, is_demo=q.is_demo))
            q.route = "auto"
            ctx.emit("aibao", "state", "审查通过，已发送给家长。", emotion="happy")
        else:
            q.route = "blocked"
            transfer("红队判定风险过高，已拦截草稿", risk)
        ctx.finish()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        ctx.db.rollback()
        ctx.emit("aibao", "state", f"出错了，已转人工：{e}", emotion="sad")
        ctx.finish("failed")
    finally:
        ctx.db.commit()
        ctx.close()
