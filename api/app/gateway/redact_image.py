"""照片脱敏：检测并模糊所有人脸（YuNet 优先，Haar 级联兜底），重新编码以去掉 EXIF/GPS。全部本地执行。"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..config import BASE_DIR

YUNET_PATH = BASE_DIR / "models" / "face_detection_yunet_2023mar.onnx"
_yunet = None


def _detect_yunet(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    global _yunet
    if not YUNET_PATH.exists():
        return []
    h, w = img.shape[:2]
    if _yunet is None:
        # 以内存缓冲加载，避免 OpenCV 在中文路径下读文件失败
        buf = np.frombuffer(YUNET_PATH.read_bytes(), dtype=np.uint8)
        _yunet = cv2.FaceDetectorYN.create("onnx", buf, np.empty(0, np.uint8), (w, h), 0.6, 0.3, 5000)
    _yunet.setInputSize((w, h))
    _, faces = _yunet.detect(img)
    if faces is None:
        return []
    return [tuple(int(v) for v in f[:4]) for f in faces]


_haar = None
_haar_profile = None


def _detect_haar(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    global _haar, _haar_profile
    if not hasattr(cv2, "CascadeClassifier"):  # OpenCV 5 已移除 Haar；此时必须有 YuNet
        if not YUNET_PATH.exists():
            raise RuntimeError("人脸检测模型缺失（YuNet），拒绝发送")
        return []
    if _haar is None:
        base = Path(cv2.data.haarcascades)
        _haar = cv2.CascadeClassifier(str(base / "haarcascade_frontalface_default.xml"))
        _haar_profile = cv2.CascadeClassifier(str(base / "haarcascade_profileface.xml"))
    gray = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    minside = max(24, min(img.shape[:2]) // 40)
    out = []
    for c in (_haar, _haar_profile):
        if c is None or c.empty():
            continue
        for (x, y, w, h) in c.detectMultiScale(gray, 1.1, 5, minSize=(minside, minside)):
            out.append((int(x), int(y), int(w), int(h)))
    return out


def blur_faces(img: np.ndarray) -> tuple[np.ndarray, int, str]:
    boxes = _detect_yunet(img)
    engine = "YuNet" if YUNET_PATH.exists() else "Haar"
    if engine == "Haar" or len(boxes) == 0:
        boxes += _detect_haar(img)  # 兜底：YuNet 未检出时再用 Haar 复检（若可用）
    h, w = img.shape[:2]
    out = img.copy()
    merged: list[tuple[int, int, int, int]] = []
    for (x, y, bw, bh) in boxes:
        pad = int(max(bw, bh) * 0.35)
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        if x1 - x0 < 4 or y1 - y0 < 4:
            continue
        if any(abs(x0 - m[0]) < bw // 2 and abs(y0 - m[1]) < bh // 2 for m in merged):
            continue
        merged.append((x0, y0, x1, y1))
        roi = out[y0:y1, x0:x1]
        k = max(31, ((x1 - x0) // 2) | 1)
        small = cv2.resize(roi, (max(1, (x1 - x0) // 12), max(1, (y1 - y0) // 12)), interpolation=cv2.INTER_LINEAR)
        roi = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        out[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)
    return out, len(merged), engine


def redact_image_file(src: Path, dst: Path, max_side: int = 1600) -> dict:
    """返回 {faces, engine, width, height}；任何失败都抛异常，调用方据此拒发。"""
    data = np.fromfile(str(src), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解析图片")
    h, w = img.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    out, n, engine = blur_faces(img)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 88])  # 重新编码 = 去掉全部 EXIF/GPS
    if not ok:
        raise ValueError("图片编码失败")
    dst.parent.mkdir(parents=True, exist_ok=True)
    buf.tofile(str(dst))
    return {"faces": n, "engine": engine, "width": out.shape[1], "height": out.shape[0]}
