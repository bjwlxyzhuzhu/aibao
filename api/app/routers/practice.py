"""实践教学接口：学生提交实践记录与反思；高校导师 / 园所导师评阅（五维评分 + 问题条目确认 + 评语）；成长档案；成效导出。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents.base import run_in_background
from ..agents.inspect_chain import run_inspection
from ..db import get_db
from ..gateway.redact_text import TextRedactor
from ..models import (AgentMessage, AgentRun, Finding, Inspection, Klass, Media, PracticeRecord, PracticeStudent, Review,
                      RubricScore, User)
from ..security import Principal, current
from ..services.calendar import current_semester_id, week_of
from ..services.practice import DIM_FULL, DIMS, final_scores, growth, metrics, metrics_markdown
from ..timeutil import now_local
from .inspect import _inspection_out

router = APIRouter(prefix="/practice")


def _me_student(db: Session, p: Principal) -> PracticeStudent:
    s = db.scalar(select(PracticeStudent).where(PracticeStudent.user_id == p.user.id))
    if not s:
        raise HTTPException(403, "当前账号不是见习 / 实习学生")
    return s


def _mentor_kind(db: Session, p: Principal, st: PracticeStudent) -> str | None:
    """返回 mentor_u（高校导师）/ mentor_k（园所导师）/ None。"""
    if p.role == "mentor" and (st.mentor_u_user_id in (None, p.user.id)):
        return "mentor_u"
    if p.staff and (st.mentor_k_staff_id == p.staff.id or (st.class_id and st.class_id in p.class_ids)):
        return "mentor_k"
    if p.role in ("principal", "admin"):
        return "mentor_k"
    return None


def _visible_students(db: Session, p: Principal) -> list[PracticeStudent]:
    rows = list(db.scalars(select(PracticeStudent).order_by(PracticeStudent.id)))
    if p.role == "student":
        return [s for s in rows if s.user_id == p.user.id]
    return [s for s in rows if _mentor_kind(db, p, s)]


def _record_out(db: Session, r: PracticeRecord, p: Principal, detail: bool = False) -> dict:
    insp = db.get(Inspection, r.inspection_id)
    st = db.get(PracticeStudent, r.student_id)
    ai = {x.dim: {"score": x.score, "evidence": x.evidence, "cited": x.cited_chunk_ids}
          for x in db.scalars(select(RubricScore).where(RubricScore.record_id == r.id, RubricScore.source == "ai"))}
    out = {"id": r.id, "student_id": st.id, "student": st.code, "cohort": st.cohort, "week_no": r.week_no,
           "segment": insp.segment, "class_name": insp.klass.name if insp.klass else "", "created_at": r.created_at.isoformat(),
           "status": insp.status, "reflection": r.reflection, "mentor_u_comment": r.mentor_u_comment, "mentor_k_comment": r.mentor_k_comment,
           "mentor_u_done": bool(r.mentor_u_at), "mentor_k_done": bool(r.mentor_k_at), "ai_scores": ai,
           "final_scores": final_scores(db, r.id), "is_demo": r.is_demo, "text": insp.text_raw[:80]}
    if detail:
        out["inspection"] = _inspection_out(db, insp, p, detail=True)
        run = db.scalar(select(AgentRun).where(AgentRun.chain == "inspect", AgentRun.source_id == insp.id).order_by(AgentRun.id.desc()))
        out["run_id"] = run.id if run else None
        sug = db.scalar(select(AgentMessage).where(AgentMessage.run_id == (run.id if run else 0), AgentMessage.agent == "xiaobu"))
        out["suggestions"] = (sug.content_json or {}).get("suggestions", []) if sug else []
        out["mentor_kind"] = _mentor_kind(db, p, st) if p.role != "student" else None
        out["dims"] = [{"key": d, "name": DIM_FULL[d]} for d in DIMS]
    return out


class RecordIn(BaseModel):
    segment: str
    text: str
    media_ids: list[int] = []


@router.post("/records")
def submit(body: RecordIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    st = _me_student(db, p)
    if not body.text.strip():
        raise HTTPException(400, "请填写实践记录")
    redacted, _ = TextRedactor.from_db(db).redact(body.text)
    w = week_of(db)
    insp = Inspection(semester_id=current_semester_id(db), week_no=w.week_no if w else None, class_id=st.class_id, segment=body.segment,
                      submitter_id=None, text_raw=body.text.strip(), text_redacted=redacted, media_ids=body.media_ids, is_demo=st.is_demo)
    db.add(insp)
    db.flush()
    for mid in body.media_ids:
        m = db.get(Media, mid)
        if m:
            m.owner_type, m.owner_id = "practice", insp.id
    n_prev = db.query(PracticeRecord).filter(PracticeRecord.student_id == st.id).count()
    first = db.scalar(select(PracticeRecord).where(PracticeRecord.student_id == st.id).order_by(PracticeRecord.created_at))
    week = 1 if not first else max(1, (now_local().date() - first.created_at.date()).days // 7 + 1)
    rec = PracticeRecord(student_id=st.id, inspection_id=insp.id, week_no=week, is_demo=st.is_demo)
    db.add(rec)
    run = AgentRun(chain="inspect", source_id=insp.id, is_demo=st.is_demo)
    db.add(run)
    db.commit()
    run_in_background(lambda: run_inspection(run.id, insp.id))
    return {"record_id": rec.id, "run_id": run.id, "inspection_id": insp.id, "nth": n_prev + 1}


@router.get("/records")
def records(student_id: int | None = None, p: Principal = Depends(current), db: Session = Depends(get_db)):
    sids = {s.id for s in _visible_students(db, p)}
    if student_id:
        sids &= {student_id}
    rows = db.scalars(select(PracticeRecord).where(PracticeRecord.student_id.in_(sids or {0})).order_by(PracticeRecord.id.desc()))
    return [_record_out(db, r, p) for r in rows]


@router.get("/records/{rid}")
def record(rid: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    r = db.get(PracticeRecord, rid)
    if not r or r.student_id not in {s.id for s in _visible_students(db, p)}:
        raise HTTPException(404)
    return _record_out(db, r, p, detail=True)


class ReflectIn(BaseModel):
    text: str


@router.post("/records/{rid}/reflection")
def reflect(rid: int, body: ReflectIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    st = _me_student(db, p)
    r = db.get(PracticeRecord, rid)
    if not r or r.student_id != st.id:
        raise HTTPException(404)
    r.reflection, r.reflection_at = body.text.strip(), now_local()
    db.commit()
    return {"ok": True}


class ReviewIn(BaseModel):
    scores: dict[str, int]
    comment: str = ""
    findings: dict[int, str] = {}  # finding_id -> valid / invalid


@router.post("/records/{rid}/review")
def review(rid: int, body: ReviewIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    r = db.get(PracticeRecord, rid)
    st = db.get(PracticeStudent, r.student_id) if r else None
    kind = _mentor_kind(db, p, st) if st else None
    if not kind:
        raise HTTPException(403, "只有该生的高校导师或园所导师可以评阅")
    db.query(RubricScore).filter(RubricScore.record_id == rid, RubricScore.source == kind).delete()
    for d, v in body.scores.items():
        if d in DIMS:
            db.add(RubricScore(record_id=rid, dim=d, score=max(1, min(5, int(v))), source=kind, evidence="导师评阅"))
    for fid, dec in body.findings.items():
        f = db.get(Finding, int(fid))
        if f and f.inspection_id == r.inspection_id and dec in ("valid", "invalid"):
            db.add(Review(finding_id=f.id, reviewer_staff_id=p.staff.id if p.staff else None, decision=dec, note=kind))
            f.status = "reviewed"
    if kind == "mentor_u":
        r.mentor_u_comment, r.mentor_u_at = body.comment, now_local()
    else:
        r.mentor_k_comment, r.mentor_k_at = body.comment, now_local()
    db.commit()
    return {"ok": True, "as": kind}


@router.get("/me")
def me(p: Principal = Depends(current), db: Session = Depends(get_db)):
    st = _me_student(db, p)
    k = db.get(Klass, st.class_id) if st.class_id else None
    return {"id": st.id, "code": st.code, "cohort": st.cohort, "class_name": k.name if k else None, "growth": growth(db, st.id),
            "dims": [{"key": d, "name": DIM_FULL[d]} for d in DIMS]}


@router.get("/students")
def students(p: Principal = Depends(current), db: Session = Depends(get_db)):
    out = []
    for s in _visible_students(db, p):
        g = growth(db, s.id)
        recs = list(db.scalars(select(PracticeRecord).where(PracticeRecord.student_id == s.id)))
        k = db.get(Klass, s.class_id) if s.class_id else None
        kind = _mentor_kind(db, p, s)
        pending = sum(1 for r in recs if not (r.mentor_u_at if kind == "mentor_u" else r.mentor_k_at))
        out.append({"id": s.id, "code": s.code, "cohort": s.cohort, "class_name": k.name if k else "", "records": len(recs),
                    "pending": pending, "start_avg": g["start_avg"], "recent_avg": g["recent_avg"], "value_added": g["value_added"],
                    "series": g["series"], "is_demo": s.is_demo})
    return out


@router.get("/students/{sid}/growth")
def student_growth(sid: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    if sid not in {s.id for s in _visible_students(db, p)}:
        raise HTTPException(404)
    return {**growth(db, sid), "dims": [{"key": d, "name": DIM_FULL[d]} for d in DIMS]}


@router.get("/metrics")
def get_metrics(source: str = "real", p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.role not in ("mentor", "principal", "admin"):
        raise HTTPException(403)
    return metrics(db, demo={"real": False, "demo": True}.get(source))


@router.get("/metrics.md", response_class=PlainTextResponse)
def get_metrics_md(source: str = "real", p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.role not in ("mentor", "principal", "admin"):
        raise HTTPException(403)
    m = metrics(db, demo={"real": False, "demo": True}.get(source))
    return metrics_markdown(m, {"real": "真实使用数据", "demo": "演示数据"}.get(source, "全部"))
