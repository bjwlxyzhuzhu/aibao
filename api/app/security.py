"""鉴权：账号密码 + JWT；岗位 + 数据范围决定可见内容；幼儿姓名加密存储。"""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import JWT_SECRET, env
from .db import get_db
from .models import ClassStaff, Klass, Staff, User, UserPosition
from .timeutil import now_local

_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256((env("CHILD_KEY") or JWT_SECRET).encode()).digest()))


def encrypt(s: str | None) -> str | None:
    return _fernet.encrypt(s.encode()).decode() if s else None


def decrypt(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return _fernet.decrypt(s.encode()).decode()
    except Exception:
        return None


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt(rounds=10)).decode()


def check_pw(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    payload = {"sub": str(user.id), "role": user.role, "exp": now_local() + timedelta(days=7) - timedelta(hours=8)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# 岗位 → 数据范围类别（巡查类别过滤用）
EDU_CATS = {"保教", "教学", "生活照料"}
LOGI_CATS = {"安全", "卫生", "膳食", "设施", "健康"}


@dataclass
class Principal:
    user: User
    staff: Staff | None
    role: str
    positions: list[str] = field(default_factory=list)
    class_ids: list[int] = field(default_factory=list)       # 当期任职班级
    vice_class_ids: list[int] = field(default_factory=list)  # 副班长包班
    scope: str = "class"  # all/edu/logistics/class/summary

    @property
    def name(self) -> str:
        if self.staff:
            return self.staff.name
        return {"principal": "园长", "admin": "管理员", "parent": "家长"}.get(self.role, self.user.login)

    def can_see_class(self, class_id: int | None) -> bool:
        if self.scope in ("all", "edu", "logistics", "summary"):
            return True
        return class_id in self.class_ids or class_id in self.vice_class_ids

    def category_ok(self, cat: str) -> bool:
        if self.scope == "edu":
            return cat in EDU_CATS
        if self.scope == "logistics":
            return cat in LOGI_CATS
        return True


SCOPE_BY_POSITION = {
    "园长": "all", "教学副园长": "edu", "后勤副园长": "logistics", "保教办主任": "all",
    "后勤处主任": "logistics", "教师发展处主任": "summary", "保健室": "all", "办公室主任": "class",
}


def build_principal(db: Session, user: User) -> Principal:
    from .services.calendar import current_semester_id
    staff = user.staff
    positions: list[str] = []
    class_ids: list[int] = []
    vice: list[int] = []
    sid = current_semester_id(db)
    if staff:
        for up in db.scalars(select(UserPosition).where(UserPosition.staff_id == staff.id)):
            if up.semester_id in (None, sid):
                positions.append(up.position.name)
        for cs in db.scalars(select(ClassStaff).where(ClassStaff.staff_id == staff.id, ClassStaff.semester_id == sid)):
            if cs.slot == "vice_lead":
                vice.append(cs.class_id)
            else:
                class_ids.append(cs.class_id)
    if user.role == "principal" and "园长" not in positions and not staff:
        positions.append("园长")
    if user.role == "admin":
        positions.append("管理员")
    if user.role == "parent" and user.parent_class_id:
        class_ids.append(user.parent_class_id)
    scope = "class"
    rank = ["all", "logistics", "edu", "summary", "class"]
    for p in positions:
        s = SCOPE_BY_POSITION.get(p)
        if s and rank.index(s) < rank.index(scope):
            scope = s
    if user.role in ("principal",) and scope == "class":
        scope = "all"
    if user.role == "admin":
        scope = "all"
    return Principal(user=user, staff=staff, role=user.role, positions=sorted(set(positions)),
                     class_ids=sorted(set(class_ids)), vice_class_ids=sorted(set(vice)), scope=scope)


def current(request: Request, db: Session = Depends(get_db)) -> Principal:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.query_params.get("token", "")
    if not token:
        raise HTTPException(401, "请先登录")
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "登录已过期，请重新登录")
    user = db.get(User, int(data["sub"]))
    if not user or user.status != "active":
        raise HTTPException(401, "账号不可用")
    return build_principal(db, user)


def require(*roles: str):
    def dep(p: Principal = Depends(current)) -> Principal:
        if p.role not in roles:
            raise HTTPException(403, "当前岗位无权访问")
        return p
    return dep


def class_name_map(db: Session) -> dict[int, str]:
    return {k.id: k.name for k in db.scalars(select(Klass))}
