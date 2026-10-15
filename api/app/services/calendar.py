"""校历周次、单双周判定（按校历，不按日期推算）、作息环节与在岗教师推算。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ClassStaff, DutyRoster, Klass, Routine, Semester, SemesterWeek, SpecialCourse, Staff, UserPosition, Position
from ..timeutil import WEEKDAY_CN, hm, now_local, today

SEGMENTS = ["入园", "进餐", "盥洗", "教学", "户外", "午睡", "离园"]


def segment_key(text: str, start: str = "") -> str:
    t = text
    if any(k in t for k in ("午睡", "起床", "睡前")):
        return "午睡"
    if "离园" in t:
        return "离园"
    if any(k in t for k in ("早餐", "午餐", "点", "餐")):
        return "进餐"
    if any(k in t for k in ("晨练", "户外", "特色", "体能", "足球", "篮球", "体技", "搭建", "大型玩具")):
        return "户外"
    if "盥洗" in t:
        return "盥洗"
    if start and hm(start) < hm("8:00"):
        return "入园"
    return "教学"


def current_semester(db: Session, d: date | None = None) -> Semester | None:
    d = d or today()
    s = db.scalar(select(Semester).where(Semester.start_date <= d, Semester.end_date >= d))
    return s or db.scalar(select(Semester).where(Semester.status == "active").order_by(Semester.start_date.desc()))


def current_semester_id(db: Session) -> int | None:
    s = current_semester(db)
    return s.id if s else None


def week_of(db: Session, d: date | None = None) -> SemesterWeek | None:
    d = d or today()
    s = current_semester(db, d)
    if not s:
        return None
    for w in db.scalars(select(SemesterWeek).where(SemesterWeek.semester_id == s.id)):
        for a, b in w.ranges_json:
            if date.fromisoformat(a) <= d <= date.fromisoformat(b):
                return w
    return None


def calendar_today(db: Session, d: date | None = None) -> dict:
    d = d or today()
    s = current_semester(db, d)
    w = week_of(db, d)
    duty = None
    if w and s:
        r = db.scalar(select(DutyRoster).where(DutyRoster.semester_id == s.id, DutyRoster.week_no == w.week_no))
        if r:
            st = db.get(Staff, r.staff_id)
            duty = st.name if st else None
    return {
        "date": d.isoformat(),
        "weekday": WEEKDAY_CN[d.weekday()],
        "semester": s.name if s else None,
        "week_no": w.week_no if w else None,
        "parity": w.parity if w else None,
        "parity_cn": {"single": "单周", "double": "双周"}.get(w.parity if w else "", None),
        "is_holiday": w is None or d.weekday() >= 5,
        "duty": duty,
    }


def _class_staff(db: Session, sid: int, class_id: int) -> list[ClassStaff]:
    return list(db.scalars(select(ClassStaff).where(ClassStaff.semester_id == sid, ClassStaff.class_id == class_id)))


def staff_by_position(db: Session, label: str) -> Staff | None:
    pos = db.scalar(select(Position).where(Position.name == label))
    if pos:
        up = db.scalar(select(UserPosition).where(UserPosition.position_id == pos.id))
        if up:
            return db.get(Staff, up.staff_id)
    return db.scalar(select(Staff).where(Staff.name == label))


def schedule_now(db: Session, class_id: int, at: datetime | None = None) -> dict:
    at = at or now_local()
    klass = db.get(Klass, class_id)
    s = current_semester(db, at.date())
    w = week_of(db, at.date())
    minute = at.hour * 60 + at.minute
    weekday = at.weekday() + 1
    result = {"class_id": class_id, "class_name": klass.name if klass else "", "segment": "教学", "segment_text": "",
              "start": None, "end": None, "confirmed": True, "course": None, "on_duty": [], "week_no": w.week_no if w else None,
              "parity": w.parity if w else None, "no_push": False}
    if not s or not klass:
        return result
    routine = None
    for r in db.scalars(select(Routine).where(Routine.semester_id == s.id).order_by(Routine.start)):
        if hm(r.start) <= minute < hm(r.end):
            routine = r
            break
    if routine is None:
        result["segment"] = "入园" if minute < hm("8:00") else "离园"
        result["segment_text"] = "非作息时段"
    else:
        result.update(segment=routine.segment_key, segment_text=routine.segment, start=routine.start, end=routine.end,
                      confirmed=routine.confirmed)
    course = None
    if w and weekday <= 5:
        for c in db.scalars(select(SpecialCourse).where(SpecialCourse.semester_id == s.id, SpecialCourse.week_type == w.parity,
                                                         SpecialCourse.weekday == weekday)):
            if hm(c.start) <= minute < hm(c.end) and c.class_name in (klass.name, "全园"):
                course = c
                break
    if not course and "晨练" in result["segment_text"]:
        result.update(segment="入园", segment_text="入园（本班今日无晨练）")
    staff_rows = _class_staff(db, s.id, class_id)
    on_duty: list[dict] = []
    if course:
        result["course"] = course.course
        result["segment"] = "教学" if course.course in ("集体教育", "教研") else "户外"
        result["segment_text"] = f"{course.course}（{'单' if w.parity == 'single' else '双'}周课表）"
        if course.course == "教研":
            result["no_push"] = True
        if course.teacher_label:
            st = staff_by_position(db, course.teacher_label)
            on_duty.append({"id": st.id if st else None, "name": st.name if st else course.teacher_label,
                            "role": course.teacher_label})
    if not on_duty:
        early = minute < hm("8:30")
        shift = "mon_wed_fri" if weekday in (1, 3, 5) else "tue_thu"
        for cs in staff_rows:
            if cs.slot == "teacher" and (not early or cs.shift == shift):
                role = {"teaching": "教学教师", "care": "保育角色教师"}.get(cs.teaching_role or "", "班级教师")
                on_duty.append({"id": cs.staff_id, "name": cs.staff.name, "role": role + ("（早班）" if early else "")})
        if result["segment"] in ("进餐", "午睡", "盥洗"):
            for cs in staff_rows:
                if cs.slot == "care":
                    on_duty.append({"id": cs.staff_id, "name": cs.staff.name, "role": "保育员"})
    result["on_duty"] = on_duty
    return result
