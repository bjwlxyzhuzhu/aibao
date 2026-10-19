"""离线规则引擎：未配置云端模型时，巡查/家园/议事三条链仍可跑通（结果标注"离线引擎"）。
规则只做关键词与条款检索，判断质量远低于大模型，仅用于演示与断网兜底。"""
from __future__ import annotations

import re

# (关键词正则, 问题描述, 类别, 严重度, 检索词)
INSPECT_RULES = [
    (r"(无人|没有?(老师|教师|人)|离开|离岗|独自|单独)", "幼儿活动时段出现看护空档", "安全", "高", "看护 离岗 视线"),
    (r"(巡视|巡查)(记录)?.{0,12}(缺|未填|没填|空白|漏)|未(按时)?巡视|(记录|登记)(缺失|空白|未填|漏)", "巡视或过程记录不完整", "保教", "中", "巡视 记录 间隔"),
    (r"(湿滑|积水|水渍|滑倒)", "地面湿滑存在滑倒隐患", "安全", "高", "地面 湿滑 防滑"),
    (r"(插座|电线|药品|药瓶|剪刀|消毒液|洗涤剂).{0,8}(外露|未收|放在|随意|触手|够得到|未上锁)|(外露|未收).{0,6}(插座|电线|药品|剪刀|消毒液)", "危险物品或电源未妥善收纳", "安全", "高", "危险物品 收纳 上锁"),
    (r"(螺丝|松动|破损|断裂|尖角|毛刺|生锈|晃动)", "户外或室内器械存在破损松动", "设施", "高", "器械 检查 破损"),
    (r"(未|没|没有)(洗手|消毒|清洗)|(毛巾|水杯|杯子).{0,4}(混用|共用)", "卫生消毒或个人用品管理不到位", "卫生", "中", "消毒 洗手 毛巾 水杯"),
    (r"(消毒记录|消毒登记).{0,4}(缺|未|没|漏|补)", "消毒记录不完整或事后补记", "卫生", "中", "消毒 记录"),
    (r"(晨检|体温|发热|咳嗽|呕吐|皮疹)", "健康观察或晨检环节需关注", "健康", "高", "晨检 体温 隔离"),
    (r"(窗户?紧闭|不通风|异味|闷)", "室内通风不足", "健康", "中", "通风 开窗"),
    (r"(盖(被|子)|被子).{0,6}(蒙|捂|盖住|过头)|蒙头", "午睡时幼儿蒙头睡觉未及时纠正", "安全", "高", "午睡 蒙头 巡视"),
    (r"(催促|一直催|催他|呵斥|大声|吼|批评|罚站|不让|别的小朋友都|拿.{0,4}比较)", "师幼互动方式不当", "保教", "中", "师幼互动 尊重 情绪"),
    (r"(直接告诉了?答案|包办|替.{0,3}(做|完成))", "未给幼儿自主探究的机会", "保教", "低", "游戏 支持 引导 探究"),
    (r"(剩饭|挑食|进餐过快|进餐时间.{0,4}(短|不足)|饭菜.{0,3}凉|食物.{0,3}(过烫|太烫))", "进餐照料不到位", "膳食", "中", "进餐 照料 温度"),
    (r"(留样|食谱).{0,4}(缺|未|没)", "食品留样或食谱公示不规范", "膳食", "中", "留样 食谱"),
    (r"(饮水|喝水).{0,6}(不足|少|没|未)", "幼儿饮水照料不足", "生活照料", "低", "饮水 照料"),
    (r"(排队|拥挤|推挤|追跑|奔跑).{0,6}(楼梯|走廊|盥洗)|(楼梯|走廊|盥洗).{0,6}(拥挤|推挤|追跑)", "过渡环节组织秩序不足", "安全", "中", "过渡 秩序 楼梯"),
    (r"(接送卡|陌生人|未核对|代接)", "离园接送核验不规范", "安全", "高", "接送 核对 离园"),
]

MITIGATE = r"(已|随即|马上|立即|临时|替岗|代岗|按规定|为了通风|通风需要|已补|已整改|已纠正|在旁|在场)"
POSITIVE = r"(良好|规范|有序|未发现|无异常|正常|到位)"


def diagnose(text: str, segment: str, search) -> list[dict]:
    findings = []
    t = text or ""
    for i, (pat, item, cat, sev, q) in enumerate(INSPECT_RULES):
        m = re.search(pat, t)
        if not m:
            continue
        hits = search(f"{segment} {q} {m.group(0)}")
        hits.sort(key=lambda h: 0 if segment in (h.get("clause_no") or "") else 1)  # 优先引用本环节章节
        cited = [h["id"] for h in hits[:2]]
        if not cited:
            continue
        findings.append({"id": f"f{len(findings) + 1}", "segment": segment, "item": item, "category": cat,
                         "severity": sev, "cited_chunks": cited,
                         "reason": f"记录中出现“{m.group(0)}”，对照{hits[0]['doc_title']}{hits[0]['clause_no']}的要求，存在不符。",
                         "_evidence": m.group(0)})
    return findings


def _mitigation(window: str) -> str | None:
    """找减轻情节；排除"无人替岗""没有通风"这类否定说法。"""
    for m in re.finditer(MITIGATE, window):
        before = window[max(0, m.start() - 2):m.start()]
        if re.search(r"(无|没|未|不|非)", before):
            continue
        return m.group(0)
    return None


def _sentence(text: str, ev: str) -> str:
    for sent in re.split(r"[。；;！!\n]", text):
        if ev and ev in sent:
            return sent
    return text


def challenge(text: str, findings: list[dict]) -> list[dict]:
    out = []
    for f in findings:
        ev = f.get("_evidence", "")
        window = _sentence(text, ev)
        mm = _mitigation(window)
        if mm:
            out.append({"finding_id": f["id"], "stance": "rebut",
                        "reason": f"记录里写明“{mm}”，现场已有处置或替岗，不宜直接认定为问题。", "cited_chunks": []})
        elif f["severity"] == "低":
            out.append({"finding_id": f["id"], "stance": "supplement",
                        "reason": "属于一线常见情况，建议以提醒为主，同时补充当时的班级人数与活动安排。", "cited_chunks": []})
        else:
            out.append({"finding_id": f["id"], "stance": "agree",
                        "reason": "从一线角度看，这一点确实需要改进，没有可以解释的特殊情境。", "cited_chunks": []})
    return out


def reply(challenges: list[dict], findings: list[dict]) -> list[dict]:
    out = []
    fmap = {f["id"]: f for f in findings}
    for c in challenges:
        if c["stance"] != "rebut":
            continue
        f = fmap.get(c["finding_id"])
        hold = f and f["severity"] == "高"
        out.append({"finding_id": c["finding_id"], "decision": "hold" if hold else "withdraw",
                    "reason": "即便已有处置，高风险环节仍需留痕并复盘。" if hold else "接受质询，现场已处置，撤回该条。"})
    return out


def judge(findings: list[dict], challenges: list[dict], replies: list[dict]) -> list[dict]:
    cmap = {c["finding_id"]: c for c in challenges}
    rmap = {r["finding_id"]: r for r in replies}
    out = []
    for f in findings:
        c = cmap.get(f["id"], {})
        r = rmap.get(f["id"])
        cited = f["cited_chunks"][:1]
        if c.get("stance") == "rebut":
            if r and r["decision"] == "withdraw":
                out.append({"finding_id": f["id"], "result": "invalid", "cited_chunks": cited, "confidence": 0.72,
                            "reason": "质询员给出了现场已处置的情境，诊断员撤回，条款要求已满足。"})
            else:
                out.append({"finding_id": f["id"], "result": "needs_review", "cited_chunks": cited, "confidence": 0.55,
                            "reason": "双方对现场情境的认定冲突，记录不足以判断，交园长复核。"})
        elif c.get("stance") == "supplement":
            out.append({"finding_id": f["id"], "result": "valid", "cited_chunks": cited, "confidence": 0.74,
                        "reason": "问题成立，程度较轻，按条款以提醒整改为主。"})
        else:
            out.append({"finding_id": f["id"], "result": "valid", "cited_chunks": cited, "confidence": 0.86,
                        "reason": "事实清楚，条款明确，质询员亦认可。"})
    return out


# ---------- 家园沟通 ----------
TRANSFER_RE = r"(我家|我们家|孩子(今天|昨天|在园|怎么|是不是|被)|请假|受伤|摔|磕|咬|打人|被打|发烧|发热|生病|过敏|投诉|退费|欺负|哭了|没吃|尿裤子)"
PROMISE_RE = r"(保证|一定会|肯定会|绝对|包您|免费退|特殊照顾|单独照顾)"
MEDICAL_RE = r"(吃药|服用|剂量|退烧药|抗生素|诊断为|应该是.{0,4}(病|炎))"


def answer(question: str, hits: list[dict]) -> dict:
    if not hits:
        return {"reply": "这个问题爱宝还不确定，已帮您记下，老师会尽快回复您哦～", "sources": []}
    h = hits[0]
    body = re.sub(r"^\s*(第[^条]+条|\d+(\.\d+)*\.?|[一二三四五六七八九十]+、)\s*", "", h["text"]).replace("\n", "")
    if len(body) > 90:
        body = body[:88] + "…"
    return {"reply": f"爱宝查到啦：{body} 🌟", "sources": [h["id"]]}


def redteam(draft: str) -> dict:
    issues = []
    if re.search(PROMISE_RE, draft):
        issues.append({"type": "promise", "quote": re.search(PROMISE_RE, draft).group(0), "suggestion": "删除承诺性表述，改为“老师会关注”"})
    if re.search(MEDICAL_RE, draft):
        issues.append({"type": "medical", "quote": re.search(MEDICAL_RE, draft).group(0), "suggestion": "不提供用药或诊断建议，请家长咨询医生"})
    if re.search(r"1[3-9]\d{9}|【幼儿|【教职工", draft):
        issues.append({"type": "privacy", "quote": "个人信息", "suggestion": "删除个人信息"})
    if re.search(r"(不可能|您应该|自己看|别问)", draft):
        issues.append({"type": "emotion", "quote": re.search(r"(不可能|您应该|自己看|别问)", draft).group(0), "suggestion": "改为共情、平和的表述"})
    level = "low"
    if any(i["type"] in ("medical", "privacy") for i in issues) or len(issues) >= 2:
        level = "high"
    elif issues:
        level = "medium"
    return {"risk_level": level, "issues": issues}


def rewrite(draft: str, issues: list[dict]) -> str:
    out = re.sub(PROMISE_RE, "会尽力", draft)
    out = re.sub(r"(不可能|您应该|自己看|别问)", "", out)
    return out


# ---------- 园务议事 ----------
VIEWS = {
    "health": ("保健视角", "从健康角度", ["作息调整要保证午睡总时长不少于 2 小时", "冬季午睡前后要注意保暖与通风的平衡"]),
    "teacher": ("教师视角", "从保教实施角度", ["调整会影响餐后散步与盥洗衔接", "需要同步调整保育员的清扫与铺床时间"]),
    "parent": ("家长视角", "从家庭与幼儿角度", ["接送时间不变时，家长接受度较高", "需要提前一周告知家长并说明理由"]),
    "safety": ("安全视角", "从安全管理角度", ["时间调整后午睡巡视人员必须到位", "过渡环节缩短时要防止楼梯与盥洗室拥挤"]),
}
CHALLENGE_PLAN = {"health": "parent", "teacher": "health", "parent": "safety", "safety": "teacher"}


def council_statement(view: str, topic: str, hits: list[dict]) -> dict:
    name, angle, ev = VIEWS[view]
    pos = {"health": "有条件支持", "teacher": "有条件支持", "parent": "支持", "safety": "有条件支持"}[view]
    evidence = list(ev)
    if hits:
        evidence.insert(0, f"{hits[0]['doc_title']}{hits[0]['clause_no']}：{hits[0]['text'][:40]}…")
    return {"round": 1, "position": f"{angle}，对“{topic[:24]}”{pos}：{ev[0]}。", "evidence": evidence,
            "challenge_to": None, "challenge": ""}


def council_challenge(view: str, topic: str) -> dict:
    target = CHALLENGE_PLAN[view]
    text = {
        "health": "家长视角只看接受度，但如果提前后午睡总时长被压缩，健康收益就打了折扣。",
        "teacher": "保健视角要求的保暖与通风，在餐后过渡缩短的情况下，教师很难同时做到。",
        "parent": "安全视角提出加巡视人员，可能挤占离园前的沟通时间，家长会有意见。",
        "safety": "教师视角说衔接能调整，但餐后过渡时间仍需核对，否则盥洗室会拥挤。",
    }[view]
    return {"round": 2, "position": "", "evidence": [], "challenge_to": target, "challenge": text}


def council_brief(topic: str) -> dict:
    return {
        "consensus": ["保留午睡总时长不变", "调整前提前一周告知家长", "午睡巡视人员按原标准到位"],
        "disagreements": [{"between": ["teacher", "safety"], "point": "餐后过渡时间缩短后能否避免盥洗室拥挤，仍需核对"},
                          {"between": ["health", "parent"], "point": "提前入睡是否影响部分幼儿的进餐与消化"}],
        "risks": ["过渡环节拥挤", "部分幼儿入睡困难", "保育员清扫时间被压缩"],
        "options": [{"name": "先小范围试行", "pros": "选 2 个班试行两周，用巡查数据说话", "cons": "全园作息短期不统一"},
                    {"name": "全园同步调整", "pros": "管理统一、家长沟通一次完成", "cons": "风险集中暴露"},
                    {"name": "暂不调整", "pros": "零风险", "cons": "冬季作息问题仍在"}],
    }
