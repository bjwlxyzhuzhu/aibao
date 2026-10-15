"""端到端冒烟测试（离线规则引擎）：python -m pytest tests -q  或  python tests/test_smoke.py"""
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ.update(DATA_DIR=TMP, DATABASE_URL=f"sqlite:///{TMP}/t.db", LLM_API_KEY="", DEMO_MODE="true",
                  DEMO_TODAY="2026-10-15", SEED_DEMO="false")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import Staff  # noqa: E402
from sqlalchemy import select  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def login(c, who):
    r = c.post("/api/auth/login", json={"login": who, "password": "Aibao@2026"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def wait_run(c, h, rid, timeout=30):
    for _ in range(timeout * 4):
        r = c.get(f"/api/runs/{rid}", headers=h).json()
        if r["status"] != "running":
            return r
        time.sleep(0.25)
    raise AssertionError("run timeout")


def test_all():
    with TestClient(app) as c:
        boss, teacher, admin = login(c, "yuanzhang"), login(c, "dayi_banzhang"), login(c, "admin")
        me = c.get("/api/me", headers=teacher).json()
        assert me["classes"] == ["大一"]
        cal = c.get("/api/calendar/today").json()
        assert cal["week_no"] == 6 and cal["parity"] == "double"  # 按校历：10.15 属第六周（双周）

        # 照片脱敏：所有人脸被模糊；网关失败拒发
        if (FIX / "faces.jpg").exists():
            r = c.post("/api/media", headers=teacher, files={"file": ("a.jpg", (FIX / "faces.jpg").read_bytes())}, data={"kind": "image"})
            assert r.status_code == 200 and r.json()["faces"] >= 1, r.text
            mid = r.json()["id"]
        else:
            mid = None

        # ① 巡查链（巡查文本中的教职工姓名取自导入名单，源码不写真实姓名）
        with SessionLocal() as db:
            who = db.scalar(select(Staff.name).where(Staff.name != "园长").order_by(Staff.id))
        r = c.post("/api/inspections", headers=teacher, json={"class_id": me["class_ids"][0], "segment": "午睡",
                   "text": "13:10 午睡巡视，寝室窗户紧闭有异味，" + who + "离开寝室约5分钟无人替岗，巡视记录12:30后空白。",
                   "media_ids": [mid] if mid else []})
        assert r.status_code == 200, r.text
        run = wait_run(c, teacher, r.json()["run_id"])
        assert run["status"] == "done"
        verdicts = [m for m in run["messages"] if m["action"] == "verdict"]
        assert verdicts and all(m["cited_chunks"] for m in verdicts if m["content"]["result"] != "needs_review")
        insp = c.get(f"/api/inspections/{r.json()['inspection_id']}", headers=teacher).json()
        assert insp["findings"]
        # 安全卫生健康类 100% 进复核
        for f in insp["findings"]:
            if f["category"] in ("安全", "卫生", "健康"):
                assert f["needs_review"]
        # 发往模型的文字不含教职工姓名
        logs = c.get("/api/admin/redaction-logs", headers=admin).json()
        assert all(who not in l["after"] for l in logs)

        # 申诉 → 复核
        fid = insp["findings"][0]["id"]
        assert c.post(f"/api/findings/{fid}/appeal", headers=teacher, json={"reason": "已有保育员在场"}).status_code == 200
        q = c.get("/api/reviews/queue", headers=boss).json()
        assert any(x["id"] == fid for x in q)
        assert c.get("/api/reviews/queue", headers=teacher).status_code == 403
        r = c.post("/api/reviews", headers=boss, json={"finding_id": fid, "decision": "valid", "note": "成立"}).json()
        rect_id = r["rectification_id"] or c.get("/api/rectifications?status=draft", headers=boss).json()[0]["id"]

        # 未经园长确认的整改单无法下发
        assert c.patch(f"/api/rectifications/{rect_id}", headers=teacher, json={"action": "issue"}).status_code == 403
        rr = c.patch(f"/api/rectifications/{rect_id}", headers=boss, json={"action": "issue"})
        assert rr.status_code == 200, rr.text
        assignee = rr.json()["assignee"]
        h2 = login(c, assignee)
        assert c.patch(f"/api/rectifications/{rect_id}", headers=h2, json={"action": "submit", "evidence_text": "已开窗、已补记录"}).status_code == 200
        assert c.patch(f"/api/rectifications/{rect_id}", headers=boss, json={"action": "close"}).json()["status"] == "closed"

        # ② 家园链：公开问题自动答；具体孩子转教师；红队拦截高风险测试草稿
        par = {"Authorization": f"Bearer {c.post('/api/auth/invite', json={'code': 'DA1A26'}).json()['token']}"}
        r = c.post("/api/parent/chat", headers=par, json={"content": "几点入园？"}).json()
        wait_run(c, par, r["run_id"])
        r = c.post("/api/parent/chat", headers=par, json={"content": "我家孩子今天发烧了能来吗"}).json()
        wait_run(c, par, r["run_id"])
        th = c.get("/api/parent/thread", headers=par).json()["messages"]
        assert any(m["route"] == "auto" for m in th if m["role"] == "parent")
        assert any(m["route"] == "transfer" for m in th if m["role"] == "parent")
        r = c.post("/api/parent/chat", headers=boss, json={"content": "孩子咳嗽怎么办", "test_draft": "保证没事，给孩子吃点退烧药就好，一定会好的。"}).json()
        run = wait_run(c, boss, r["run_id"])
        red = [m for m in run["messages"] if m["action"] == "redteam"]
        assert red and red[-1]["content"]["risk_level"] == "high"

        # ③ 议事链
        t = c.post("/api/council/topics", headers=boss, json={"title": "冬季午睡时间是否提前 20 分钟？"}).json()
        run = wait_run(c, boss, t["run_id"], timeout=60)
        brief = c.get(f"/api/council/topics/{t['id']}", headers=boss).json()["brief"]
        assert brief["consensus"] and brief["disagreements"]
        challenges = [m for m in run["messages"] if m["action"] == "challenge"]
        assert len({m["agent"] for m in challenges}) == 4  # 每个视角至少质疑一次

        # 驾驶舱
        d = c.get("/api/dashboard?source=real", headers=boss).json()
        assert d["kpi"]["inspections"] >= 1 and d["accuracy"]["reviewed"] >= 1

        # 导入中心：模板校验 + 回滚
        tpl = Path(__file__).resolve().parent.parent / "seed_data" / "import_template_2026autumn.xlsx"
        r = c.post("/api/admin/import/upload", headers=admin, data={"kind": "calendar"}, files={"file": ("t.xlsx", tpl.read_bytes())}).json()
        assert r["ok"], r
        assert c.post(f"/api/admin/import/{r['job_id']}/commit", headers=admin, json={}).status_code == 200
        assert c.post(f"/api/admin/import/{r['job_id']}/rollback", headers=admin).status_code == 200

        # 知识库上传后可检索
        r = c.post("/api/admin/kb/docs", headers=admin, data={"title": "测试制度", "kind": "policy", "visibility": "internal"},
                   files={"file": ("t.md", "第一条 午睡室每 15 分钟巡视一次并记录。".encode())}).json()
        assert r["chunk_count"] >= 1
        hits = c.get("/api/admin/kb/search?q=午睡巡视", headers=admin).json()
        assert any(h["doc_title"] == "测试制度" for h in hits)
    print("ALL OK")


if __name__ == "__main__":
    test_all()
