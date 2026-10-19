"""实践教学：五维保教实践能力评分（AI 草稿 → 双导师评阅）、成长档案（周趋势与增值）、成效数据导出。
五个维度取自《幼儿园教师专业标准（试行）》"专业能力"中的领域。"""
from __future__ import annotations

import re
from collections import defaultdict

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import kb
from ..models import AgentRun, Finding, Inspection, PracticeRecord, PracticeStudent, Review, RubricScore

DIMS = ["一日生活", "环境创设", "游戏支持", "激励评价", "反思发展"]
DIM_FULL = {"一日生活": "一日生活的组织与保育", "环境创设": "环境的创设与利用", "游戏支持": "游戏活动的支持与引导",
            "激励评价": "激励与评价", "反思发展": "反思与发展"}
SOURCE_RANK = {"mentor_u": 3, "mentor_k": 2, "ai": 1}


class _S(BaseModel):
    dim: str
    score: int
    evidence: str = ""
    cited_chunks: list[int] = Field(default_factory=list)


class RubricOut(BaseModel):
    scores: list[_S]
    suggestions: list[str] = Field(default_factory=list)


# ---------- 离线规则（未接模型时兜底，结果标注"离线规则引擎"） ----------
POS = {
    "一日生活": r"(提醒.{0,6}(洗手|喝水|如厕)|巡视|盖好被|整理|清点人数|按时|有序|照料)",
    "环境创设": r"(投放|材料|区角|环境|布置|标识|图示)",
    "游戏支持": r"(游戏|观察.{0,6}(幼儿|孩子)|支持|引导|追随|提问)",
    "激励评价": r"(表扬|鼓励|蹲下|倾听|回应|肯定|安抚|拥抱)",
    "反思发展": r"(反思|下次|改进|我意识到|原因是|如果再|调整)",
}
NEG = {
    "一日生活": r"(离开|无人|未(洗手|巡视|清点)|遗漏|蒙头|催促)",
    "环境创设": r"(杂乱|不足|缺少|危险|尖角|未收)",
    "游戏支持": r"(打断|包办|直接告诉|没有观察)",
    "激励评价": r"(大声|批评|呵斥|罚站|不理|比较)",
    "反思发展": r"(没想到|不知道为什么)",
}


def offline_rubric(text: str, findings: list[dict], search) -> dict:
    cats = [f.get("category") for f in findings]
    out = []
    for d in DIMS:
        pos = len(re.findall(POS[d], text))
        neg = len(re.findall(NEG[d], text))
        if d == "一日生活":
            neg += sum(c in ("安全", "卫生", "生活照料", "健康") for c in cats)
        if d == "激励评价":
            neg += sum(c == "保教" for c in cats)
        touched = pos + neg > 0
        score = max(1, min(5, 3 + min(pos, 2) - min(neg, 2))) if touched else 3
        hits = search(f"{DIM_FULL[d]} 幼儿园教师 专业标准")
        cited = [h["id"] for h in hits[:1]]
        ev = (f"记录中有 {pos} 处积极表现、{neg} 处需改进的表现，对照{hits[0]['doc_title']}{hits[0]['clause_no']}评定。" if touched and hits
              else "本次记录未涉及，按基本达到计。")
        out.append({"dim": d, "score": score, "evidence": ev, "cited_chunks": cited})
    low = min(out, key=lambda s: s["score"])
    sug = [f"下一次重点关注“{DIM_FULL[low['dim']]}”：记录时写清幼儿的反应和你的调整。"]
    if not re.search(POS["反思发展"], text):
        sug.append("在记录末尾补一句反思：这次哪里做得好、下次准备怎么改。")
    return {"scores": out, "suggestions": sug}


def score_record(ctx, practice: PracticeRecord, insp: Inspection, findings: list[dict], text: str) -> None:
    db = ctx.db
    hits = kb.search(db, "幼儿园教师 专业能力 " + " ".join(DIM_FULL.values()) + " " + text[:80], k=10)
    ref = "\n".join(f"[{h['id']}] 《{h['doc_title']}》{h['clause_no']}：{h['text'][:200]}" for h in hits)
    fl = "\n".join(f"- [{f.get('category')}/{f.get('severity')}] {f.get('item')}" for f in findings) or "无"
    ctx.think("mingli", round=3)
    out, _ = ctx.call("mingli", "rubric", f"实践记录：{text}\n\n裁定后的问题：\n{fl}\n\n可引用条款：\n{ref}", RubricOut, "max",
                      lambda: offline_rubric(text, findings, lambda q: kb.search(db, q, k=2)))
    valid_ids = {h["id"] for h in hits}
    by_dim = {s["dim"]: s for s in out["scores"] if s["dim"] in DIMS}
    for d in DIMS:
        s = by_dim.get(d, {"dim": d, "score": 3, "evidence": "未给出评分，按基本达到计。", "cited_chunks": []})
        db.add(RubricScore(record_id=practice.id, dim=d, score=max(1, min(5, int(s["score"]))), evidence=s.get("evidence", ""),
                           cited_chunk_ids=[c for c in s.get("cited_chunks", []) if c in valid_ids] or s.get("cited_chunks", [])[:1],
                           source="ai"))
    db.flush()
    summary = "、".join(f"{d} {by_dim.get(d, {'score': 3})['score']}" for d in DIMS)
    ctx.emit("mingli", "verdict", f"五维评分（AI 草稿）：{summary}。", round=3, emotion="happy",
             content={"rubric": out["scores"], "result": "rubric"})
    sug = out.get("suggestions") or []
    if sug:
        ctx.emit("xiaobu", "statement", "改进建议：" + "；".join(sug), round=3, emotion="cheer", content={"suggestions": sug})


# ---------- 成长档案 ----------
def final_scores(db: Session, record_id: int) -> dict[str, dict]:
    """每个维度取优先级最高来源的最新评分：高校导师 > 园所导师 > AI。"""
    best: dict[str, RubricScore] = {}
    for r in db.scalars(select(RubricScore).where(RubricScore.record_id == record_id).order_by(RubricScore.id)):
        cur = best.get(r.dim)
        if cur is None or SOURCE_RANK[r.source] >= SOURCE_RANK[cur.source]:
            best[r.dim] = r
    return {d: {"score": r.score, "source": r.source, "evidence": r.evidence, "cited": r.cited_chunk_ids} for d, r in best.items()}


def growth(db: Session, student_id: int) -> dict:
    recs = list(db.scalars(select(PracticeRecord).where(PracticeRecord.student_id == student_id).order_by(PracticeRecord.created_at)))
    weekly: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in recs:
        for d, v in final_scores(db, r.id).items():
            weekly[r.week_no][d].append(v["score"])
    weeks = sorted(weekly)
    series = [{"week": w, **{d: round(sum(v) / len(v), 2) for d, v in weekly[w].items()}} for w in weeks]

    def avg(ws):
        vals = [s[d] for s in series if s["week"] in ws for d in DIMS if d in s]
        return round(sum(vals) / len(vals), 2) if vals else None
    first, last = weeks[:2], weeks[-2:]
    va = None
    if len(weeks) >= 3:
        va = {d: round(sum(s.get(d, 0) for s in series if s["week"] in last) / max(1, sum(1 for s in series if s["week"] in last))
                       - sum(s.get(d, 0) for s in series if s["week"] in first) / max(1, sum(1 for s in series if s["week"] in first)), 2)
              for d in DIMS}
    return {"weeks": weeks, "series": series, "records": len(recs), "start_avg": avg(first), "recent_avg": avg(last),
            "value_added": va, "reflections": sum(1 for r in recs if r.reflection.strip())}


# ---------- 成效数据（全部由系统记录直接计算） ----------
def metrics(db: Session, demo: bool | None = None) -> dict:
    q = select(PracticeStudent)
    if demo is not None:
        q = q.where(PracticeStudent.is_demo.is_(demo))
    students = list(db.scalars(q))
    sids = {s.id for s in students}
    recs = [r for r in db.scalars(select(PracticeRecord)) if r.student_id in sids]
    rids = {r.id for r in recs}
    # AI 评分与导师评分一致性
    pairs = []
    for rid in rids:
        rows = list(db.scalars(select(RubricScore).where(RubricScore.record_id == rid)))
        ai = {r.dim: r.score for r in rows if r.source == "ai"}
        for r in rows:
            if r.source in ("mentor_u", "mentor_k") and r.dim in ai:
                pairs.append((ai[r.dim], r.score))
    # 对抗前后误判率（以导师对问题条目的评阅为标准答案）
    insp_ids = {r.inspection_id for r in recs}
    solo_err = adv_err = n = adv_n = 0
    for f in db.scalars(select(Finding).where(Finding.inspection_id.in_(insp_ids or {0}))):
        rv = db.scalar(select(Review).where(Review.finding_id == f.id).order_by(Review.id.desc()))
        if not rv:
            continue
        n += 1
        solo_err += f.solo_judgement != rv.decision
        if f.final_verdict in ("valid", "invalid"):
            adv_n += 1
            adv_err += f.final_verdict != rv.decision
    # 反馈时长
    lat = []
    for r in recs:
        run = db.scalar(select(AgentRun).where(AgentRun.chain == "inspect", AgentRun.source_id == r.inspection_id))
        if run and run.finished_at:
            lat.append((run.finished_at - run.started_at).total_seconds())
    reviewed_u = sum(1 for r in recs if r.mentor_u_at)
    reviewed_k = sum(1 for r in recs if r.mentor_k_at)
    gs = [growth(db, s.id) for s in students]
    vas = [g["value_added"] for g in gs if g["value_added"]]
    va_avg = {d: round(sum(v[d] for v in vas) / len(vas), 2) for d in DIMS} if vas else None
    return {
        "students": len(students), "records": len(recs),
        "records_per_student": round(len(recs) / len(students), 1) if students else None,
        "reflection_rate": round(sum(1 for r in recs if r.reflection.strip()) / len(recs), 3) if recs else None,
        "mentor_u_reviewed": reviewed_u, "mentor_k_reviewed": reviewed_k,
        "feedback_seconds_median": sorted(lat)[len(lat) // 2] if lat else None,
        "rubric_pairs": len(pairs),
        "rubric_exact_rate": round(sum(a == b for a, b in pairs) / len(pairs), 3) if pairs else None,
        "rubric_within1_rate": round(sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs), 3) if pairs else None,
        "findings_reviewed": n, "solo_error_rate": round(solo_err / n, 3) if n else None,
        "adversarial_error_rate": round(adv_err / adv_n, 3) if adv_n else None, "adversarial_deferred": n - adv_n,
        "value_added_avg": va_avg, "students_with_growth": len(vas),
    }


def metrics_markdown(m: dict, label: str) -> str:
    pct = lambda v: "—" if v is None else f"{v * 100:.1f}%"
    lines = [f"# 实践评价成效数据（{label}）", "", "> 全部数字由系统记录直接计算；评分一致性与误判率以导师评阅为标准答案。", "",
             "| 指标 | 数值 |", "| --- | --- |",
             f"| 参与学生数 | {m['students']} |", f"| 提交实践记录数 | {m['records']}（人均 {m['records_per_student']}） |",
             f"| 提交反思比例 | {pct(m['reflection_rate'])} |", f"| 高校导师 / 园所导师已评阅记录 | {m['mentor_u_reviewed']} / {m['mentor_k_reviewed']} |",
             f"| 从提交到收到 AI 反馈（中位数） | {'—' if m['feedback_seconds_median'] is None else str(round(m['feedback_seconds_median'])) + ' 秒'} |",
             f"| AI 评分与导师评分完全一致率（样本 {m['rubric_pairs']} 项） | {pct(m['rubric_exact_rate'])} |",
             f"| AI 评分与导师评分相差 ≤1 分比例 | {pct(m['rubric_within1_rate'])} |",
             f"| 问题条目导师评阅数 | {m['findings_reviewed']} |",
             f"| 诊断员单独判断误判率 | {pct(m['solo_error_rate'])} |", f"| 对抗后裁定误判率 | {pct(m['adversarial_error_rate'])}（另有 {m['adversarial_deferred']} 条主动交导师） |"]
    if m["value_added_avg"]:
        lines += ["", f"**五维增值（后两周均分 − 前两周均分，{m['students_with_growth']} 名学生平均）**", "", "| 维度 | 增值 |", "| --- | --- |"]
        lines += [f"| {DIM_FULL[d]} | {v:+.2f} |" for d, v in m["value_added_avg"].items()]
    return "\n".join(lines)
