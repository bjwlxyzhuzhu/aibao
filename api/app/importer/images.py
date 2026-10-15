"""园徽多尺寸生成与取色；吉祥物 / 智能体形象导入（真人人脸检测即拒绝）。图片只存在园方服务器，不发送给模型。"""
from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..config import DATA_DIR
from ..gateway.redact_image import _detect_haar, _detect_yunet, YUNET_PATH

BRAND_DIR = DATA_DIR / "brand"
AVATAR_DIR = DATA_DIR / "avatars"
SIZES = {"logo_header": 128, "logo_login": 512, "favicon": 64, "pdf_header": 256}


def remove_white_bg(im: Image.Image, tol: int = 18) -> Image.Image:
    """从四边泛洪去掉近白 / 近纯色背景（JPG 吉祥物用）。"""
    rgb = np.array(im.convert("RGB"))
    h, w = rgb.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8) | cv2.FLOODFILL_FIXED_RANGE
    for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1)]:
        cv2.floodFill(rgb.copy(), mask, (x, y), 0, (tol,) * 3, (tol,) * 3, flags)
    alpha = 255 - mask[1:-1, 1:-1]
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    out = np.dstack([rgb, alpha])
    return Image.fromarray(out, "RGBA")


def palette(im: Image.Image, n: int = 5) -> list[str]:
    small = im.convert("RGBA").resize((96, 96))
    px = [p[:3] for p in small.getdata() if p[3] > 200 and not (p[0] > 235 and p[1] > 235 and p[2] > 235)]
    if not px:
        return []
    tmp = Image.new("RGB", (len(px), 1))
    tmp.putdata(px)
    q = tmp.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: n * 3]
    counts = sorted(q.getcolors(), reverse=True)
    return ["#%02X%02X%02X" % tuple(pal[i * 3:i * 3 + 3]) for _, i in counts]


def process_logo(src: Path, version: int, strip_bg: bool) -> dict:
    im = Image.open(src)
    if im.size[0] < 256 or im.size[1] < 256:
        raise ValueError(f"园徽尺寸过小（{im.size[0]}×{im.size[1]}），建议正方形且不小于 512px")
    if strip_bg:
        im = remove_white_bg(im)
    im = im.convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    out = {}
    d = BRAND_DIR / f"v{version}"
    d.mkdir(parents=True, exist_ok=True)
    for kind, size in SIZES.items():
        c = im.copy()
        c.thumbnail((size, size), Image.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(c, ((size - c.size[0]) // 2, (size - c.size[1]) // 2), c)
        p = d / f"{kind}.png"
        canvas.save(p)
        out[kind] = str(p)
    shutil.copy(src, d / f"source{src.suffix}")
    return {"paths": out, "palette": palette(im)}


def has_real_face(path: Path) -> int:
    """真人照片检测：YuNet（真人人脸置信度高）；无 YuNet 模型时用 Haar 正脸检测且要求肤色区域。"""
    if path.suffix.lower() == ".svg":
        text = path.read_text(encoding="utf-8", errors="ignore")
        return 1 if "<image" in text else 0  # 矢量图内嵌位图时一律按可疑处理
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解析图片")
    if YUNET_PATH.exists():
        return len(_detect_yunet(img))
    faces = _detect_haar(img)
    real = 0
    for (x, y, w, h) in faces:
        roi = cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2YCrCb)
        skin = cv2.inRange(roi, (0, 135, 85), (255, 173, 127))
        if skin.mean() / 255 > 0.45 and w > img.shape[1] / 12:
            real += 1
    return real


def save_avatar(src: Path, agent: str, view: str, version: int, strip_bg: bool) -> str:
    im = Image.open(src)
    if strip_bg or src.suffix.lower() in (".jpg", ".jpeg"):
        im = remove_white_bg(im)
    im = im.convert("RGBA")
    im.thumbnail((1024, 1024), Image.LANCZOS)
    d = AVATAR_DIR / agent / f"v{version}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{view}.png"
    im.save(p)
    return str(p)
