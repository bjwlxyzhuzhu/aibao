"""工单时限与超时升级（PRD 4.6）：工作时间计时、过半提醒、两级升级、全程留痕。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (ClassStaff, Notification, Position, SemesterWeek, SlaEvent, SlaPolicy, Staff, User, UserPosition,
                      WorkOrder)
from ..timeutil import add_work_minutes, now_local, work_minutes_between
from .calendar import current_semester_id

# 默认规则（管理员 A12 可改，改动只对新建工单生效）
DEFAULT_POLICIES = [
    ("review", "高", 120, 0.5, {"l1": ["值周负责人", "分管副园长"], "l1_after": 0}, "待复核 · 安全卫生类 2 工作小时"),
    ("review", "*", 630, 0.5, {"l1": ["值周负责人", "分管副园长"], "l1_after": 0}, "待复核 · 其他 1 个工作日"),
    ("rectification", "高", 240, 0.5, {"l1": ["班长", "副班长"], "l2": ["分管副园长", "园长"], "l2_after": 240}, "整改单 · 高 4 工作小时"),
    ("rectification", "中", 1260, 0.5, {"l1": ["班长", "副班长"], "l2": ["分管副园长", "园长"], "l2_after": 630}, "整改单 · 中 2 个工作日"),
    ("rectification", "低", 3150, 0.8, {"l1": ["班长", "副班长"], "l2": ["分管副园长"], "l2_after": 1260}, "整改单 · 低 5 个工作日"),
    ("acceptance", "*", 1260, 0.5, {"l1": ["值周负责人"]}, "整改回传待验收 2 个工作日"),
    ("appeal", "*", 1260, 0.5, {"l1": ["园长"]}, "教师申诉 2 个工作日"),
    ("parent", "*", 120, 0.5, {"l1": ["班长", "副班长"], "l2": ["办公室主任"], "l2_after": 300}, "家长转人工 2 工作小时"),
]


def seed_policies(db: Session) -> None:
    if db.scalar(select(SlaPolicy.id).limit(1)):
        return
    for t, sev, mins, ratio, esc, label in DEFAULT_POLICIES:
        db.add(SlaPolicy(type=t, severity=sev, duration_minutes=mins, remind_ratio=ratio, escalation_json=esc, label=label))


def holidays(db: Session) -> set[date]:
    """校历内未覆盖的工作日视为假期（如国庆 10.1–10.7）。"""
    covered: set[date] = set()
    lo, hi = None, None
    for w in db.scalars(select(SemesterWeek)):
        for a, b in w.ranges_json:
            da, dbb = date.fromisoformat(a), date.fromisoformat(b)
            lo = da if lo is None or da < lo else lo
            hi = dbb if hi is None or dbb > hi else hi
            d = da
            while d <= dbb:
                covered.add(d)
                d = date.fromordinal(d.toordinal() + 1)
    if lo is None:
        return set()
    out = set()
    d = lo
    while d <= hi:
        if d not in covered and d.weekday() < 5:
            out.add(d)
        d = date.fromordinal(d.toordinal() + 1)
    return out


def policy_for(db: Session, type_: str, severity: str) -> SlaPolicy | None:
    p = db.scalar(select(SlaPolicy).where(SlaPolicy.type == type_, SlaPolicy.severity == severity))
    return p or db.scalar(select(SlaPolicy).where(SlaPolicy.type == type_, SlaPolicy.severity == "*"))


def notify(db: Session, staff_ids: list[int | None], title: str, body: str = "", link: str = "") -> None:
    for sid in {s for s in staff_ids if s}:
        db.add(Notification(staff_id=sid, title=title, body=body, link=link))


def principal_staff_ids(db: Session) -> list[int]:
    ids = [u.staff_id for u in db.scalars(select(User).where(User.role == "principal")) if u.staff_id]
    pos = db.scalar(select(Position).where(Position.name == "园长"))
    if pos:
        ids += [up.staff_id for up in db.scalars(select(UserPosition).where(UserPosition.position_id == pos.id))]
    return list(set(ids))


def create_work_order(db: Session, type_: str, ref_id: int, title: str, assignee: int | None, severity: str = "中",
                      class_id: int | None = None, is_demo: bool = False, start: datetime | None = None) -> WorkOrder:
    start = start or now_local()
    p = policy_for(db, type_, severity if type_ != "review" else ("高" if severity == "高" else "*"))
    mins = p.duration_minutes if p else 630
    wo = WorkOrder(type=type_, ref_id=ref_id, title=title, assignee_staff_id=assignee, severity=severity, class_id=class_id,
                   created_at=start, due_at=add_work_minutes(start, mins, holidays(db)), is_demo=is_demo)
    db.add(wo)
    db.flush()
    db.add(SlaEvent(work_order_id=wo.id, event="created", to_staff_ids=[assignee] if assignee else [], at=start))
    notify(db, [assignee], f"新工单：{title}", f"截止 {wo.due_at:%m-%d %H:%M}", link=f"/work-orders/{wo.id}")
    return wo


def close_work_orders(db: Session, type_: str, ref_id: int) -> None:
    for wo in db.scalars(select(WorkOrder).where(WorkOrder.type == type_, WorkOrder.ref_id == ref_id, WorkOrder.status == "open")):
        wo.status = "done"
        wo.done_at = now_local()
        db.add(SlaEvent(work_order_id=wo.id, event="done", at=wo.done_at))


def _class_people(db: Session, class_id: int | None, slot_filter) -> list[int]:
    if not class_id:
        return []
    sid = current_semester_id(db)
    return [c.staff_id for c in db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid, ClassStaff.class_id == class_id))
            if slot_filter(c)]


def tick(db: Session) -> int:
    """扫描未完成工单：过半提醒 → 超时一级升级 → 再超时二级升级。夜间不推送（次日 7:30 统一提醒）。"""
    n = now_local()
    if not (7 * 60 + 30 <= n.hour * 60 + n.minute <= 18 * 60):
        return 0
    hol = holidays(db)
    changed = 0
    for wo in db.scalars(select(WorkOrder).where(WorkOrder.status == "open")):
        p = policy_for(db, wo.type, wo.severity)
        total = max(1, work_minutes_between(wo.created_at, wo.due_at, hol))
        used = work_minutes_between(wo.created_at, n, hol)
        if not wo.reminded and used >= total * (p.remind_ratio if p else 0.5) and n < wo.due_at:
            wo.reminded = True
            db.add(SlaEvent(work_order_id=wo.id, event="reminded", to_staff_ids=[wo.assignee_staff_id] if wo.assignee_staff_id else [], at=n))
            notify(db, [wo.assignee_staff_id], f"工单时限已过半：{wo.title}", f"截止 {wo.due_at:%m-%d %H:%M}")
            changed += 1
        if n >= wo.due_at and wo.escalation_level == 0:
            to = [wo.assignee_staff_id] + _class_people(db, wo.class_id, lambda c: c.is_lead or c.slot == "vice_lead")
            wo.escalation_level = 1
            db.add(SlaEvent(work_order_id=wo.id, event="escalated", to_staff_ids=[t for t in to if t], note="第一级升级", at=n))
            notify(db, to, f"工单超时（一级升级）：{wo.title}")
            changed += 1
        esc = (p.escalation_json if p else {}) or {}
        if wo.escalation_level == 1 and esc.get("l2") and n >= add_work_minutes(wo.due_at, esc.get("l2_after", 240), hol):
            to = principal_staff_ids(db)
            wo.escalation_level = 2
            db.add(SlaEvent(work_order_id=wo.id, event="escalated", to_staff_ids=to, note="第二级升级：分管副园长 + 园长，驾驶舱标红", at=n))
            notify(db, to, f"工单超时（二级升级）：{wo.title}")
            changed += 1
    return changed


def suggest_assignee(db: Session, class_id: int | None, category: str, segment: str, item: str = "") -> tuple[int | None, str]:
    """责任人按岗位自动建议（PRD 4.2 第 7 步）；园长可改。"""
    def holder(pos_name: str) -> int | None:
        pos = db.scalar(select(Position).where(Position.name == pos_name))
        if not pos:
            return None
        up = db.scalar(select(UserPosition).where(UserPosition.position_id == pos.id))
        return up.staff_id if up else None

    if category == "设施" or any(k in item for k in ("器械", "插座", "电线", "门窗")):
        s = holder("后勤处主任")
        if s:
            return s, "设施安全 → 后勤处主任"
    if category == "膳食":
        s = holder("伙管室")
        if s:
            return s, "膳食 → 伙管室"
    if category == "卫生" and "消毒" in item:
        s = holder("保健室")
        if s:
            return s, "卫生消毒 → 保健室"
    sid = current_semester_id(db)
    rows = list(db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid, ClassStaff.class_id == class_id))) if class_id else []
    if segment in ("进餐", "午睡", "盥洗") or category == "生活照料":
        care = [r for r in rows if r.slot == "care"] or [r for r in rows if r.teaching_role == "care"]
        if care:
            return care[0].staff_id, f"{segment}环节 → 当期保育岗"
    lead = [r for r in rows if r.is_lead] or [r for r in rows if r.teaching_role == "teaching"] or [r for r in rows if r.slot == "teacher"]
    if lead:
        return lead[0].staff_id, "班级问题 → 当期班长"
    return None, "未匹配到岗位，请园长指定"


def staff_name(db: Session, sid: int | None) -> str:
    if not sid:
        return "—"
    s = db.get(Staff, sid)
    return s.name if s else "—"
