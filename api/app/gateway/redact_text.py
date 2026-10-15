"""文字脱敏：教职工姓名 → 岗位代号；幼儿姓名 → 编号；手机号、身份证号、住址 → 占位符；健康明细 → 类别。"""
from __future__ import annotations

import re

ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
LANDLINE_RE = re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)")
ADDR_RE = re.compile(r"[一-龥]{2,12}(?:路|街|巷|大道)\d{1,4}号(?:[一-龥\d]{0,10}(?:小区|单元|栋|楼|室))*")
COMMUNITY_RE = re.compile(r"[一-龥]{2,8}(?:小区|花园|家园|公寓)\d{1,3}(?:号楼|栋|单元)[\d\-]*(?:室)?")
TEMP_RE = re.compile(r"(体温|发烧|发热)\s*[:：]?\s*3[7-9](?:\.\d)?\s*(?:度|℃)?")


class TextRedactor:
    def __init__(self, staff: dict[str, str], children: dict[str, str]):
        # 长名字优先，避免"王小"先替换掉"王小雨"
        self.staff = dict(sorted(staff.items(), key=lambda kv: -len(kv[0])))
        self.children = dict(sorted(children.items(), key=lambda kv: -len(kv[0])))

    @classmethod
    def from_db(cls, db) -> "TextRedactor":
        from sqlalchemy import select
        from ..models import Child, Klass, Staff
        from ..security import decrypt
        staff = {s.name: f"【教职工{s.id:03d}】" for s in db.scalars(select(Staff)) if s.name and len(s.name) >= 2}
        children = {}
        for c in db.scalars(select(Child).where(Child.status == "在园")):
            n = decrypt(c.name_encrypted)
            if n and len(n) >= 2:
                children[n] = f"【幼儿{c.code}】"
        return cls(staff, children)

    def redact(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        reps: list[tuple[str, str]] = []
        out = text or ""

        def sub(regex: re.Pattern, label: str, s: str) -> str:
            def f(m: re.Match) -> str:
                reps.append((label, f"[{label}]"))
                return f"[{label}]"
            return regex.sub(f, s)

        out = sub(ID_RE, "身份证号", out)
        out = sub(PHONE_RE, "手机号", out)
        out = sub(LANDLINE_RE, "电话", out)
        out = sub(ADDR_RE, "住址", out)
        out = sub(COMMUNITY_RE, "住址", out)
        out = TEMP_RE.sub(lambda m: (reps.append(("健康明细", "[体温异常]")) or "[体温异常]"), out)
        for name, code in self.children.items():
            if name in out:
                out = out.replace(name, code)
                reps.append(("幼儿姓名", code))
        for name, code in self.staff.items():
            if name in out:
                out = out.replace(name, code)
                reps.append(("教职工姓名", code))
        return out, reps

    def restore(self, text: str) -> str:
        out = text or ""
        for name, code in self.staff.items():
            out = out.replace(code, name)
        return out
