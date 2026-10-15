"""数据模型：与 PRD 第 7.3 节表结构一一对应（SQLite 开发 / PostgreSQL 生产通用）。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    from .timeutil import now_local
    return now_local()


# ---------- 组织与人员 ----------
class OrgUnit(Base):
    __tablename__ = "org_units"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    tier: Mapped[str] = mapped_column(String(16))  # 1/2/3/4/class/special
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    org_unit_id: Mapped[int | None] = mapped_column(ForeignKey("org_units.id"), nullable=True)
    portal: Mapped[str] = mapped_column(String(16))  # principal/staff/admin
    permission_template: Mapped[str] = mapped_column(String(32), default="")
    data_scope: Mapped[str] = mapped_column(String(32), default="class")  # all/edu/logistics/class/summary/health/meal/public


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    note: Mapped[str | None] = mapped_column(String(128), nullable=True)
    import_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), nullable=True)
    parent_class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(16), default="staff")  # principal/staff/admin/parent
    status: Mapped[str] = mapped_column(String(16), default="active")
    staff: Mapped[Staff | None] = relationship()


class UserPosition(Base):
    __tablename__ = "user_positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"))
    semester_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scope_json: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[Position] = relationship()


# ---------- 学期、校历、班级 ----------
class Semester(Base):
    __tablename__ = "semesters"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")


class SemesterWeek(Base):
    __tablename__ = "semester_weeks"
    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    week_no: Mapped[int] = mapped_column(Integer)
    ranges_json: Mapped[list] = mapped_column(JSON)  # [["2026-09-28","2026-09-30"],["2026-10-08","2026-10-11"]]
    parity: Mapped[str] = mapped_column(String(8))   # single/double


class DutyRoster(Base):
    __tablename__ = "duty_rosters"
    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer)
    week_no: Mapped[int] = mapped_column(Integer)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))


class Klass(Base):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(16), unique=True)  # 大一
    grade: Mapped[str] = mapped_column(String(8))               # small/middle/big
    order: Mapped[int] = mapped_column(Integer, default=0)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_boys: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref_girls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template: Mapped[str] = mapped_column(String(16), default="small_middle")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ClassStaff(Base):
    __tablename__ = "class_staff"
    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    slot: Mapped[str] = mapped_column(String(16))   # teacher/care/vice_lead
    shift: Mapped[str | None] = mapped_column(String(16), nullable=True)  # mon_wed_fri/tue_thu
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    teaching_role: Mapped[str | None] = mapped_column(String(16), nullable=True)  # teaching/care
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/confirmed
    not_rotated_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    staff: Mapped[Staff] = relationship()


class Routine(Base):
    __tablename__ = "routines"
    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(32), default="all")
    start: Mapped[str] = mapped_column(String(5))
    end: Mapped[str] = mapped_column(String(5))
    segment: Mapped[str] = mapped_column(String(64))       # 原文环节
    segment_key: Mapped[str] = mapped_column(String(8))    # 入园/进餐/盥洗/午睡/户外/离园/教学
    source: Mapped[str] = mapped_column(String(32))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class SpecialCourse(Base):
    __tablename__ = "special_courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer)
    week_type: Mapped[str] = mapped_column(String(8))  # single/double
    weekday: Mapped[int] = mapped_column(Integer)      # 1..5
    start: Mapped[str] = mapped_column(String(5))
    end: Mapped[str] = mapped_column(String(5))
    course: Mapped[str] = mapped_column(String(16))
    class_name: Mapped[str] = mapped_column(String(16))
    teacher_label: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 足球教师 / 姓名 / 空=班级教师


class Child(Base):
    __tablename__ = "children"
    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    code: Mapped[str] = mapped_column(String(24), unique=True)
    name_encrypted: Mapped[str] = mapped_column(Text)
    gender: Mapped[str] = mapped_column(String(4))
    birth_month: Mapped[str | None] = mapped_column(String(8), nullable=True)
    parent_phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(8), default="在园")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    import_job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(String(512))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="validated")  # validated/committed/rolled_back
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(24))
    title: Mapped[str] = mapped_column(String(128))
    semester_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    target_position: Mapped[str] = mapped_column(String(32), default="管理员")
    status: Mapped[str] = mapped_column(String(16), default="open")


class ReviewDelegation(Base):
    __tablename__ = "review_delegations"
    id: Mapped[int] = mapped_column(primary_key=True)
    delegate_staff_id: Mapped[int] = mapped_column(Integer)
    categories: Mapped[list] = mapped_column(JSON)
    granted_by: Mapped[int] = mapped_column(Integer)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)


# ---------- 知识库 ----------
class KbDoc(Base):
    __tablename__ = "kb_docs"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))         # national/policy/experience/faq
    visibility: Mapped[str] = mapped_column(String(16))   # internal/public
    file_path: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(16), default="parsing")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class KbChunk(Base):
    __tablename__ = "kb_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("kb_docs.id", ondelete="CASCADE"))
    clause_no: Mapped[str] = mapped_column(String(64), default="")
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    doc: Mapped[KbDoc] = relationship()


# ---------- 巡查链 ----------
class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    semester_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    segment: Mapped[str] = mapped_column(String(8))
    on_duty_staff_ids: Mapped[list] = mapped_column(JSON, default=list)
    submitter_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_raw: Mapped[str] = mapped_column(Text, default="")
    text_redacted: Mapped[str] = mapped_column(Text, default="")
    media_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(16), default="running")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    klass: Mapped[Klass] = relationship()


class Media(Base):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(16), default="")
    owner_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(8))  # image/audio
    path_raw: Mapped[str] = mapped_column(String(512))
    path_redacted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    faces: Mapped[int] = mapped_column(Integer, default=0)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploader_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    chain: Mapped[str] = mapped_column(String(16))  # inspect/parent/council
    source_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="running")
    engine: Mapped[str] = mapped_column(String(16), default="llm")  # llm/offline
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    round: Mapped[int] = mapped_column(Integer, default=1)
    agent: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(16))  # state/think/statement/challenge/support/verdict/redteam/brief/route
    target_agent: Mapped[str | None] = mapped_column(String(24), nullable=True)
    finding_key: Mapped[str | None] = mapped_column(String(16), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    cited_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion: Mapped[str] = mapped_column(String(16), default="cheer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(16))
    item: Mapped[str] = mapped_column(Text)
    segment: Mapped[str] = mapped_column(String(8))
    category: Mapped[str] = mapped_column(String(8))
    severity: Mapped[str] = mapped_column(String(4))
    reason: Mapped[str] = mapped_column(Text, default="")
    cited_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    solo_judgement: Mapped[str] = mapped_column(String(16), default="valid")
    final_verdict: Mapped[str] = mapped_column(String(16), default="needs_review")
    verdict_reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    review_reason: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="open")  # open/reviewed/rectifying/closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    inspection: Mapped[Inspection] = relationship()


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    reviewer_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    via_delegation: Mapped[bool] = mapped_column(Boolean, default=False)
    decision: Mapped[str] = mapped_column(String(16))  # valid/invalid
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Appeal(Base):
    __tablename__ = "appeals"
    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"))
    staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Rectification(Base):
    __tablename__ = "rectifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    finding_ids: Mapped[list] = mapped_column(JSON)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(256))
    requirement: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(4), default="中")
    assignee_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_by_rule: Mapped[str] = mapped_column(String(64), default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft/issued/submitted/closed
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    evidence_media_ids: Mapped[list] = mapped_column(JSON, default=list)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16))  # review/rectification/acceptance/appeal/parent
    ref_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(256), default="")
    assignee_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(4), default="中")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open/done
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    extended_count: Mapped[int] = mapped_column(Integer, default=0)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class SlaPolicy(Base):
    __tablename__ = "sla_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(8), default="*")
    duration_minutes: Mapped[int] = mapped_column(Integer)
    remind_ratio: Mapped[float] = mapped_column(Float, default=0.5)
    escalation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    label: Mapped[str] = mapped_column(String(64), default="")


class SlaEvent(Base):
    __tablename__ = "sla_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(16))
    to_staff_ids: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(String(256), default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(Integer, index=True)
    channel: Mapped[str] = mapped_column(String(8), default="inbox")
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Invite(Base):
    __tablename__ = "invites"
    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    class_id: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------- 家园沟通 ----------
class ParentThread(Base):
    __tablename__ = "parent_threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ParentMessage(Base):
    __tablename__ = "parent_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("parent_threads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # parent/aibao/teacher/system
    content: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    route: Mapped[str | None] = mapped_column(String(16), nullable=True)  # auto/transfer/blocked
    routed_to_staff_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="done")  # pending/done
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------- 园务议事 ----------
class CouncilTopic(Base):
    __tablename__ = "council_topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brief_json: Mapped[dict] = mapped_column(JSON, default=dict)
    final_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# ---------- 合规与日志 ----------
class RedactionLog(Base):
    __tablename__ = "redaction_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(String(40))
    agent: Mapped[str] = mapped_column(String(24), default="")
    before_hash: Mapped[str] = mapped_column(String(64))
    before_preview: Mapped[str] = mapped_column(Text, default="")  # 仅管理员可看
    after_text: Mapped[str] = mapped_column(Text)
    faces: Mapped[int] = mapped_column(Integer, default=0)
    replacements_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent: Mapped[str] = mapped_column(String(24))
    model: Mapped[str] = mapped_column(String(48))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | float | int | bool] = mapped_column(JSON)


class Avatar(Base):
    __tablename__ = "avatars"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent: Mapped[str] = mapped_column(String(24))
    view: Mapped[str] = mapped_column(String(16))  # front/side/back/emotion 名
    image_path: Mapped[str] = mapped_column(String(512))
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_doc_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class BrandAsset(Base):
    __tablename__ = "brand_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # logo_header/logo_login/favicon/pdf_header
    path: Mapped[str] = mapped_column(String(512))
    source_path: Mapped[str] = mapped_column(String(512), default="")
    palette_json: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
