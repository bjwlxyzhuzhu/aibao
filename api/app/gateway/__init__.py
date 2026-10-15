"""脱敏网关：所有云端模型调用的必经之路。失败即拒发，不允许绕过。"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from .redact_text import TextRedactor
from .redact_image import redact_image_file


class GatewayError(RuntimeError):
    """网关处理失败：调用方必须中止发送。"""


@dataclass(frozen=True)
class RedactedPayload:
    """只有网关能构造的"已脱敏"载荷；LLM 客户端只接受这个类型。"""
    call_id: str
    text: str
    image_paths: tuple[str, ...] = ()
    replacements: tuple = field(default_factory=tuple)
    faces: int = 0


def pass_through_gateway(db, text: str, image_paths: list[str] | None = None, agent: str = "") -> RedactedPayload:
    from ..models import RedactionLog
    try:
        red = TextRedactor.from_db(db)
        after, reps = red.redact(text)
    except Exception as e:  # noqa: BLE001
        raise GatewayError(f"文字脱敏失败：{e}") from e
    faces = 0
    out_imgs: list[str] = []
    for p in image_paths or []:
        if "redacted" not in p.replace("\\", "/"):
            raise GatewayError("图片未经过人脸打码，拒绝发送")
        out_imgs.append(p)
    call_id = uuid.uuid4().hex[:16]
    db.add(RedactionLog(call_id=call_id, agent=agent, before_hash=hashlib.sha256(text.encode()).hexdigest(),
                        before_preview=text[:2000], after_text=after[:4000], faces=faces,
                        replacements_json=[{"from_type": r[0], "to": r[1]} for r in reps]))
    db.flush()
    return RedactedPayload(call_id=call_id, text=after, image_paths=tuple(out_imgs), replacements=tuple(reps), faces=faces)


__all__ = ["GatewayError", "RedactedPayload", "pass_through_gateway", "redact_image_file", "TextRedactor"]
