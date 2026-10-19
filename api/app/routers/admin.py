"""管理员端：导入中心、知识库、组织与账号、学期任职与轮换、作息课表、模型阈值、脱敏日志、时限规则、幼儿名册、邀请码。"""
from __future__ import annotations

import secrets
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, kb
from ..db import get_db
from ..importer import images as img
from ..importer import template as tpl
from ..models import (Avatar, BrandAsset, Child, ClassStaff, ImportJob, Invite, KbDoc, Klass, ModelCall, Position, RedactionLog,
                      Routine, Semester, SemesterWeek, Setting, SlaPolicy, SpecialCourse, Staff, User, UserPosition)
from ..security import Principal, current, decrypt, hash_pw, require
from ..services.calendar import current_semester_id
from ..timeutil import now_local

router = APIRouter(prefix="/admin")
admin_only = require("admin")
IMPORT_DIR = config.DATA_DIR / "imports"
IMPORT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------- 导入中心 ----------------
@router.get("/import/templates")
def download_template(p: Principal = Depends(admin_only)):
    return FileResponse(config.SEED_TEMPLATE, filename="爱宝保教智囊团_管理员导入模板_2026秋.xlsx")


@router.post("/import/upload")
async def import_upload(kind: str = Form(...), file: UploadFile = File(...), strip_bg: bool = Form(False), agent: str = Form(""),
                        view: str = Form("front"), p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    data = await file.read()
    ext = Path(file.filename or "").suffix.lower()
    path = IMPORT_DIR / f"{uuid.uuid4().hex}{ext}"
    path.write_bytes(data)
    version = (db.query(ImportJob).filter(ImportJob.kind == kind).count() or 0) + 1
    job = ImportJob(kind=kind, filename=file.filename or "", file_path=str(path), version=version, operator_id=p.user.id)
    if kind in ("staff", "calendar", "routine", "course", "children", "all"):
        if ext not in (".xlsx", ".xlsm"):
            raise HTTPException(400, "请上传 xlsx 模板文件")
        report = tpl.validate(db, kind, tpl.parse(path))
    elif kind == "logo":
        if ext not in (".png", ".jpg", ".jpeg", ".svg", ".webp") or len(data) > 5 * 1024 * 1024:
            raise HTTPException(400, "园徽支持 PNG/JPG/SVG，≤ 5MB")
        try:
            res = img.process_logo(path, version, strip_bg)
            report = {"red": [], "yellow": [], "green": ["已生成顶栏、登录页、浏览器图标、PDF 页眉四种尺寸"],
                      "preview": {"paths": res["paths"], "palette": res["palette"]}, "ok": True}
        except ValueError as e:
            report = {"red": [str(e)], "yellow": [], "green": [], "preview": {}, "ok": False}
    elif kind in ("mascot", "avatar"):
        faces = img.has_real_face(path)
        if faces:
            report = {"red": [f"检测到 {faces} 张真人人脸：吉祥物只接受纯形象图（短片截图等含真人的图片不能导入）"],
                      "yellow": [], "green": [], "preview": {}, "ok": False}
        else:
            saved = img.save_avatar(path, agent or "aibao", view, version, strip_bg)
            report = {"red": [], "yellow": [] if ext == ".png" else ["JPG 已自动抠除白底，请在预览中确认边缘"],
                      "green": [f"已绑定到 {agent} · {view}"], "preview": {"path": saved, "agent": agent, "view": view}, "ok": True}
    elif kind == "kb":
        report = {"red": [] if ext in (".pdf", ".docx", ".doc", ".txt", ".md") else ["只支持 PDF / Word / 文本"], "yellow": [],
                  "green": [], "preview": {}, "ok": ext in (".pdf", ".docx", ".doc", ".txt", ".md")}
    else:
        raise HTTPException(400, "未知导入类型")
    job.report_json = report
    db.add(job)
    db.commit()
    return {"job_id": job.id, "kind": kind, "version": version, **{k: v for k, v in report.items() if k != "snapshot"}}


class CommitIn(BaseModel):
    effective_from: str | None = None


@router.post("/import/{job_id}/commit")
def import_commit(job_id: int, body: CommitIn, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    job = db.get(ImportJob, job_id)
    if not job or job.status != "validated":
        raise HTTPException(400, "该导入不可确认")
    rep = job.report_json
    if not rep.get("ok"):
        raise HTTPException(400, "校验报告有红色问题，必须修正后重新上传")
    if body.effective_from:
        job.effective_from = date.fromisoformat(body.effective_from)
    result: dict = {}
    if job.kind in ("staff", "calendar", "routine", "course", "children", "all"):
        result = tpl.commit(db, job, tpl.parse(Path(job.file_path)), rep)
    elif job.kind == "logo":
        db.query(BrandAsset).update({BrandAsset.active: False})
        for kind_, pth in rep["preview"]["paths"].items():
            db.add(BrandAsset(kind=kind_, path=pth, source_path=job.file_path, palette_json={"colors": rep["preview"]["palette"]},
                              version=job.version, active=True))
        job.status = "committed"
    elif job.kind in ("mascot", "avatar"):
        pv = rep["preview"]
        db.query(Avatar).filter(Avatar.agent == pv["agent"], Avatar.view == pv["view"]).update({Avatar.active: False})
        db.add(Avatar(agent=pv["agent"], view=pv["view"], image_path=pv["path"], version=job.version, active=True))
        job.status = "committed"
    db.commit()
    return {"ok": True, "result": result}


@router.post("/import/{job_id}/rollback")
def import_rollback(job_id: int, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    job = db.get(ImportJob, job_id)
    if not job or job.status != "committed":
        raise HTTPException(400, "只能回滚已生效的导入")
    if job.kind in ("logo", "mascot", "avatar"):
        if job.kind == "logo":
            db.query(BrandAsset).filter(BrandAsset.version == job.version).update({BrandAsset.active: False})
            prev = db.scalars(select(BrandAsset).where(BrandAsset.version < job.version).order_by(BrandAsset.version.desc())).first()
            if prev:
                db.query(BrandAsset).filter(BrandAsset.version == prev.version).update({BrandAsset.active: True})
        else:
            pv = job.report_json["preview"]
            db.query(Avatar).filter(Avatar.agent == pv["agent"], Avatar.view == pv["view"]).delete()
    else:
        snap = job.report_json.get("snapshot")
        if not snap:
            raise HTTPException(400, "没有可回滚的快照")
        tpl.restore(db, snap)
    job.status = "rolled_back"
    db.commit()
    return {"ok": True}


@router.get("/import/jobs")
def import_jobs(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    return [{"id": j.id, "kind": j.kind, "filename": j.filename, "version": j.version, "status": j.status,
             "created_at": j.created_at.isoformat(), "effective_from": j.effective_from.isoformat() if j.effective_from else None,
             "red": len(j.report_json.get("red", [])), "yellow": len(j.report_json.get("yellow", [])),
             "result": j.report_json.get("result")}
            for j in db.scalars(select(ImportJob).order_by(ImportJob.id.desc()))]


@router.get("/import/password-file/{name}")
def pw_file(name: str, p: Principal = Depends(admin_only)):
    f = config.DATA_DIR / Path(name).name
    if not f.exists() or not f.name.startswith("initial_passwords"):
        raise HTTPException(404)
    return FileResponse(f, filename=f.name)


@router.get("/setup-wizard")
def wizard(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    sid = current_semester_id(db)
    steps = [
        ("园所信息与园徽", db.query(BrandAsset).filter(BrandAsset.active.is_(True)).count() > 0),
        ("组织架构与岗位（已预置）", db.query(Position).count() > 0),
        ("人员名单", db.query(Staff).count() > 0),
        ("校历", db.query(SemesterWeek).filter(SemesterWeek.semester_id == sid).count() > 0),
        ("作息与特色课表", db.query(Routine).count() > 0 and db.query(SpecialCourse).count() > 0),
        ("吉祥物与智能体形象", db.query(Avatar).filter(Avatar.agent.in_(["aibao", "xingbao"])).count() >= 2),
        ("知识库文件", db.query(KbDoc).filter(KbDoc.is_sample.is_(False)).count() > 0),
        ("模型与阈值", bool(config.LLM_API_KEY)),
    ]
    return [{"step": s, "done": d} for s, d in steps]


# ---------------- 知识库 ----------------
@router.get("/kb/docs")
def kb_docs(p: Principal = Depends(current), db: Session = Depends(get_db)):
    if p.role not in ("admin", "principal", "mentor"):
        raise HTTPException(403)
    return [{"id": d.id, "title": d.title, "kind": d.kind, "visibility": d.visibility, "status": d.status, "chunk_count": d.chunk_count,
             "is_sample": d.is_sample, "created_at": d.created_at.isoformat()}
            for d in db.scalars(select(KbDoc).order_by(KbDoc.id.desc()))]


@router.post("/kb/docs")
async def kb_upload(file: UploadFile = File(...), title: str = Form(""), kind: str = Form("policy"), visibility: str = Form("internal"),
                    p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".pdf", ".docx", ".doc", ".txt", ".md"):
        raise HTTPException(400, "只支持 PDF / Word / 文本")
    path = config.DATA_DIR / "kb" / f"{uuid.uuid4().hex}{ext}"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(await file.read())
    doc = KbDoc(title=title or Path(file.filename).stem, kind=kind, visibility=visibility, file_path=str(path), status="parsing")
    db.add(doc)
    db.commit()
    try:
        n = kb.ingest(db, doc)
    except Exception as e:  # noqa: BLE001
        doc.status = "failed"
        db.commit()
        raise HTTPException(422, f"解析失败：{e}")
    db.commit()
    return {"id": doc.id, "chunk_count": n, "status": doc.status}


@router.delete("/kb/docs/{did}")
def kb_delete(did: int, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    d = db.get(KbDoc, did)
    if d:
        from ..models import KbChunk
        db.query(KbChunk).filter(KbChunk.doc_id == did).delete()
        db.delete(d)
        db.commit()
        kb._idx.clear()
    return {"ok": True}


@router.get("/kb/docs/{did}/chunks")
def kb_chunks(did: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    from ..models import KbChunk
    return [{"id": c.id, "clause_no": c.clause_no, "text": c.text} for c in db.scalars(select(KbChunk).where(KbChunk.doc_id == did))]


@router.post("/kb/reindex")
def kb_reindex(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    n = 0
    for d in db.scalars(select(KbDoc)):
        if d.file_path and Path(d.file_path).exists():
            n += kb.ingest(db, d)
    db.commit()
    return {"chunks": n}


@router.get("/kb/search")
def kb_search(q: str, visibility: str | None = None, p: Principal = Depends(current), db: Session = Depends(get_db)):
    return kb.search(db, q, k=8, visibility=visibility)


# ---------------- 设置 ----------------
DEFAULT_MODELS = {"aibao": "flash", "xingbao": "max", "humiao": "flash", "mingli": "max", "xiaobu": "flash", "weishi": "max",
                  "xiaoyi": "flash", "xiaoshi": "flash", "xiaojia": "flash", "xiaodun": "flash"}


@router.get("/settings")
def get_settings(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    def g(k, d):
        s = db.get(Setting, k)
        return s.value if s else d
    return {"llm_base_url": g("llm_base_url", config.LLM_BASE_URL), "api_key_set": bool(config.LLM_API_KEY),
            "model_fast": config.LLM_MODEL_FAST, "model_strong": config.LLM_MODEL_STRONG,
            "agent_models": {**DEFAULT_MODELS, **g("agent_models", {})},
            "agent_thinking": {**{k: False for k in DEFAULT_MODELS}, **g("agent_thinking", {})},
            "thresholds": {"review_confidence": config.REVIEW_CONFIDENCE_THRESHOLD, "debate_rounds": config.DEBATE_MAX_ROUNDS,
                           "force_review_categories": config.FORCE_REVIEW_CATEGORIES, **g("thresholds", {})},
            "reminder_days": g("reminder_days", {"first": 14, "second": 7}),
            "calls": [{"agent": c.agent, "model": c.model, "ok": c.ok, "latency_ms": c.latency_ms, "at": c.created_at.isoformat(),
                       "error": c.error} for c in db.scalars(select(ModelCall).order_by(ModelCall.id.desc()).limit(20))]}


class SettingsIn(BaseModel):
    llm_base_url: str | None = None
    agent_models: dict | None = None
    agent_thinking: dict | None = None
    thresholds: dict | None = None
    reminder_days: dict | None = None


@router.put("/settings")
def put_settings(body: SettingsIn, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_none=True).items():
        s = db.get(Setting, k)
        if s:
            s.value = v
        else:
            db.add(Setting(key=k, value=v))
    db.commit()
    return {"ok": True}


@router.post("/llm/test")
def llm_test(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    from ..gateway import pass_through_gateway
    from ..llm.client import LLMUnavailable, chat_json
    try:
        pl = pass_through_gateway(db, "请回复 JSON：{\"ok\": true}", agent="test")
        out = chat_json(db, agent="test", system="只输出 JSON", payload=pl, tier="flash", retries=0)
        db.commit()
        return {"ok": True, "reply": out}
    except LLMUnavailable as e:
        db.commit()
        return {"ok": False, "error": str(e)}


@router.get("/redaction-logs")
def redaction_logs(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    return [{"id": r.id, "call_id": r.call_id, "agent": r.agent, "before": r.before_preview, "after": r.after_text, "faces": r.faces,
             "replacements": r.replacements_json, "created_at": r.created_at.isoformat()}
            for r in db.scalars(select(RedactionLog).order_by(RedactionLog.id.desc()).limit(100))]


@router.get("/media-logs")
def media_logs(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    from ..models import Media
    return [{"id": m.id, "kind": m.kind, "faces": m.faces, "redacted": f"/api/media/{m.id}/redacted" if m.path_redacted else None,
             "created_at": m.created_at.isoformat()} for m in db.scalars(select(Media).order_by(Media.id.desc()).limit(50))]


# ---------------- 时限与升级规则 ----------------
@router.get("/sla-policies")
def sla(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    return [{"id": s.id, "type": s.type, "severity": s.severity, "duration_minutes": s.duration_minutes, "remind_ratio": s.remind_ratio,
             "escalation": s.escalation_json, "label": s.label} for s in db.scalars(select(SlaPolicy))]


class SlaIn(BaseModel):
    id: int
    duration_minutes: int
    remind_ratio: float


@router.put("/sla-policies")
def put_sla(body: list[SlaIn], p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    for b in body:
        s = db.get(SlaPolicy, b.id)
        if s:
            s.duration_minutes, s.remind_ratio = b.duration_minutes, b.remind_ratio
    db.commit()
    return {"ok": True}


# ---------------- 组织、人员、班级 ----------------
@router.get("/positions")
def positions(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    out = []
    for pos in db.scalars(select(Position)):
        holders = [db.get(Staff, up.staff_id).name for up in db.scalars(select(UserPosition).where(UserPosition.position_id == pos.id))
                   if up.semester_id in (None, current_semester_id(db))]
        out.append({"id": pos.id, "name": pos.name, "tier": pos.permission_template, "portal": pos.portal, "scope": pos.data_scope,
                    "holders": holders})
    return out


@router.get("/staff")
def staff_list(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    out = []
    for s in db.scalars(select(Staff).order_by(Staff.id)):
        u = db.scalar(select(User).where(User.staff_id == s.id))
        ps = [up.position.name for up in db.scalars(select(UserPosition).where(UserPosition.staff_id == s.id))]
        out.append({"id": s.id, "name": s.name, "phone": s.phone, "status": s.status, "note": s.note, "login": u.login if u else None,
                    "role": u.role if u else None, "positions": sorted(set(ps))})
    return out


class StaffPosIn(BaseModel):
    staff_id: int
    position: str
    add: bool = True


@router.post("/user-positions")
def set_pos(body: StaffPosIn, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    pos = db.scalar(select(Position).where(Position.name == body.position))
    if not pos:
        raise HTTPException(400, "岗位不存在")
    if body.add:
        db.add(UserPosition(staff_id=body.staff_id, position_id=pos.id))
        if pos.portal == "principal":
            u = db.scalar(select(User).where(User.staff_id == body.staff_id))
            if u:
                u.role = "principal"
    else:
        db.query(UserPosition).filter(UserPosition.staff_id == body.staff_id, UserPosition.position_id == pos.id).delete()
    db.commit()
    return {"ok": True}


@router.post("/staff/{sid}/reset-password")
def reset_pw(sid: int, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.staff_id == sid))
    if not u:
        raise HTTPException(404)
    pw = secrets.token_urlsafe(6)
    u.password_hash, u.must_change_password = hash_pw(pw), True
    db.commit()
    return {"login": u.login, "password": pw}


@router.get("/classes")
def admin_classes(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    sid = current_semester_id(db)
    out = []
    for k in db.scalars(select(Klass).order_by(Klass.order)):
        kids = list(db.scalars(select(Child).where(Child.class_id == k.id, Child.status == "在园")))
        rows = list(db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid, ClassStaff.class_id == k.id)))
        out.append({"id": k.id, "name": k.name, "grade": k.grade, "active": k.active, "template": k.template,
                    "children": len(kids) if kids else k.ref_count, "boys": sum(c.gender == "男" for c in kids) if kids else k.ref_boys,
                    "girls": sum(c.gender == "女" for c in kids) if kids else k.ref_girls, "from_roster": bool(kids),
                    "staff": [{"id": r.id, "staff_id": r.staff_id, "name": r.staff.name, "slot": r.slot, "shift": r.shift,
                               "is_lead": r.is_lead, "teaching_role": r.teaching_role, "status": r.status,
                               "not_rotated_reason": r.not_rotated_reason} for r in rows]})
    return out


class ClassIn(BaseModel):
    name: str
    grade: str
    active: bool = True


@router.post("/classes")
def add_class(body: ClassIn, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    k = db.scalar(select(Klass).where(Klass.name == body.name))
    if k:
        k.grade, k.active = body.grade, body.active
    else:
        db.add(Klass(name=body.name, grade=body.grade, active=body.active, order=900,
                     template="big" if body.grade == "big" else "small_middle"))
    db.commit()
    return {"ok": True}


@router.get("/children")
def children(class_id: int | None = None, p: Principal = Depends(current), db: Session = Depends(get_db)):
    q = select(Child)
    if class_id:
        q = q.where(Child.class_id == class_id)
    see_names = p.role in ("principal",) or "保健室" in p.positions
    out = []
    for c in db.scalars(q):
        if p.role != "admin" and not p.can_see_class(c.class_id):
            continue
        show = see_names or c.class_id in p.class_ids
        out.append({"id": c.id, "code": c.code, "class_id": c.class_id, "gender": c.gender, "status": c.status,
                    "name": decrypt(c.name_encrypted) if show else None})
    return out


@router.post("/invites")
def make_invite(class_id: int, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    code = secrets.token_hex(3).upper()
    db.add(Invite(code=code, class_id=class_id))
    db.commit()
    return {"code": code}


@router.get("/invites")
def list_invites(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    names = {k.id: k.name for k in db.scalars(select(Klass))}
    return [{"code": i.code, "class_name": names.get(i.class_id), "revoked": i.revoked} for i in db.scalars(select(Invite))]


# ---------------- 学期任职与轮换 ----------------
@router.get("/semesters")
def semesters(p: Principal = Depends(current), db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name, "start": s.start_date.isoformat(), "end": s.end_date.isoformat(), "status": s.status,
             "weeks": [{"no": w.week_no, "ranges": w.ranges_json, "parity": w.parity}
                       for w in db.scalars(select(SemesterWeek).where(SemesterWeek.semester_id == s.id).order_by(SemesterWeek.week_no))]}
            for s in db.scalars(select(Semester))]


@router.post("/semesters/next/assignments")
def swap_draft(swap_shift: bool = False, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    """按惯例互换：生成下学期草案（两名班级教师教学 / 保育角色互换；早班可选互换），提交园长确认。"""
    cur = db.get(Semester, current_semester_id(db))
    nxt = db.scalar(select(Semester).where(Semester.name == "2027春"))
    if not nxt:
        nxt = Semester(name="2027春", start_date=date(2027, 2, 22), end_date=date(2027, 7, 9), status="draft")
        db.add(nxt)
        db.flush()
    db.query(ClassStaff).filter(ClassStaff.semester_id == nxt.id).delete()
    n = 0
    for r in db.scalars(select(ClassStaff).where(ClassStaff.semester_id == cur.id)):
        role, shift = r.teaching_role, r.shift
        if r.slot == "teacher":
            role = {"teaching": "care", "care": "teaching"}.get(r.teaching_role or "", r.teaching_role)
            if swap_shift:
                shift = {"mon_wed_fri": "tue_thu", "tue_thu": "mon_wed_fri"}.get(shift or "", shift)
        db.add(ClassStaff(semester_id=nxt.id, class_id=r.class_id, slot=r.slot, shift=shift, is_lead=r.is_lead, teaching_role=role,
                          staff_id=r.staff_id, status="draft"))
        n += 1
    db.commit()
    return {"semester": nxt.name, "rows": n, "status": "draft"}


@router.get("/semesters/{sid}/assignments")
def assignments(sid: int, p: Principal = Depends(current), db: Session = Depends(get_db)):
    names = {k.id: k.name for k in db.scalars(select(Klass))}
    prev = {}
    if sid != current_semester_id(db):
        for r in db.scalars(select(ClassStaff).where(ClassStaff.semester_id == current_semester_id(db))):
            prev[(r.class_id, r.staff_id)] = r.teaching_role
    return [{"id": r.id, "class_name": names.get(r.class_id), "class_id": r.class_id, "name": r.staff.name, "slot": r.slot,
             "shift": r.shift, "teaching_role": r.teaching_role, "is_lead": r.is_lead, "status": r.status,
             "not_rotated": r.slot == "teacher" and prev.get((r.class_id, r.staff_id)) == r.teaching_role and bool(prev),
             "not_rotated_reason": r.not_rotated_reason}
            for r in db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid).order_by(ClassStaff.class_id))]


@router.post("/semesters/{sid}/assignments/confirm")
def confirm_assignments(sid: int, p: Principal = Depends(require("principal")), db: Session = Depends(get_db)):
    for r in db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid)):
        r.status, r.confirmed_by, r.confirmed_at = "confirmed", p.user.id, now_local()
    db.commit()
    return {"ok": True}


@router.get("/routines")
def routines(p: Principal = Depends(current), db: Session = Depends(get_db)):
    sid = current_semester_id(db)
    return [{"id": r.id, "start": r.start, "end": r.end, "segment": r.segment, "segment_key": r.segment_key, "grade": r.grade,
             "source": r.source, "confirmed": r.confirmed}
            for r in db.scalars(select(Routine).where(Routine.semester_id == sid).order_by(Routine.start))]


@router.patch("/routines/{rid}")
def confirm_routine(rid: int, confirmed: bool = True, p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    r = db.get(Routine, rid)
    r.confirmed = confirmed
    db.commit()
    return {"ok": True}


@router.get("/special-courses")
def courses(p: Principal = Depends(current), db: Session = Depends(get_db)):
    sid = current_semester_id(db)
    return [{"week_type": c.week_type, "weekday": c.weekday, "start": c.start, "end": c.end, "course": c.course,
             "class_name": c.class_name, "teacher": c.teacher_label}
            for c in db.scalars(select(SpecialCourse).where(SpecialCourse.semester_id == sid))]


# ---------------- 演示数据 ----------------
@router.post("/demo/seed")
def demo_seed(p: Principal = Depends(admin_only)):
    from ..seed import seed_demo_activity
    return seed_demo_activity(force=True)


@router.post("/demo/clear")
def demo_clear(p: Principal = Depends(admin_only), db: Session = Depends(get_db)):
    from ..models import AgentRun, Finding, Inspection, ParentMessage, Rectification, WorkOrder
    ids = [i.id for i in db.scalars(select(Inspection).where(Inspection.is_demo.is_(True)))]
    db.query(Finding).filter(Finding.inspection_id.in_(ids or [0])).delete(synchronize_session=False)
    db.query(AgentRun).filter(AgentRun.chain == "inspect", AgentRun.source_id.in_(ids or [0])).delete(synchronize_session=False)
    db.query(Inspection).filter(Inspection.is_demo.is_(True)).delete(synchronize_session=False)
    db.query(Rectification).filter(Rectification.is_demo.is_(True)).delete(synchronize_session=False)
    db.query(WorkOrder).filter(WorkOrder.is_demo.is_(True)).delete(synchronize_session=False)
    db.query(ParentMessage).filter(ParentMessage.is_demo.is_(True)).delete(synchronize_session=False)
    db.commit()
    return {"removed_inspections": len(ids)}
