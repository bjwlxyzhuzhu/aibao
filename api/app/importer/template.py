"""导入中心：解析《管理员导入模板》→ 校验报告（红/黄/绿）→ 确认生效 → 版本快照可回滚。"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime
from pathlib import Path

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import (Child, ClassStaff, DutyRoster, ImportJob, Klass, Position, Routine, Semester, SemesterWeek,
                      SpecialCourse, Staff, User, UserPosition)
from ..security import encrypt, hash_pw
from ..services.calendar import segment_key

POSITIONS = [
    # 名称, 层级, 端, 数据范围
    ("园长", "1", "principal", "all"), ("教学副园长", "2", "principal", "edu"), ("后勤副园长", "2", "principal", "logistics"),
    ("办公室主任", "3", "staff", "public"), ("保教办主任", "3", "staff", "all"), ("后勤处主任", "3", "staff", "logistics"),
    ("教师发展处主任", "3", "staff", "summary"), ("财务室", "4", "staff", "none"), ("保健室", "4", "staff", "health"),
    ("伙管室", "4", "staff", "meal"), ("班级教师", "class", "staff", "class"), ("保育员", "class", "staff", "class"),
    ("班长", "class", "staff", "class"), ("副班长", "class", "staff", "class"), ("足球教师", "special", "staff", "course"),
    ("篮球教师", "special", "staff", "course"), ("大班科发教师", "special", "staff", "course"),
    ("中班科发教师", "special", "staff", "course"), ("管理员", "admin", "admin", "config"),
]
GRADE = {"大班": "big", "中班": "middle", "小班": "small"}
WEEKDAY = {"周一": 1, "周二": 2, "周三": 3, "周四": 4, "周五": 5}
FORBIDDEN_CHILD_FIELDS = ("身份证", "住址", "地址", "健康", "病", "照片", "过敏")


def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _sheet(wb, prefix: str):
    for ws in wb.worksheets:
        if ws.title.startswith(prefix):
            return ws
    return None


def _rows(ws, skip_example=True):
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []
    header = [_s(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        vals = [_s(v) if not isinstance(v, (datetime, date)) else v for v in r]
        if not any(vals):
            continue
        first = _s(r[0])
        if skip_example and (first.startswith("示例") or first.startswith("来源") or first.startswith("第 3 行")
                             or first.startswith('"') or first.startswith("只填") or first.startswith("“")):
            continue
        out.append(dict(zip(header, vals)))
    return header, out


def _cls(name: str) -> str:
    return name.replace("班", "").strip()


def parse(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    out: dict = {}
    for key, prefix in [("staff", "教职工名单"), ("assign", "班级任职"), ("children", "幼儿名册"), ("calendar", "校历周次"),
                        ("routine", "作息时段"), ("course", "特色课表")]:
        ws = _sheet(wb, prefix)
        if ws is not None:
            out[key + "_header"], out[key] = _rows(ws)
    return out


# ---------------- 校验 ----------------
def validate(db: Session, kind: str, data: dict) -> dict:
    red, yellow, green = [], [], []
    preview: dict = {}
    staff_rows = data.get("staff", [])
    names = [r.get("姓名", "") for r in staff_rows]
    name_set = set(names) | {s.name for s in db.scalars(select(Staff))}
    pos_names = {p[0] for p in POSITIONS}

    if kind in ("staff", "all"):
        seen, phones = set(), {}
        for i, r in enumerate(staff_rows, start=3):
            n = r.get("姓名", "")
            if n.startswith("第") or not n:
                continue
            if n in seen:
                red.append(f"教职工名单第 {i} 行：重名「{n}」，请加区分（如 王小雨A）")
            seen.add(n)
            main = r.get("主岗位", "")
            extra = [x for x in re.split(r"[、,，]", r.get("兼任岗位（可空，多个用、分隔）", "") or "") if x]
            if not main:
                yellow.append(f"教职工名单第 {i} 行：「{n}」主岗位为空（{r.get('备注', '')}），导入后暂按兼任岗位授权")
            for p in [main] + extra:
                if p and p not in pos_names:
                    red.append(f"教职工名单第 {i} 行：岗位「{p}」不在岗位清单")
            ph = r.get("手机号", "")
            if ph:
                if not re.fullmatch(r"1[3-9]\d{9}", ph):
                    red.append(f"教职工名单第 {i} 行：手机号格式不正确")
                if ph in phones:
                    red.append(f"教职工名单第 {i} 行：手机号与「{phones[ph]}」重复")
                phones[ph] = n
        no_phone = sum(1 for r in staff_rows if r.get("姓名") and not r.get("手机号"))
        if no_phone:
            yellow.append(f"{no_phone} 人未填手机号：将以姓名作为登录账号，初始密码随机生成")
        preview["staff_count"] = len(seen)
        # 班级任职
        assigned: dict[str, str] = {}
        classes = []
        for r in data.get("assign", []):
            c = _cls(r.get("班级", ""))
            if not c or r.get("年级") in ("合计", "") and not r.get("一三五早班"):
                continue
            classes.append(c)
            t1, t2 = r.get("一三五早班", ""), r.get("二四早班", "")
            cares = [x for x in (r.get("保育岗 1", ""), r.get("保育岗 2", "")) if x]
            if not t1 or not t2:
                red.append(f"{c}班：两名班级教师未配齐")
            need_care = 2 if r.get("年级") == "大班" else 1
            if len(cares) < need_care:
                yellow.append(f"{c}班：保育岗 {len(cares)} 人，模板要求 {need_care} 人")
            if not r.get("副班长"):
                yellow.append(f"{c}班：暂无副班长")
            for person in [t1, t2] + cares:
                if not person:
                    continue
                if person not in name_set:
                    red.append(f"{c}班：「{person}」不在教职工名单")
                if person in assigned and assigned[person] != c:
                    red.append(f"「{person}」同时在 {assigned[person]}班 和 {c}班 担任班级岗位")
                assigned[person] = c
        missing_roles = sum(1 for r in data.get("assign", []) if r.get("一三五早班") and not r.get("教学教师（本学期）"))
        if missing_roles:
            yellow.append(f"{missing_roles} 个班未填本学期教学 / 保育角色：系统暂按「班长 = 教学教师」生成草案，提交园长确认")
        preview["classes"] = classes
        if len(classes) != 16:
            yellow.append(f"共识别 {len(classes)} 个班（PRD 预期 16 个）")
    if kind in ("calendar", "all"):
        weeks = []
        prev_end = None
        for r in data.get("calendar", []):
            try:
                no = int(r.get("周次"))
            except (TypeError, ValueError):
                continue
            a, b = r.get("起始日期"), r.get("结束日期")
            if not isinstance(a, (date, datetime)) or not isinstance(b, (date, datetime)):
                red.append(f"第 {no} 周：日期缺失或格式错误")
                continue
            ranges = [[a.date().isoformat() if isinstance(a, datetime) else a.isoformat(),
                       b.date().isoformat() if isinstance(b, datetime) else b.isoformat()]]
            a2, b2 = r.get("第二段起始"), r.get("第二段结束")
            if isinstance(a2, (date, datetime)) and isinstance(b2, (date, datetime)):
                ranges.append([a2.date().isoformat(), b2.date().isoformat()])
            if weeks and no != weeks[-1]["week_no"] + 1:
                red.append(f"周次不连续：第 {weeks[-1]['week_no']} 周之后是第 {no} 周")
            if prev_end and ranges[0][0] <= prev_end:
                red.append(f"第 {no} 周与上一周日期重叠")
            prev_end = ranges[-1][1]
            duty = r.get("值周负责人", "")
            if duty and duty not in name_set:
                yellow.append(f"第 {no} 周值周负责人「{duty}」不在教职工名单")
            weeks.append({"week_no": no, "ranges": ranges, "parity": "single" if no % 2 else "double", "duty": duty})
        if weeks and not any(w["duty"] for w in weeks):
            yellow.append("值周负责人列为空：本周巡查提醒和周报暂不抄送值周负责人")
        preview["weeks"] = weeks
        if not weeks:
            red.append("未识别到校历周次")
    if kind in ("routine", "all"):
        items = []
        for r in data.get("routine", []):
            s, e = r.get("开始", ""), r.get("结束", "")
            if not re.fullmatch(r"\d{1,2}:\d{2}", s or "") or not re.fullmatch(r"\d{1,2}:\d{2}", e or ""):
                continue
            conf = r.get("是否已确认（是/否）", "") == "是"
            items.append({"start": s, "end": e, "segment": r.get("环节", ""), "grade": r.get("适用年级", "全园"),
                          "source": r.get("来源", ""), "confirmed": conf})
            if not conf:
                yellow.append(f"作息 {s}–{e}「{r.get('环节', '')}」未确认：家长端不会用它回答作息问题")
        items.sort(key=lambda x: tuple(map(int, x["start"].split(":"))))
        for a, b in zip(items, items[1:]):
            if tuple(map(int, b["start"].split(":"))) < tuple(map(int, a["end"].split(":"))):
                red.append(f"作息时段重叠：{a['start']}–{a['end']} 与 {b['start']}–{b['end']}")
        preview["routines"] = items
    if kind in ("course", "all"):
        known_classes = {k.name for k in db.scalars(select(Klass))} | {_cls(r.get("班级", "")) for r in data.get("assign", [])}
        slots = set()
        cells = []
        for r in data.get("course", []):
            wt = {"单周": "single", "双周": "double"}.get(r.get("单双周", ""))
            wd = WEEKDAY.get(r.get("星期", ""))
            if not wt or not wd:
                continue
            c = _cls(r.get("班级", ""))
            if c != "全园" and c not in known_classes:
                red.append(f"特色课表：班级「{c}」不存在")
            key = (wt, wd, r.get("开始"), c)
            if key in slots and c != "全园":
                red.append(f"特色课表：{r.get('单双周')}{r.get('星期')} {r.get('开始')} {c}班 同一时段两门课")
            slots.add(key)
            t = r.get("授课教师（岗位或姓名，空=班级教师）", "")
            if t and t not in pos_names and t not in name_set:
                yellow.append(f"特色课表：授课教师「{t}」不在名单或岗位清单")
            cells.append({"week_type": wt, "weekday": wd, "start": r.get("开始"), "end": r.get("结束"), "course": r.get("课程"),
                          "class_name": c, "teacher": t})
        teacher_labels = {c["teacher"] for c in cells if c["teacher"]}
        unfilled = [t for t in teacher_labels if t in pos_names and not _position_holder(db, t)]
        if unfilled:
            yellow.append(f"岗位「{'、'.join(sorted(unfilled))}」尚无人任职：在岗推算暂显示岗位名称")
        preview["courses"] = cells
        if not cells:
            red.append("未识别到特色课表")
    if kind in ("children",):
        header = data.get("children_header", [])
        bad = [h for h in header if any(k in h for k in FORBIDDEN_CHILD_FIELDS)]
        if bad:
            red.append(f"幼儿名册包含不允许导入的字段：{'、'.join(bad)}（不导入照片、身份证号、住址和健康信息）")
        known = {k.name for k in db.scalars(select(Klass))}
        seen = set()
        kids = []
        for i, r in enumerate(data.get("children", []), start=3):
            c, n, g = _cls(r.get("班级", "")), r.get("姓名", ""), r.get("性别（男/女）", "")
            if not n:
                continue
            if c not in known:
                red.append(f"幼儿名册第 {i} 行：班级「{c}」不存在")
            if g not in ("男", "女"):
                red.append(f"幼儿名册第 {i} 行：性别缺失")
            if (c, n) in seen:
                red.append(f"幼儿名册第 {i} 行：同班重名，请加区分")
            seen.add((c, n))
            kids.append({"class": c, "gender": g})
        preview["children_count"] = len(kids)
        if not kids:
            yellow.append("幼儿名册为空：模板中尚未填写幼儿，可稍后再导入")
    if not red:
        green.append("校验通过，可以确认生效")
    return {"red": red, "yellow": yellow, "green": green, "preview": preview, "ok": not red}


def _position_holder(db: Session, pos_name: str):
    pos = db.scalar(select(Position).where(Position.name == pos_name))
    if not pos:
        return None
    return db.scalar(select(UserPosition).where(UserPosition.position_id == pos.id))


# ---------------- 快照与回滚 ----------------
SNAP_TABLES = {
    "staff": [Staff, User, UserPosition, ClassStaff, Klass],
    "calendar": [Semester, SemesterWeek, DutyRoster],
    "routine": [Routine],
    "course": [SpecialCourse],
    "children": [Child],
}


def _row_dict(obj) -> dict:
    out = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        if isinstance(v, (date, datetime)):
            v = {"__dt": v.isoformat(), "__t": "dt" if isinstance(v, datetime) else "d"}
        out[c.name] = v
    return out


def _from_dict(model, d: dict):
    kw = {}
    for k, v in d.items():
        if isinstance(v, dict) and "__dt" in v:
            v = datetime.fromisoformat(v["__dt"]) if v["__t"] == "dt" else date.fromisoformat(v["__dt"])
        kw[k] = v
    return model(**kw)


def snapshot(db: Session, kind: str) -> dict:
    kinds = ["staff", "calendar", "routine", "course"] if kind == "all" else [kind]
    snap = {}
    for k in kinds:
        for m in SNAP_TABLES.get(k, []):
            snap[m.__tablename__] = [_row_dict(o) for o in db.scalars(select(m))]
    return snap


def restore(db: Session, snap: dict) -> None:
    order = [ClassStaff, UserPosition, User, Child, Staff, Klass, DutyRoster, SemesterWeek, Semester, Routine, SpecialCourse]
    present = [m for m in order if m.__tablename__ in snap]
    for m in present:
        db.query(m).delete()
    db.flush()
    for m in reversed(present):
        for d in snap[m.__tablename__]:
            db.add(_from_dict(m, d))
    db.flush()


# ---------------- 写入 ----------------
def ensure_positions(db: Session) -> dict[str, Position]:
    out = {p.name: p for p in db.scalars(select(Position))}
    for name, tier, portal, scope in POSITIONS:
        if name not in out:
            p = Position(name=name, portal=portal, permission_template=tier, data_scope=scope)
            db.add(p)
            out[name] = p
    db.flush()
    return out


def _semester(db: Session, weeks: list[dict] | None = None) -> Semester:
    s = db.scalar(select(Semester).where(Semester.name == "2026秋"))
    if not s:
        s = Semester(name="2026秋", start_date=date(2026, 9, 1), end_date=date(2027, 1, 24), status="active")
        db.add(s)
        db.flush()
    if weeks:
        s.start_date = date.fromisoformat(weeks[0]["ranges"][0][0])
        s.end_date = date.fromisoformat(weeks[-1]["ranges"][-1][1])
    return s


def commit(db: Session, job: ImportJob, data: dict, report: dict) -> dict:
    kind = job.kind
    job.report_json = {**report, "snapshot": snapshot(db, kind)}
    result: dict = {}
    pos = ensure_positions(db)
    if kind in ("staff", "all"):
        result.update(_commit_staff(db, job, data, pos))
    if kind in ("calendar", "all"):
        result.update(_commit_calendar(db, report["preview"]["weeks"]))
    if kind in ("routine", "all"):
        sem = _semester(db)
        db.query(Routine).filter(Routine.semester_id == sem.id).delete()
        for r in report["preview"]["routines"]:
            db.add(Routine(semester_id=sem.id, grade=r["grade"], start=r["start"], end=r["end"], segment=r["segment"],
                           segment_key=segment_key(r["segment"], r["start"]), source=r["source"], confirmed=r["confirmed"]))
        result["routines"] = len(report["preview"]["routines"])
    if kind in ("course", "all"):
        sem = _semester(db)
        db.query(SpecialCourse).filter(SpecialCourse.semester_id == sem.id).delete()
        for c in report["preview"]["courses"]:
            db.add(SpecialCourse(semester_id=sem.id, week_type=c["week_type"], weekday=c["weekday"], start=c["start"],
                                 end=c["end"], course=c["course"], class_name=c["class_name"], teacher_label=c["teacher"] or None))
        result["courses"] = len(report["preview"]["courses"])
    if kind == "children":
        result.update(_commit_children(db, job, data))
    job.status = "committed"
    job.report_json = {**job.report_json, "result": result}
    db.flush()
    return result


def _commit_staff(db: Session, job: ImportJob, data: dict, pos: dict[str, Position]) -> dict:
    sem = _semester(db)
    created, updated = 0, 0
    passwords = []
    by_name = {s.name: s for s in db.scalars(select(Staff))}
    for r in data.get("staff", []):
        n = r.get("姓名", "")
        if not n or n.startswith("第"):
            continue
        st = by_name.get(n)
        if st and (not r.get("手机号") or st.phone in (None, "", r.get("手机号"))):
            st.phone = r.get("手机号") or st.phone
            st.note = r.get("备注") or st.note
            updated += 1
        else:
            st = Staff(name=n, phone=r.get("手机号") or None, note=r.get("备注") or None, import_job_id=job.id)
            db.add(st)
            db.flush()
            by_name[n] = st
            created += 1
        login = r.get("手机号") or n
        u = db.scalar(select(User).where(User.staff_id == st.id))
        roles = [r.get("主岗位", "")] + [x for x in re.split(r"[、,，]", r.get("兼任岗位（可空，多个用、分隔）", "") or "") if x]
        role = "principal" if any(x in ("园长", "教学副园长", "后勤副园长") for x in roles) else "staff"
        if not u:
            pw = config.DEMO_PASSWORD if config.DEMO_MODE else secrets.token_urlsafe(6)
            if db.scalar(select(User).where(User.login == login)):
                login = f"{login}{st.id}"
            db.add(User(staff_id=st.id, login=login, password_hash=hash_pw(pw), must_change_password=not config.DEMO_MODE, role=role))
            passwords.append({"name": n, "login": login, "initial_password": pw})
        # 长期岗位（非班级岗位）
        db.query(UserPosition).filter(UserPosition.staff_id == st.id, UserPosition.semester_id.is_(None)).delete()
        for p in roles:
            if p and p in pos and p not in ("班级教师", "保育员", "副班长", "班长"):
                db.add(UserPosition(staff_id=st.id, position_id=pos[p].id))
    db.flush()
    # 班级与任职（本学期）
    db.query(ClassStaff).filter(ClassStaff.semester_id == sem.id).delete()
    db.query(UserPosition).filter(UserPosition.semester_id == sem.id).delete()
    order = 0
    for r in data.get("assign", []):
        c = _cls(r.get("班级", ""))
        g = GRADE.get(r.get("年级", ""))
        if not c or not g:
            continue
        order += 1
        k = db.scalar(select(Klass).where(Klass.name == c))
        if not k:
            k = Klass(name=c, grade=g)
            db.add(k)
        k.order = {"big": 0, "middle": 100, "small": 200}[g] + order
        k.grade = g
        k.template = "big" if g == "big" else "small_middle"
        k.ref_count = int(r["幼儿人数（参考）"]) if str(r.get("幼儿人数（参考）", "")).isdigit() else None
        k.ref_boys = int(r["男"]) if str(r.get("男", "")).isdigit() else None
        k.ref_girls = int(r["女"]) if str(r.get("女", "")).isdigit() else None
        db.flush()
        lead = r.get("班长（表中 ※）", "")
        teach = r.get("教学教师（本学期）", "")
        care_role = r.get("保育角色教师（本学期）", "")

        def add(name, slot, shift=None, role=None):
            st = by_name.get(name)
            if not st:
                return
            db.add(ClassStaff(semester_id=sem.id, class_id=k.id, slot=slot, shift=shift, is_lead=(name == lead and slot == "teacher"),
                              teaching_role=role, staff_id=st.id, status="draft"))
            pname = {"teacher": "班级教师", "care": "保育员", "vice_lead": "副班长"}[slot]
            db.add(UserPosition(staff_id=st.id, position_id=pos[pname].id, semester_id=sem.id, scope_json={"class_id": k.id}))
            if slot == "teacher" and name == lead:
                db.add(UserPosition(staff_id=st.id, position_id=pos["班长"].id, semester_id=sem.id, scope_json={"class_id": k.id}))

        for name, shift in ((r.get("一三五早班", ""), "mon_wed_fri"), (r.get("二四早班", ""), "tue_thu")):
            if not name:
                continue
            if teach or care_role:
                role = "teaching" if name == teach else "care" if name == care_role else None
            else:
                role = "teaching" if name == lead else "care"
            add(name, "teacher", shift, role)
        for col in ("保育岗 1", "保育岗 2"):
            if r.get(col):
                add(r[col], "care")
        if r.get("副班长"):
            add(r["副班长"], "vice_lead")
    db.flush()
    pw_file = config.DATA_DIR / f"initial_passwords_job{job.id}.csv"
    if passwords:
        pw_file.write_text("姓名,登录账号,初始密码\n" + "\n".join(f"{p['name']},{p['login']},{p['initial_password']}" for p in passwords),
                           encoding="utf-8-sig")
    return {"staff_created": created, "staff_updated": updated, "classes": order, "accounts_created": len(passwords),
            "password_file": pw_file.name if passwords else None}


def _commit_calendar(db: Session, weeks: list[dict]) -> dict:
    sem = _semester(db, weeks)
    db.query(SemesterWeek).filter(SemesterWeek.semester_id == sem.id).delete()
    db.query(DutyRoster).filter(DutyRoster.semester_id == sem.id).delete()
    by_name = {s.name: s for s in db.scalars(select(Staff))}
    for w in weeks:
        db.add(SemesterWeek(semester_id=sem.id, week_no=w["week_no"], ranges_json=w["ranges"], parity=w["parity"]))
        if w["duty"] and w["duty"] in by_name:
            db.add(DutyRoster(semester_id=sem.id, week_no=w["week_no"], staff_id=by_name[w["duty"]].id))
    return {"weeks": len(weeks)}


def _commit_children(db: Session, job: ImportJob, data: dict) -> dict:
    classes = {k.name: k for k in db.scalars(select(Klass))}
    n = 0
    for r in data.get("children", []):
        c, name = _cls(r.get("班级", "")), r.get("姓名", "")
        if not name or c not in classes:
            continue
        k = classes[c]
        seq = db.query(Child).filter(Child.class_id == k.id).count() + 1
        db.add(Child(class_id=k.id, code=f"{c}班-{seq:02d}", name_encrypted=encrypt(name), gender=r.get("性别（男/女）", ""),
                     birth_month=_s(r.get("出生年月（可空）")) or None,
                     parent_phone_encrypted=encrypt(_s(r.get("家长手机号（可空，用于家长端绑定）")) or None), import_job_id=job.id))
        n += 1
    return {"children": n}
