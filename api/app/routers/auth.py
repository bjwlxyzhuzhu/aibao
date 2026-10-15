from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_db
from ..models import Invite, Klass, User
from ..security import Principal, check_pw, current, hash_pw, make_token
from ..services.calendar import calendar_today

router = APIRouter()


class LoginIn(BaseModel):
    login: str
    password: str


class InviteIn(BaseModel):
    code: str
    phone: str = ""


def _me(db: Session, p: Principal) -> dict:
    names = {k.id: k.name for k in db.scalars(select(Klass))}
    return {
        "user_id": p.user.id, "login": p.user.login, "role": p.role, "name": p.name, "positions": p.positions,
        "class_ids": p.class_ids, "classes": [names.get(i, "") for i in p.class_ids],
        "vice_class_ids": p.vice_class_ids, "scope": p.scope, "must_change_password": p.user.must_change_password,
        "staff_id": p.staff.id if p.staff else None,
    }


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.login == body.login.strip()))
    if not u or not check_pw(body.password, u.password_hash) or u.status != "active":
        raise HTTPException(400, "账号或密码不正确")
    from ..security import build_principal
    return {"token": make_token(u), "me": _me(db, build_principal(db, u))}


@router.post("/auth/invite")
def invite_login(body: InviteIn, db: Session = Depends(get_db)):
    inv = db.get(Invite, body.code.strip().upper())
    if not inv or inv.revoked:
        raise HTTPException(400, "邀请码无效或已作废")
    login = f"parent:{inv.code}:{body.phone or 'guest'}"
    u = db.scalar(select(User).where(User.login == login))
    if not u:
        u = User(login=login, password_hash="!", must_change_password=False, role="parent", parent_class_id=inv.class_id)
        db.add(u)
        db.commit()
    from ..security import build_principal
    return {"token": make_token(u), "me": _me(db, build_principal(db, u))}


@router.get("/me")
def me(p: Principal = Depends(current), db: Session = Depends(get_db)):
    return _me(db, p)


class PwIn(BaseModel):
    old: str
    new: str


@router.post("/auth/password")
def change_pw(body: PwIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    u = db.get(User, p.user.id)
    if not check_pw(body.old, u.password_hash):
        raise HTTPException(400, "原密码不正确")
    if len(body.new) < 8:
        raise HTTPException(400, "新密码至少 8 位")
    u.password_hash = hash_pw(body.new)
    u.must_change_password = False
    db.commit()
    return {"ok": True}


@router.get("/public/info")
def public_info(db: Session = Depends(get_db)):
    """未登录也可访问：园所名称、演示模式、今日校历。"""
    demo = []
    if config.DEMO_MODE:
        demo = [
            {"label": "园长", "login": "yuanzhang", "portal": "principal"},
            {"label": "班级教师（大一班班长）", "login": "dayi_banzhang", "portal": "staff"},
            {"label": "保育员（大一班）", "login": "dayi_baoyu", "portal": "staff"},
            {"label": "管理员", "login": "admin", "portal": "admin"},
            {"label": "家长（邀请码）", "login": "DA1A26", "portal": "parent"},
        ]
    return {"school": "宝鸡幼儿园", "product": "爱宝园务大脑", "demo_mode": config.DEMO_MODE,
            "demo_accounts": demo, "demo_password": config.DEMO_PASSWORD if config.DEMO_MODE else None,
            "calendar": calendar_today(db)}
