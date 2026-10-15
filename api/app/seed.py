"""初始化：建表、预置组织架构、导入园方模板、注册品牌与形象素材、示例知识库、演示数据（is_demo 标记，可一键清除）。"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from . import config, kb
from .db import Base, SessionLocal, engine
from .importer import template as tpl
from .models import (AgentRun, Avatar, BrandAsset, ClassStaff, Finding, ImportJob, Inspection, Invite, KbDoc, Klass, Rectification, Review,
                     Staff, User, UserPosition, WorkOrder)
from .security import hash_pw
from .services.workorders import seed_policies
from .timeutil import now_local, today

AVATAR_ROOT = config.ASSETS_DIR / "avatars"


def init_db() -> None:
    Base.metadata.create_all(engine)


def seed_base() -> None:
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.login == "admin")):
            return
        pos = tpl.ensure_positions(db)
        db.add(User(login="admin", password_hash=hash_pw(config.DEMO_PASSWORD), must_change_password=not config.DEMO_MODE, role="admin"))
        boss = Staff(name="园长", note="项目负责人（姓名待管理员补充）")
        db.add(boss)
        db.flush()
        db.add(UserPosition(staff_id=boss.id, position_id=pos["园长"].id))
        db.add(User(login="yuanzhang", staff_id=boss.id, password_hash=hash_pw(config.DEMO_PASSWORD),
                    must_change_password=not config.DEMO_MODE, role="principal"))
        # 导入园方模板（人员、班级任职、校历、作息、特色课表）
        path = config.SEED_DIR / "import_template_2026autumn.xlsx"
        if not path.exists():  # 参赛代码包不含园方名单：由管理员在导入中心上传
            seed_policies(db)
            db.commit()
            seed_assets()
            seed_kb()
            return
        data = tpl.parse(path)
        report = tpl.validate(db, "all", data)
        job = ImportJob(kind="all", filename=path.name, file_path=str(path), version=1, report_json=report)
        db.add(job)
        db.flush()
        tpl.commit(db, job, data, report)
        seed_policies(db)
        # 家长邀请码（演示：大一班）
        k = db.scalar(select(Klass).where(Klass.name == "大一"))
        if k:
            db.add(Invite(code="DA1A26", class_id=k.id))
        db.commit()
    seed_assets()
    seed_kb()


DEMO_ALIASES = {"dayi_banzhang": ("teacher", True), "dayi_baoyu": ("care", False)}  # 演示岗位账号 → 大一班 (slot, is_lead)


def ensure_demo_aliases() -> None:
    """演示模式：为大一班班长、保育员建岗位登录别名，指向导入名单中的当期任职人；源代码与演示按钮不出现真实教职工姓名。"""
    if not config.DEMO_MODE:
        return
    with SessionLocal() as db:
        k = db.scalar(select(Klass).where(Klass.name == "大一"))
        if not k:
            return
        for login, (slot, lead) in DEMO_ALIASES.items():
            q = select(ClassStaff).where(ClassStaff.class_id == k.id, ClassStaff.slot == slot)
            cs = db.scalars(q.where(ClassStaff.is_lead.is_(True)) if lead else q.order_by(ClassStaff.id)).first()
            if not cs:
                continue
            u = db.scalar(select(User).where(User.login == login))
            if u:
                u.staff_id = cs.staff_id
            else:
                db.add(User(login=login, staff_id=cs.staff_id, password_hash=hash_pw(config.DEMO_PASSWORD),
                            must_change_password=False, role="staff"))
        db.commit()


def seed_assets() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Avatar.id).limit(1)):
            return
        for agent_dir in AVATAR_ROOT.iterdir() if AVATAR_ROOT.exists() else []:
            if not agent_dir.is_dir():
                continue
            for f in agent_dir.iterdir():
                if f.suffix.lower() not in (".png", ".svg") or f.stem.endswith("_raw"):
                    continue
                db.add(Avatar(agent=agent_dir.name, view=f.stem, image_path=str(f), version=1, active=True))
        brand = config.ASSETS_DIR / "brand"
        logo = brand / "logo_mark.png"
        if logo.exists():
            from .importer.images import process_logo
            res = process_logo(logo, 1, strip_bg=False)
            for kind, p in res["paths"].items():
                db.add(BrandAsset(kind=kind, path=p, source_path=str(logo), palette_json={"colors": res["palette"]}))
        full = brand / "logo_full.png"
        if full.exists():
            db.add(BrandAsset(kind="logo_wordmark", path=str(full), source_path=str(full)))
        db.commit()


def seed_kb() -> None:
    with SessionLocal() as db:
        if db.scalar(select(KbDoc.id).limit(1)):
            return
        for fname, title, kind, vis in [
            ("kb_policy_sample.md", "保教一日生活巡查细则（示例）", "policy", "internal"),
            ("kb_parent_public.md", "家长须知（示例）", "faq", "public"),
            ("kb_experience_sample.md", "本园经验·巡查点评范例（示例）", "experience", "internal"),
        ]:
            p = config.SEED_DIR / fname
            doc = KbDoc(title=title, kind=kind, visibility=vis, file_path=str(p), is_sample=True)
            db.add(doc)
            db.flush()
            kb.ingest(db, doc)
        db.commit()


DEMO_TEXTS = [
    ("午睡", "午睡巡视时发现寝室窗户紧闭，有异味，午睡巡视记录 12:30 之后空白。"),
    ("午睡", "13:10 巡视，一名幼儿蒙头睡觉，值班教师在旁随即纠正。巡视记录按时填写。"),
    ("午睡", "值班教师离开寝室约 5 分钟取被子，期间无人替岗。"),
    ("进餐", "午餐时教师多次催促幼儿快点吃，进餐时间不足 15 分钟。"),
    ("进餐", "早餐前幼儿洗手规范，餐桌已消毒，进餐有序，未发现问题。"),
    ("进餐", "饭菜偏凉，部分幼儿剩饭较多，保育员未个别照料。"),
    ("盥洗", "盥洗室地面有积水，未放防滑提示，幼儿排队时有推挤。"),
    ("盥洗", "两名幼儿毛巾混用，毛巾架标识脱落。"),
    ("户外", "大型玩具滑梯扶手螺丝松动，仍在使用。"),
    ("户外", "户外活动饮水不足，部分幼儿出汗较多未擦汗。"),
    ("户外", "足球课开始前清点人数，活动组织有序，器械检查良好。"),
    ("教学", "区域活动中剪刀使用后未收，放在桌面幼儿够得到的位置。"),
    ("教学", "集体活动中教师大声批评一名幼儿，让其站在一旁。"),
    ("入园", "晨检记录未填写完整，有一名幼儿咳嗽未登记。"),
    ("入园", "入园时教师临时离开，保育员已替岗，交接清楚。"),
    ("离园", "离园时一名陌生人代接，教师未核对接送卡。"),
    ("离园", "离园后消毒记录缺失，保育员说明次日补记。"),
]


def seed_demo_activity(force: bool = False) -> dict:
    """演示数据：在离线规则引擎上跑一组巡查（is_demo=True），用于视频录制前的界面演示；真实试用数据产生后驾驶舱自动切换为真实数据。"""
    from .agents import base as agent_base
    agent_base.FORCE_OFFLINE = True
    try:
        return _seed_demo(force)
    finally:
        agent_base.FORCE_OFFLINE = False


def _seed_demo(force: bool) -> dict:
    from .agents.inspect_chain import run_inspection
    from .gateway.redact_text import TextRedactor
    with SessionLocal() as db:
        if not force and db.scalar(select(Inspection.id).where(Inspection.is_demo.is_(True)).limit(1)):
            return {"skipped": True}
        classes = list(db.scalars(select(Klass).order_by(Klass.order)))
        if not classes:
            return {"skipped": "no classes"}
        red = TextRedactor.from_db(db)
        rng = random.Random(20261015)
        base = datetime.combine(today(), datetime.min.time())
        jobs = []
        n = 0
        for day in range(0, 4):
            for _ in range(7 if day else 9):
                seg, text = rng.choice(DEMO_TEXTS)
                k = rng.choice(classes)
                hh = {"入园": 7, "进餐": 11, "盥洗": 9, "教学": 9, "户外": 10, "午睡": 13, "离园": 16}[seg]
                at = base - timedelta(days=day) + timedelta(hours=hh, minutes=rng.randint(0, 50))
                if at > now_local():
                    at = now_local() - timedelta(minutes=rng.randint(5, 90))
                insp = Inspection(class_id=k.id, segment=seg, text_raw=text, text_redacted=red.redact(text)[0], created_at=at,
                                  is_demo=True, week_no=6, status="running")
                db.add(insp)
                db.flush()
                run = AgentRun(chain="inspect", source_id=insp.id, started_at=at, is_demo=True)
                db.add(run)
                db.flush()
                jobs.append((run.id, insp.id, at))
                n += 1
        db.commit()
    for run_id, iid, at in jobs:
        run_inspection(run_id, iid, pace=0)
    with SessionLocal() as db:
        rng = random.Random(7)
        boss = db.scalar(select(Staff).where(Staff.name == "园长"))
        for run_id, iid, at in jobs:
            for f in db.scalars(select(Finding).where(Finding.inspection_id == iid)):
                f.created_at = at + timedelta(seconds=40)
        # 园长复核一部分（作为标准答案），并下发 / 关闭部分整改单，展示闭环
        fs = list(db.scalars(select(Finding).join(Inspection).where(Inspection.is_demo.is_(True))))
        for f in fs:
            if f.needs_review and rng.random() < 0.7 and f.inspection.created_at < now_local() - timedelta(hours=3):
                # 演示用"园长复核"：对抗后裁定多数与园长一致；诊断员单独判断（一律成立）在不成立项上出错
                if f.final_verdict in ("valid", "invalid"):
                    dec = f.final_verdict if rng.random() < 0.9 else ("invalid" if f.final_verdict == "valid" else "valid")
                else:
                    dec = "valid" if rng.random() < 0.55 else "invalid"
                db.add(Review(finding_id=f.id, reviewer_staff_id=boss.id if boss else None, decision=dec, note="演示复核",
                              created_at=f.created_at + timedelta(hours=1)))
                f.status = "reviewed" if dec == "valid" else "closed"
                for w in db.scalars(select(WorkOrder).where(WorkOrder.type == "review", WorkOrder.ref_id == f.id)):
                    w.status, w.done_at = "done", f.created_at + timedelta(hours=1, minutes=rng.randint(0, 200))
        for r in db.scalars(select(Rectification).where(Rectification.is_demo.is_(True))):
            x = rng.random()
            if x < 0.55:
                r.status, r.issued_at, r.closed_at = "closed", r.created_at + timedelta(minutes=30), r.created_at + timedelta(hours=5)
            elif x < 0.8:
                r.status, r.issued_at = "issued", r.created_at + timedelta(minutes=30)
                from .services.workorders import create_work_order
                create_work_order(db, "rectification", r.id, r.title, r.assignee_staff_id, r.severity, r.class_id, True,
                                  start=r.issued_at)
        db.commit()
    _seed_demo_parent_and_council()
    return {"inspections": n}


DEMO_PARENT_QS = ["几点入园？", "每周食谱在哪里看？", "周五下午有什么安排？", "户外特色课有哪些？", "需要带备用衣物吗？",
                  "我家孩子今天有点咳嗽可以来吗？", "孩子昨天在园里摔了一下，怎么回事？", "几点入园？", "请假找谁？"]


def _seed_demo_parent_and_council() -> None:
    from .agents.council_chain import run_council
    from .agents.parent_chain import run_parent
    from .models import CouncilTopic, ParentMessage, ParentThread
    jobs = []
    with SessionLocal() as db:
        k = db.scalar(select(Klass).where(Klass.name == "大一"))
        u = db.scalar(select(User).where(User.login == "parent:demo"))
        if not u:
            u = User(login="parent:demo", password_hash="!", must_change_password=False, role="parent",
                     parent_class_id=k.id if k else None)
            db.add(u)
            db.flush()
        t = ParentThread(user_id=u.id, class_id=u.parent_class_id)
        db.add(t)
        db.flush()
        for q in DEMO_PARENT_QS:
            m = ParentMessage(thread_id=t.id, role="parent", content=q, is_demo=True)
            db.add(m)
            db.flush()
            run = AgentRun(chain="parent", source_id=m.id, is_demo=True)
            db.add(run)
            db.flush()
            m.run_id = run.id
            jobs.append((run.id, m.id))
        topic = None
        if not db.scalar(select(CouncilTopic.id).limit(1)):
            topic = CouncilTopic(title="冬季午睡时间是否提前 20 分钟？", detail="讨论冬季午睡时间调整方案，综合保健、教师、家长与安全四方意见。（演示议题）")
            db.add(topic)
            db.flush()
            crun = AgentRun(chain="council", source_id=topic.id, is_demo=True)
            db.add(crun)
            db.flush()
            topic.run_id = crun.id
        db.commit()
        cjob = (topic.run_id, topic.id) if topic else None
    for rid, mid in jobs:
        run_parent(rid, mid)
    if cjob:
        run_council(*cjob, pace=0)


def run_all(with_demo: bool = True) -> None:
    init_db()
    seed_base()
    ensure_demo_aliases()
    if with_demo:
        seed_demo_activity()


if __name__ == "__main__":
    run_all()
    print("seed done")
