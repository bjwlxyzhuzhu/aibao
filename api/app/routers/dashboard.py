"""园长驾驶舱、周报、对话助手、提醒、校历与品牌等公共接口。"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, kb
from ..agents.base import AGENTS, ChainContext
from ..db import get_db
from ..llm.client import llm_enabled
from ..models import (AgentRun, Avatar, BrandAsset, ClassStaff, Finding, Inspection, Klass, Notification, ParentMessage,
                      Rectification, Reminder, Review, Routine, Staff, WorkOrder)
from ..security import Principal, current, require
from ..services.calendar import SEGMENTS, calendar_today, current_semester, current_semester_id
from ..services.workorders import staff_name
from ..timeutil import now_local, today

router = APIRouter()


def _range_start(rng: str, db: Session) -> datetime:
    t = today()
    if rng == "today":
        return datetime.combine(t, datetime.min.time())
    if rng == "week":
        return datetime.combine(t - timedelta(days=t.weekday()), datetime.min.time())
    s = current_semester(db)
    return datetime.combine(s.start_date if s else t - timedelta(days=120), datetime.min.time())


@router.get("/dashboard")
def dashboard(range: str = "week", source: str = "auto", p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    start = _range_start(range, db)
    all_insp = list(db.scalars(select(Inspection).where(Inspection.created_at >= start)))
    has_real = any(not i.is_demo for i in db.scalars(select(Inspection)))
    use_demo = source == "demo" or (source == "auto" and not has_real)
    insp = [i for i in all_insp if (i.is_demo if use_demo else not i.is_demo)]
    ids = {i.id for i in insp}
    fs = [f for f in db.scalars(select(Finding)) if f.inspection_id in ids and p.category_ok(f.category)]
    classes = [k for k in db.scalars(select(Klass).where(Klass.active.is_(True)).order_by(Klass.order))]
    heat = {seg: {k.name: 0 for k in classes} for seg in SEGMENTS}
    for f in fs:
        if f.final_verdict == "invalid" and not f.needs_review:
            continue
        cname = f.inspection.klass.name
        if f.segment in heat and cname in heat[f.segment]:
            heat[f.segment][cname] += 1
    t0 = datetime.combine(today(), datetime.min.time())
    today_insp = [i for i in insp if i.created_at >= t0]
    rects = [r for r in db.scalars(select(Rectification)) if r.is_demo == use_demo]
    issued = [r for r in rects if r.status != "draft"]
    closed = [r for r in issued if r.status == "closed"]
    # 待复核
    reviewed_ids = {r.finding_id for r in db.scalars(select(Review))}
    pending = [f for f in db.scalars(select(Finding).where(Finding.needs_review.is_(True)))
               if f.id not in reviewed_ids and f.inspection.is_demo == use_demo and p.category_ok(f.category)]
    pending.sort(key=lambda f: f.id, reverse=True)
    # 对抗前后误判率（以园长复核为标准答案）
    solo_err = adv_err = adv_decided = solo_n = 0
    for rv in db.scalars(select(Review)):
        f = db.get(Finding, rv.finding_id)
        if not f or f.inspection.is_demo != use_demo:
            continue
        solo_n += 1
        solo_err += f.solo_judgement != rv.decision
        if f.final_verdict in ("valid", "invalid"):
            adv_decided += 1
            adv_err += f.final_verdict != rv.decision
    # 工单
    wos = [w for w in db.scalars(select(WorkOrder)) if w.is_demo == use_demo]
    n = now_local()
    overdue = [w for w in wos if w.status == "open" and n > w.due_at]
    done = [w for w in wos if w.status == "done"]
    ontime = [w for w in done if w.done_at and w.done_at <= w.due_at]
    by_class: dict[str, list] = defaultdict(lambda: [0, 0])
    for w in done:
        k = db.get(Klass, w.class_id) if w.class_id else None
        key = k.name if k else "职能部门"
        by_class[key][1] += 1
        by_class[key][0] += bool(w.done_at and w.done_at <= w.due_at)
    # 家长端
    pm = [m for m in db.scalars(select(ParentMessage).where(ParentMessage.role == "parent")) if m.is_demo == use_demo]
    auto = sum(m.route == "auto" for m in pm)
    blocked = sum(m.route == "blocked" for m in pm)
    transferred = sum(m.route in ("transfer", "blocked") for m in pm)
    topq = Counter(m.content[:18] for m in pm).most_common(10)
    cal = calendar_today(db)
    reminders = [{"type": r.type, "title": r.title, "due_at": r.due_at.isoformat() if r.due_at else None}
                 for r in db.scalars(select(Reminder).where(Reminder.status == "open"))]
    unconf = db.query(Routine).filter(Routine.confirmed.is_(False), Routine.semester_id == current_semester_id(db)).count()
    if unconf:
        reminders.append({"type": "routine_confirm", "title": f"作息表还有 {unconf} 个时段待园方确认", "due_at": None})
    drafts = db.query(ClassStaff).filter(ClassStaff.status == "draft", ClassStaff.semester_id == current_semester_id(db)).count()
    if drafts:
        reminders.append({"type": "rotation", "title": "本学期班级任职表待园长确认", "due_at": None})
    return {
        "range": range, "data_source": "demo" if use_demo else "real", "has_real": has_real, "calendar": cal,
        "engine": "llm" if llm_enabled(db) else "offline",
        "kpi": {"inspections_today": len(today_insp), "inspections": len(insp), "issues": sum(f.final_verdict != "invalid" for f in fs),
                "pending_review": len(pending), "closure_rate": round(len(closed) / len(issued), 3) if issued else None,
                "rect_issued": len(issued), "rect_closed": len(closed), "rect_drafts": sum(r.status == "draft" for r in rects),
                "review_ratio": round(sum(f.needs_review for f in fs) / len(fs), 3) if fs else None,
                "overdue": len(overdue), "ontime_rate": round(len(ontime) / len(done), 3) if done else None},
        "heatmap": {"segments": SEGMENTS, "classes": [k.name for k in classes],
                    "values": [[heat[s][k.name] for k in classes] for s in SEGMENTS]},
        "pending": [{"id": f.id, "item": f.item, "class_name": f.inspection.klass.name, "segment": f.segment, "category": f.category,
                     "severity": f.severity, "created_at": f.created_at.isoformat(), "review_reason": f.review_reason} for f in pending[:6]],
        "accuracy": {"reviewed": solo_n, "solo_error_rate": round(solo_err / solo_n, 3) if solo_n else None,
                     "adversarial_error_rate": round(adv_err / adv_decided, 3) if adv_decided else None,
                     "adversarial_deferred": solo_n - adv_decided},
        "sla": {"overdue": [{"id": w.id, "title": w.title, "assignee": staff_name(db, w.assignee_staff_id),
                             "level": w.escalation_level, "due_at": w.due_at.isoformat()} for w in overdue[:8]],
                "by_class": [{"name": k, "ontime": v[0], "done": v[1]} for k, v in sorted(by_class.items())]},
        "parent": {"questions": len(pm), "auto_rate": round(auto / len(pm), 3) if pm else None, "blocked": blocked,
                   "transferred": transferred, "top": [{"q": q, "n": c} for q, c in topq]},
        "reminders": reminders,
    }


@router.get("/reminders")
def reminders(p: Principal = Depends(current), db: Session = Depends(get_db)):
    return [{"id": r.id, "type": r.type, "title": r.title, "status": r.status} for r in db.scalars(select(Reminder))]


# ---------- 周报 ----------
@router.post("/reports/weekly")
def weekly(p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    from pydantic import BaseModel as _B
    d = dashboard("week", "auto", p, db)
    seg_tot = {s: sum(row) for s, row in zip(d["heatmap"]["segments"], d["heatmap"]["values"])}
    cls_tot = Counter()
    for row in d["heatmap"]["values"]:
        for c, v in zip(d["heatmap"]["classes"], row):
            cls_tot[c] += v
    stats = (f"本周巡查 {d['kpi']['inspections']} 次，问题 {d['kpi']['issues']} 条，待复核 {d['kpi']['pending_review']} 条；"
             f"整改下发 {d['kpi']['rect_issued']} 单、已关闭 {d['kpi']['rect_closed']} 单；超时工单 {d['kpi']['overdue']} 个。\n"
             f"环节分布：{seg_tot}\n问题较多的班级：{cls_tot.most_common(4)}")

    class W(_B):
        summary: str
        highlights: list[str] = []
        suggestions: list[str] = []

    run = AgentRun(chain="report", source_id=0, is_demo=d["data_source"] == "demo")
    db.add(run)
    db.commit()
    ctx = ChainContext(run.id)
    try:
        top_seg = max(seg_tot, key=seg_tot.get) if seg_tot else "—"
        out, eng = ctx.call("aibao", "weekly", stats, W, "max", lambda: {
            "summary": f"本周共巡查 {d['kpi']['inspections']} 次，发现问题 {d['kpi']['issues']} 条，问题最集中的环节是「{top_seg}」。"
                       f"整改闭环率 {round((d['kpi']['closure_rate'] or 0) * 100)}%。",
            "highlights": [f"{c}班问题 {v} 条" for c, v in cls_tot.most_common(3) if v],
            "suggestions": [f"下周重点巡查「{top_seg}」环节", "对超时工单所在班级开展一次流程复盘", "补全作息表中待确认的时段"]})
        ctx.finish()
    finally:
        ctx.close()
    return {**out, "engine": "llm" if eng.startswith("llm") else "offline", "stats": d["kpi"], "segments": seg_tot,
            "data_source": d["data_source"], "generated_at": now_local().isoformat(), "note": "AI 草稿，经园长确认"}


# ---------- 对话助手 ----------
class AskIn(BaseModel):
    q: str


@router.post("/assistant/chat")
def assistant(body: AskIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.role == "parent":
        raise HTTPException(403)
    q = body.q.strip()
    data_q = any(k in q for k in ("这周", "本周", "哪个环节", "哪个班", "多少", "最多", "统计", "闭环"))
    from pydantic import BaseModel as _B

    class A(_B):
        answer: str
        sources: list[int] = []

    run = AgentRun(chain="assistant", source_id=0)
    db.add(run)
    db.commit()
    ctx = ChainContext(run.id)
    try:
        if data_q and p.role == "principal":
            d = dashboard("week", "auto", p, db)
            seg_tot = {s: sum(row) for s, row in zip(d["heatmap"]["segments"], d["heatmap"]["values"])}
            top = max(seg_tot, key=seg_tot.get)
            stat = f"本周环节问题数：{seg_tot}；巡查 {d['kpi']['inspections']} 次；待复核 {d['kpi']['pending_review']}；闭环率 {d['kpi']['closure_rate']}"
            out, _ = ctx.call("aibao", "assistant", f"问题：{q}\n统计：{stat}", A, "flash",
                              lambda: {"answer": f"本周问题最多的环节是「{top}」（{seg_tot[top]} 条）。共巡查 {d['kpi']['inspections']} 次，"
                                                 f"待复核 {d['kpi']['pending_review']} 条。", "sources": []})
            return {**out, "chunks": [], "data_source": d["data_source"]}
        hits = kb.search(db, q, k=4)
        ref = "\n".join(f"[{h['id']}]《{h['doc_title']}》{h['clause_no']}：{h['text']}" for h in hits)
        out, _ = ctx.call("aibao", "assistant", f"问题：{q}\n条款：\n{ref}", A, "flash",
                          lambda: {"answer": (f"依据《{hits[0]['doc_title']}》{hits[0]['clause_no']}：{hits[0]['text'][:120]}" if hits
                                              else "知识库里没有找到相关条款，请管理员补充制度文件。"),
                                   "sources": [hits[0]["id"]] if hits else []})
        return {**out, "chunks": hits[:3]}
    finally:
        ctx.finish()
        ctx.close()


# ---------- 校历、班级、通知 ----------
@router.get("/calendar/today")
def cal_today(db: Session = Depends(get_db)):
    return calendar_today(db)


@router.get("/classes")
def classes(p: Principal = Depends(current), db: Session = Depends(get_db)):
    sid = current_semester_id(db)
    out = []
    for k in db.scalars(select(Klass).where(Klass.active.is_(True)).order_by(Klass.order)):
        rows = list(db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid, ClassStaff.class_id == k.id)))
        out.append({"id": k.id, "name": k.name, "grade": k.grade, "mine": k.id in p.class_ids,
                    "staff": [{"id": r.staff_id, "name": r.staff.name, "slot": r.slot, "shift": r.shift, "is_lead": r.is_lead,
                               "teaching_role": r.teaching_role, "status": r.status} for r in rows]})
    return out


@router.get("/classes/{cid}/stats")
def class_stats(cid: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    from ..models import Child
    k = db.get(Klass, cid)
    kids = list(db.scalars(select(Child).where(Child.class_id == cid, Child.status == "在园")))
    fs = [f for f in db.scalars(select(Finding)) if f.inspection.class_id == cid]
    return {"name": k.name, "children": len(kids) or k.ref_count, "boys": sum(c.gender == "男" for c in kids) or k.ref_boys,
            "girls": sum(c.gender == "女" for c in kids) or k.ref_girls, "from_roster": bool(kids),
            "inspections": db.query(Inspection).filter(Inspection.class_id == cid).count(), "findings": len(fs)}


@router.get("/notifications")
def notifications(p: Principal = Depends(current), db: Session = Depends(get_db)):
    if not p.staff:
        return []
    return [{"id": n.id, "title": n.title, "body": n.body, "created_at": n.created_at.isoformat(), "read": bool(n.read_at)}
            for n in db.scalars(select(Notification).where(Notification.staff_id == p.staff.id).order_by(Notification.id.desc()).limit(30))]


@router.post("/notifications/read")
def read_all(p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.staff:
        for n in db.scalars(select(Notification).where(Notification.staff_id == p.staff.id, Notification.read_at.is_(None))):
            n.read_at = now_local()
        db.commit()
    return {"ok": True}


@router.get("/staff/search")
def staff_search(q: str = "", p: Principal = Depends(current), db: Session = Depends(get_db)):
    rows = db.scalars(select(Staff).where(Staff.name.contains(q)).limit(30)) if q else db.scalars(select(Staff).limit(200))
    return [{"id": s.id, "name": s.name, "note": s.note} for s in rows]


# ---------- 品牌与形象（未登录可访问，只读展示，不进模型） ----------
@router.get("/brand")
def brand(db: Session = Depends(get_db)):
    out = {"name": "宝鸡幼儿园", "product": "爱宝园务大脑", "palette": {"primary": "#019E33", "secondary": "#C4EA03", "accent": "#F56D01"}}
    assets = {b.kind: f"/api/brand/file/{b.id}" for b in db.scalars(select(BrandAsset).where(BrandAsset.active.is_(True)))}
    out["assets"] = assets
    return out


@router.get("/brand/file/{bid}")
def brand_file(bid: int, db: Session = Depends(get_db)):
    b = db.get(BrandAsset, bid)
    if not b:
        raise HTTPException(404)
    return FileResponse(b.path)


@router.get("/avatars")
def avatars(agent: str | None = None, db: Session = Depends(get_db)):
    q = select(Avatar).where(Avatar.active.is_(True))
    if agent:
        q = q.where(Avatar.agent == agent)
    out: dict = {}
    for a in db.scalars(q):
        out.setdefault(a.agent, {})[a.view] = f"/api/avatars/file/{a.id}"
    return {"agents": AGENTS, "images": out}


@router.get("/avatars/file/{aid}")
def avatar_file(aid: int, db: Session = Depends(get_db)):
    a = db.get(Avatar, aid)
    if not a:
        raise HTTPException(404)
    return FileResponse(a.image_path, headers={"Cache-Control": "public, max-age=3600"})
