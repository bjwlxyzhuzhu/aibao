"""家园沟通（家长端、教师转人工队列）与园务议事接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.base import run_in_background
from ..agents.council_chain import run_council
from ..agents.parent_chain import run_parent
from ..db import get_db
from ..models import AgentRun, CouncilTopic, Klass, ParentMessage, ParentThread
from ..security import Principal, current, require
from ..services.workorders import close_work_orders, staff_name
from ..timeutil import now_local

router = APIRouter()


class ChatIn(BaseModel):
    content: str
    test_draft: str | None = None  # 仅管理员 / 园长验收红队用


def _thread(db: Session, p: Principal) -> ParentThread:
    t = db.scalar(select(ParentThread).where(ParentThread.user_id == p.user.id))
    if not t:
        t = ParentThread(user_id=p.user.id, class_id=p.user.parent_class_id)
        db.add(t)
        db.flush()
    return t


def _pm_out(m: ParentMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "risk_level": m.risk_level, "route": m.route, "sources": m.sources,
            "run_id": m.run_id, "status": m.status, "reply_to_id": m.reply_to_id, "created_at": m.created_at.isoformat()}


@router.post("/parent/chat")
def parent_chat(body: ChatIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.role not in ("parent", "principal", "admin"):
        raise HTTPException(403)
    if not body.content.strip():
        raise HTTPException(400, "请输入问题")
    t = _thread(db, p)
    if t.class_id is None and p.role != "parent":
        t.class_id = db.scalar(select(Klass.id).order_by(Klass.order).limit(1))
    m = ParentMessage(thread_id=t.id, role="parent", content=body.content.strip()[:500])
    db.add(m)
    db.flush()
    run = AgentRun(chain="parent", source_id=m.id)
    db.add(run)
    db.flush()
    m.run_id = run.id
    db.commit()
    draft = body.test_draft if p.role in ("principal", "admin") else None
    run_in_background(lambda: run_parent(run.id, m.id, draft))
    return {"message_id": m.id, "run_id": run.id}


@router.get("/parent/thread")
def parent_thread(p: Principal = Depends(current), db: Session = Depends(get_db)):
    t = _thread(db, p)
    db.commit()
    msgs = list(db.scalars(select(ParentMessage).where(ParentMessage.thread_id == t.id).order_by(ParentMessage.id)))
    k = db.get(Klass, t.class_id) if t.class_id else None
    return {"class_name": k.name if k else None, "messages": [_pm_out(m) for m in msgs]}


@router.get("/staff/parent-queue")
def parent_queue(p: Principal = Depends(current), db: Session = Depends(get_db)):
    out = []
    for m in db.scalars(select(ParentMessage).where(ParentMessage.role == "parent", ParentMessage.route.in_(["transfer", "blocked"]))
                        .order_by(ParentMessage.id.desc())):
        t = db.get(ParentThread, m.thread_id)
        if p.role not in ("principal", "admin") and not p.can_see_class(t.class_id) and not (p.staff and m.routed_to_staff_id == p.staff.id):
            continue
        k = db.get(Klass, t.class_id) if t.class_id else None
        reply = db.scalar(select(ParentMessage).where(ParentMessage.reply_to_id == m.id, ParentMessage.role == "teacher"))
        out.append({**_pm_out(m), "class_name": k.name if k else "", "assignee": staff_name(db, m.routed_to_staff_id),
                    "reply": reply.content if reply else None})
    return out


class ReplyIn(BaseModel):
    message_id: int
    content: str


@router.post("/staff/parent-queue")
def parent_reply(body: ReplyIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    m = db.get(ParentMessage, body.message_id)
    if not m or p.role == "parent":
        raise HTTPException(404)
    db.add(ParentMessage(thread_id=m.thread_id, role="teacher", content=body.content, reply_to_id=m.id, route="manual"))
    m.status = "done"
    close_work_orders(db, "parent", m.id)
    db.commit()
    return {"ok": True}


# ---------- 园务议事 ----------
class TopicIn(BaseModel):
    title: str
    detail: str = ""


def _topic_out(t: CouncilTopic) -> dict:
    return {"id": t.id, "title": t.title, "detail": t.detail, "run_id": t.run_id, "brief": t.brief_json, "status": t.status,
            "final_decision": t.final_decision, "decided_at": t.decided_at.isoformat() if t.decided_at else None,
            "created_at": t.created_at.isoformat()}


@router.post("/council/topics")
def new_topic(body: TopicIn, p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    t = CouncilTopic(title=body.title.strip()[:250], detail=body.detail, created_by=p.user.id)
    db.add(t)
    db.flush()
    run = AgentRun(chain="council", source_id=t.id)
    db.add(run)
    db.flush()
    t.run_id = run.id
    db.commit()
    run_in_background(lambda: run_council(run.id, t.id))
    return _topic_out(t)


@router.get("/council/topics")
def topics(p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    return [_topic_out(t) for t in db.scalars(select(CouncilTopic).order_by(CouncilTopic.id.desc()))]


@router.get("/council/topics/{tid}")
def topic(tid: int, p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    t = db.get(CouncilTopic, tid)
    if not t:
        raise HTTPException(404)
    return _topic_out(t)


class DecisionIn(BaseModel):
    decision: str


@router.post("/council/topics/{tid}/decision")
def decide(tid: int, body: DecisionIn, p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    if "园长" not in p.positions and p.staff:
        raise HTTPException(403, "最终决定由园长记录")
    t = db.get(CouncilTopic, tid)
    t.final_decision, t.decided_at, t.status = body.decision, now_local(), "decided"
    db.commit()
    return _topic_out(t)
