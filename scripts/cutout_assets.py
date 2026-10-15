"""一次性素材处理：从园方吉祥物设定图中抠出全身像与园徽（需 rembg + onnxruntime==1.20.1）。"""
import sys
from pathlib import Path
from rembg import remove, new_session
from PIL import Image

root = Path(sys.argv[1])
s = new_session("u2net")
jobs = {
    "avatars/aibao/hero_raw.png": "avatars/aibao/front.png",
    "avatars/xingbao/front_raw.png": "avatars/xingbao/front.png",
    "avatars/xingbao/side_raw.png": "avatars/xingbao/side.png",
    "avatars/xingbao/back_raw.png": "avatars/xingbao/back.png",
    "avatars/aibao/mini_raw.png": "avatars/aibao/mini.png",
    "brand/logo_mark_raw.png": "brand/logo_mark.png",
}
for a, b in jobs.items():
    im = Image.open(root / a).convert("RGB")
    if im.size[0] < 400:
        im = im.resize((im.size[0] * 3, im.size[1] * 3), Image.LANCZOS)
    out = remove(im, session=s)
    out = out.crop(out.getbbox())
    out.save(root / b)
    print(b, out.size, flush=True)
