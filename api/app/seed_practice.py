"""实践教学种子：国家规范知识库；演示用见习队列（虚构学生代号，is_demo 标记，可一键清除，不作为成效证据）。"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy import select

from . import config, kb
from .db import SessionLocal
from .models import (AgentRun, ClassStaff, Finding, Inspection, KbDoc, Klass, PracticeRecord, PracticeStudent, Review,
                     RubricScore, User)
from .security import hash_pw
from .timeutil import now_local

NATIONAL = [("01_幼儿园工作规程.md", "幼儿园工作规程"), ("02_3-6岁儿童学习与发展指南.md", "3-6岁儿童学习与发展指南"),
            ("03_幼儿园保育教育质量评估指南.md", "幼儿园保育教育质量评估指南"), ("04_幼儿园教师专业标准.md", "幼儿园教师专业标准（试行）")]


def seed_national_kb() -> None:
    with SessionLocal() as db:
        for fname, title in NATIONAL:
            p = config.SEED_DIR / "national" / fname
            if not p.exists() or db.scalar(select(KbDoc.id).where(KbDoc.title == title)):
                continue
            doc = KbDoc(title=title, kind="national", visibility="internal", file_path=str(p), is_sample=False)
            db.add(doc)
            db.flush()
            kb.ingest(db, doc)
        db.commit()


# 演示文本：前几周问题多、反思少；后几周表现与反思逐步改善（仅用于界面演示）
EARLY = [
    ("午睡", "我负责看午睡。13:00 我去走廊拿被子离开了几分钟，回来发现一名幼儿蒙头睡，我把被子拉下来了。巡视记录我没来得及填。"),
    ("进餐", "午餐时有几个孩子吃得慢，我在旁边一直催他们快点吃，还说别的小朋友都吃完了。"),
    ("盥洗", "带孩子们洗手，地面有积水我没注意，有孩子差点滑倒。排队时有点挤。"),
    ("户外", "户外活动时我主要在旁边看，孩子玩滑梯时有推挤，我大声批评了一个孩子。"),
    ("教学", "区域活动我投放了剪纸材料，剪刀用完没收，放在桌上。孩子问我问题时我直接告诉了答案。"),
]
LATE = [
    ("午睡", "午睡前我检查了口袋和床铺，13:00 起每 15 分钟巡视一次并填写记录。发现一名幼儿蒙头睡，我轻声提醒并帮他整理被子。反思：下次离开前先请保育老师替岗。"),
    ("进餐", "午餐时我蹲下来鼓励进餐慢的孩子，先给他盛小半碗，吃完再添，没有催促。反思：我意识到比较会让孩子紧张，下次多用鼓励。"),
    ("盥洗", "洗手前我先检查地面并放好防滑提示，分组如厕盥洗，按图示提醒七步洗手，孩子们有序完成。下次准备把图示贴得更低一些。"),
    ("户外", "户外前清点人数并目测检查器械，孩子游戏时我在旁观察，看到有孩子争抢滑梯，我引导他们轮流并肯定了主动谦让的孩子。"),
    ("教学", "区域活动中我观察孩子剪纸的过程，用提问引导他们自己想办法，剪刀用完及时收纳。反思：原因是我之前太急着给答案，下次多等一等。"),
]


def seed_practice_demo(force: bool = False) -> dict:
    from .agents import base as agent_base
    from .agents.inspect_chain import run_inspection
    from .gateway.redact_text import TextRedactor
    with SessionLocal() as db:
        if not force and db.scalar(select(PracticeStudent.id).limit(1)):
            return {"skipped": True}
        classes = list(db.scalars(select(Klass).order_by(Klass.order)))[:5]
        if not classes:
            return {"skipped": "no classes"}
        mentor = db.scalar(select(User).where(User.login == "gaoxiao_daoshi"))
        if not mentor:
            mentor = User(login="gaoxiao_daoshi", password_hash=hash_pw(config.DEMO_PASSWORD), must_change_password=False, role="mentor")
            db.add(mentor)
            db.flush()
        rng = random.Random(20261018)
        students = []
        for i in range(10):
            code = f"学生{chr(65 + i)}"
            login = f"xs_{chr(97 + i)}"
            u = db.scalar(select(User).where(User.login == login)) or User(login=login, password_hash=hash_pw(config.DEMO_PASSWORD),
                                                                           must_change_password=False, role="student")
            db.add(u)
            db.flush()
            k = classes[i % len(classes)]
            lead = db.scalar(select(ClassStaff).where(ClassStaff.class_id == k.id, ClassStaff.is_lead.is_(True)))
            st = PracticeStudent(user_id=u.id, code=code, cohort="学前教育专业本科 · 见习（演示）", class_id=k.id,
                                 mentor_u_user_id=mentor.id, mentor_k_staff_id=lead.staff_id if lead else None, is_demo=True)
            db.add(st)
            students.append(st)
        db.flush()
        red = TextRedactor.from_db(db)
        jobs = []
        today0 = datetime.combine(now_local().date(), datetime.min.time())
        for st in students:
            skill = rng.uniform(0.0, 0.35)  # 学生起点差异
            for w in range(1, 7):
                p_late = min(0.95, skill + (w - 1) * 0.17 + rng.uniform(-0.1, 0.1))
                seg, text = rng.choice(LATE if rng.random() < p_late else EARLY)
                at = today0 - timedelta(days=(6 - w) * 7 + rng.randint(1, 3), hours=-rng.randint(9, 16))
                insp = Inspection(class_id=st.class_id, segment=seg, text_raw=text, text_redacted=red.redact(text)[0], created_at=at,
                                  is_demo=True, status="running")
                db.add(insp)
                db.flush()
                rec = PracticeRecord(student_id=st.id, inspection_id=insp.id, week_no=w, created_at=at, is_demo=True)
                db.add(rec)
                run = AgentRun(chain="inspect", source_id=insp.id, started_at=at, is_demo=True)
                db.add(run)
                db.flush()
                jobs.append((run.id, insp.id, rec.id, at, w))
        db.commit()
    agent_base.FORCE_OFFLINE = True
    try:
        for run_id, iid, *_ in jobs:
            run_inspection(run_id, iid, pace=0)
    finally:
        agent_base.FORCE_OFFLINE = False
    with SessionLocal() as db:
        rng = random.Random(7)
        for run_id, iid, rid, at, w in jobs:
            run = db.get(AgentRun, run_id)
            run.started_at, run.finished_at = at, at + timedelta(seconds=rng.randint(38, 70))
            rec = db.get(PracticeRecord, rid)
            if rng.random() < 0.55 + w * 0.06:
                rec.reflection = rng.choice(["收到建议，下次会先请保育老师替岗再离开。", "我会把鼓励放在前面，不再拿孩子作比较。",
                                             "下次活动前先检查环境和材料，用完及时收纳。", "多观察、少替孩子做决定。"])
                rec.reflection_at = at + timedelta(hours=6)
            ai = {r.dim: r.score for r in db.scalars(select(RubricScore).where(RubricScore.record_id == rid, RubricScore.source == "ai"))}
            for kind, prob in (("mentor_u", 0.85), ("mentor_k", 0.65)):
                if rng.random() > prob or w == 6 and rng.random() < 0.4:
                    continue
                for d, s in ai.items():
                    delta = rng.choices([0, 1, -1, 2], [0.62, 0.17, 0.17, 0.04])[0]
                    db.add(RubricScore(record_id=rid, dim=d, score=max(1, min(5, s + delta)), source=kind, evidence="导师评阅（演示）"))
                setattr(rec, f"{kind}_comment", rng.choice(["观察记录具体，继续保持。", "注意保教结合，安全意识再加强。",
                                                           "反思到位，下周尝试新的组织方式。", "师幼互动更自然了，很好。"]))
                setattr(rec, f"{kind}_at", at + timedelta(hours=rng.randint(8, 30)))
                if kind == "mentor_u":
                    for f in db.scalars(select(Finding).where(Finding.inspection_id == iid)):
                        dec = f.final_verdict if f.final_verdict in ("valid", "invalid") and rng.random() < 0.9 else rng.choice(["valid", "invalid"])
                        db.add(Review(finding_id=f.id, decision=dec, note="mentor_u（演示）", created_at=at + timedelta(hours=10)))
            for f in db.scalars(select(Finding).where(Finding.inspection_id == iid)):
                f.created_at = at
        db.commit()
    return {"students": 10, "records": len(jobs)}
