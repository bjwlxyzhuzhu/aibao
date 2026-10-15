"""① 保教巡查链：诊断（星宝）↔ 质询（护苗）→ 答辩 → 裁判（明理）→ 分流 → 整改草稿（小步）。"""
from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field

from .. import config, kb
from ..models import Finding, Inspection, KbChunk, Media, Rectification, Setting
from ..services.workorders import create_work_order, suggest_assignee
from ..timeutil import now_local
from . import offline_rules as R
from .base import ChainContext


class _F(BaseModel):
    id: str
    segment: str = ""
    item: str
    category: str
    severity: str
    cited_chunks: list[int] = Field(default_factory=list)
    reason: str = ""


class DiagOut(BaseModel):
    findings: list[_F]


class _C(BaseModel):
    finding_id: str
    stance: str
    reason: str = ""
    cited_chunks: list[int] = Field(default_factory=list)


class ChalOut(BaseModel):
    challenges: list[_C]


class _R(BaseModel):
    finding_id: str
    decision: str
    reason: str = ""


class ReplyOut(BaseModel):
    replies: list[_R]


class _V(BaseModel):
    finding_id: str
    result: str
    cited_chunks: list[int] = Field(default_factory=list)
    confidence: float = 0.5
    reason: str = ""


class JudgeOut(BaseModel):
    verdicts: list[_V]


class TrackOut(BaseModel):
    title: str
    requirement: str
    evidence_needed: str = ""


CATS = {"安全", "卫生", "健康", "膳食", "设施", "保教", "生活照料"}
STANCE_CN = {"rebut": "反驳", "agree": "同意", "supplement": "补充"}
RESULT_CN = {"valid": "成立", "invalid": "不成立", "needs_review": "转园长"}


def _settings(db) -> tuple[float, int, list[str]]:
    th, rounds, cats = config.REVIEW_CONFIDENCE_THRESHOLD, config.DEBATE_MAX_ROUNDS, config.FORCE_REVIEW_CATEGORIES
    s = db.get(Setting, "thresholds")
    if s and isinstance(s.value, dict):
        th = float(s.value.get("review_confidence", th))
        rounds = int(s.value.get("debate_rounds", rounds))
        cats = s.value.get("force_review_categories", cats)
    return th, rounds, cats


def _chunks_text(hits: list[dict]) -> str:
    return "\n".join(f"[{h['id']}] 《{h['doc_title']}》{h['clause_no']}：{h['text']}" for h in hits)


def run_inspection(run_id: int, inspection_id: int, pace: float | None = None) -> None:
    ctx = ChainContext(run_id, pace=0.0)
    db = ctx.db
    try:
        insp = db.get(Inspection, inspection_id)
        ctx.pace = pace if pace is not None else (0.0 if ctx.online else 0.9)
        th, max_rounds, force_cats = _settings(db)
        images = [m.path_redacted for m in (db.get(Media, i) for i in insp.media_ids) if m and m.kind == "image" and m.path_redacted]
        text = insp.text_redacted or insp.text_raw
        klass = insp.klass.name if insp.klass else ""

        ctx.emit("aibao", "route", f"收到{klass}班「{insp.segment}」环节巡查，已脱敏，转入保教巡查链。", emotion="cheer")

        # 1. 诊断员：检索前 8 条条款
        hits = kb.search(db, f"{insp.segment} {text}", k=8)
        hit_ids = {h["id"] for h in hits}
        ctx.think("xingbao")

        def kb_search(q: str):
            return kb.search(db, q, k=3)

        user = f"环节：{insp.segment}\n班级：{klass}\n巡查记录：{text}\n\n可引用的条款切片：\n{_chunks_text(hits)}"
        diag, eng = ctx.call("xingbao", "diagnoser", user, DiagOut, "max", lambda: {"findings": R.diagnose(text, insp.segment, kb_search)}, images)
        ctx.run.engine = "llm" if eng.startswith("llm") else "offline"
        findings = [f for f in diag["findings"] if f.get("item")]
        for f in findings:
            f["category"] = f["category"] if f["category"] in CATS else "保教"
            f["severity"] = f["severity"] if f["severity"] in ("高", "中", "低") else "中"
            f["segment"] = insp.segment
            hit_ids.update(f.get("cited_chunks", []))
        if not findings:
            ctx.emit("xingbao", "statement", "对照条款逐项检查，这条巡查记录未发现问题。", emotion="happy")
        for f in findings:
            ctx.emit("xingbao", "statement", f"【{f['category']}·{f['severity']}】{f['item']}。{f['reason']}", finding_key=f["id"],
                     cited=f["cited_chunks"], emotion="cheer", content=f)

        # 2. 质询员逐条回应（第 1 轮）
        challenges: list[dict] = []
        replies: list[dict] = []
        if findings:
            ctx.think("humiao")
            fl = "\n".join(f"{f['id']}: [{f['category']}/{f['severity']}] {f['item']}（引用 {f['cited_chunks']}）{f['reason']}" for f in findings)
            ch, _ = ctx.call("humiao", "challenger", f"巡查记录：{text}\n\n诊断员问题清单：\n{fl}\n\n条款：\n{_chunks_text(hits)}",
                             ChalOut, "flash", lambda: {"challenges": R.challenge(text, findings)})
            challenges = ch["challenges"]
            for c in challenges:
                emo = {"rebut": "surprised", "agree": "support", "supplement": "cheer"}.get(c["stance"], "cheer")
                ctx.emit("humiao", "challenge" if c["stance"] == "rebut" else "support",
                         f"{STANCE_CN.get(c['stance'], c['stance'])}：{c['reason']}", target="xingbao",
                         finding_key=c["finding_id"], cited=c.get("cited_chunks", []), emotion=emo, content=c)
            # 3. 诊断员答辩（第 2 轮，最多两轮）
            rebuts = [c for c in challenges if c["stance"] == "rebut"]
            if rebuts and max_rounds >= 2:
                ctx.think("xingbao", round=2)
                rl = "\n".join(f"{c['finding_id']}: {c['reason']}" for c in rebuts)
                rp, _ = ctx.call("xingbao", "diagnoser_reply", f"巡查记录：{text}\n被反驳的问题：\n{rl}", ReplyOut, "max",
                                 lambda: {"replies": R.reply(challenges, findings)})
                replies = rp["replies"]
                for r in replies:
                    hold = r["decision"] == "hold"
                    ctx.emit("xingbao", "challenge" if hold else "support", ("坚持：" if hold else "撤回：") + r["reason"],
                             round=2, target="humiao", finding_key=r["finding_id"], emotion="cheer" if hold else "sad", content=r)

            # 4. 裁判员逐条裁定，必须引用真实存在的切片
            ctx.think("mingli", round=2)
            cl = "\n".join(f"{c['finding_id']}: {c['stance']} {c['reason']}" for c in challenges)
            rl2 = "\n".join(f"{r['finding_id']}: {r['decision']} {r['reason']}" for r in replies) or "无"
            jd, _ = ctx.call("mingli", "judge",
                             f"巡查记录：{text}\n\n条款：\n{_chunks_text(hits)}\n\n问题清单：\n{fl}\n\n质询：\n{cl}\n\n答辩：\n{rl2}",
                             JudgeOut, "max", lambda: {"verdicts": R.judge(findings, challenges, replies)})
            vmap = {v["finding_id"]: v for v in jd["verdicts"]}
            existing = {c.id for c in db.query(KbChunk.id).filter(KbChunk.id.in_(list(hit_ids) or [0]))}
            for f in findings:
                v = vmap.get(f["id"]) or {"result": "needs_review", "cited_chunks": [], "confidence": 0.3, "reason": "裁判未给出裁定"}
                cited = [c for c in v.get("cited_chunks", []) if c in existing]
                if not cited:
                    v["result"], v["reason"] = "needs_review", (v.get("reason", "") + "（未能引用有效条款，自动转人工）").strip()
                conf = max(0.0, min(1.0, float(v.get("confidence", 0.5))))
                reasons = []
                if v["result"] == "needs_review":
                    reasons.append("裁判转人工")
                if conf < th:
                    reasons.append(f"置信度 {conf:.2f} < {th}")
                if f["category"] in force_cats:
                    reasons.append(f"{f['category']}类必须复核")
                fobj = Finding(run_id=run_id, inspection_id=insp.id, key=f["id"], item=f["item"], segment=f["segment"],
                               category=f["category"], severity=f["severity"], reason=f.get("reason", ""),
                               cited_chunk_ids=cited or f.get("cited_chunks", []), solo_judgement="valid",
                               final_verdict=v["result"], verdict_reason=v.get("reason", ""), confidence=conf,
                               needs_review=bool(reasons), review_reason="；".join(reasons))
                db.add(fobj)
                db.flush()
                emo = {"valid": "happy", "invalid": "happy", "needs_review": "doubt"}[v["result"]]
                ctx.emit("mingli", "verdict", f"裁定{RESULT_CN[v['result']]}（置信度 {conf:.2f}）：{v.get('reason', '')}", round=2,
                         target="xingbao", finding_key=f["id"], cited=cited, confidence=conf, emotion=emo,
                         content={"result": v["result"], "finding_db_id": fobj.id, "needs_review": fobj.needs_review,
                                  "review_reason": fobj.review_reason})
                # 5. 分流
                if fobj.needs_review:
                    create_work_order(db, "review", fobj.id, f"复核：{insp.klass.name}班 {fobj.item}", None,
                                      "高" if fobj.category in force_cats else "中", insp.class_id, insp.is_demo)
                elif v["result"] == "valid":
                    _draft_rectification(ctx, insp, fobj)
        insp.status = "done"
        ctx.emit("aibao", "state", "本次巡查对抗完成。需要复核的条目已进入园长队列，整改单草稿等待园长确认。", emotion="happy")
        ctx.finish()
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        ctx.db.rollback()
        ctx.emit("aibao", "state", f"链路异常，已转人工处理：{e}", emotion="sad")
        ctx.finish("failed")
    finally:
        ctx.close()


def _draft_rectification(ctx: ChainContext, insp: Inspection, f: Finding) -> Rectification:
    db = ctx.db
    ctx.think("xiaobu", round=3)
    out, _ = ctx.call("xiaobu", "tracker", f"问题：[{f.category}/{f.severity}] {f.item}\n理由：{f.reason}\n环节：{f.segment}",
                      TrackOut, "flash",
                      lambda: {"title": f"{insp.klass.name}班 · {f.item}",
                               "requirement": f"1. 对照条款整改：{f.item}。\n2. 班内复盘当日{f.segment}环节流程。\n3. 回传整改后照片或文字说明。",
                               "evidence_needed": "整改后现场照片（已自动打码）或说明"})
    # 标题以系统已知班级为准，避免模型写错班级
    short = out["title"].split("·")[-1].split("|")[-1].split("｜")[-1].strip() or f.item
    out["title"] = f"{insp.klass.name}班 · {short}"
    assignee, rule = suggest_assignee(db, insp.class_id, f.category, f.segment, f.item)
    hours = {"高": 4, "中": 16, "低": 40}.get(f.severity, 16)
    r = Rectification(finding_ids=[f.id], class_id=insp.class_id, title=out["title"][:250],
                      requirement=out["requirement"] + "\n\n（AI 草稿，经园长确认后下发）", severity=f.severity,
                      assignee_staff_id=assignee, suggested_by_rule=rule, due_at=now_local() + timedelta(hours=hours),
                      status="draft", is_demo=insp.is_demo)
    db.add(r)
    db.flush()
    f.status = "rectifying"
    ctx.emit("xiaobu", "statement", f"已起草整改单「{r.title}」，建议责任人按岗位规则：{rule}。等待园长确认后下发。", round=3,
             finding_key=f.key, emotion="cheer", content={"rectification_id": r.id})
    return r
