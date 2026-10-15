"""生成 8 个原创卡通动物占位形象（SVG），每个 9 种表情。管理端可随时上传正式形象替换。
用法：python scripts/gen_avatars.py assets/avatars"""
import sys
from pathlib import Path

ANIMALS = {
    "humiao": {"cn": "护苗·小熊", "face": "#C8935E", "inner": "#F1D6B4", "ear": "bear", "acc": "#7A4B26", "bg": "#FBE9D7"},
    "mingli": {"cn": "明理·猫头鹰", "face": "#9C7A5A", "inner": "#F3E3C8", "ear": "owl", "acc": "#4E3A28", "bg": "#EFE6D8"},
    "xiaobu": {"cn": "小步·小乌龟", "face": "#8CC79A", "inner": "#E3F4DF", "ear": "turtle", "acc": "#3E8A52", "bg": "#E5F4E5"},
    "weishi": {"cn": "小卫士·柴犬", "face": "#E3A35A", "inner": "#FFF3E2", "ear": "shiba", "acc": "#A8641F", "bg": "#FCEBD6"},
    "xiaoyi": {"cn": "小医·小白兔", "face": "#FFFFFF", "inner": "#FCE4EC", "ear": "rabbit", "acc": "#E68AA6", "bg": "#FDECF1"},
    "xiaoshi": {"cn": "小师·小熊猫", "face": "#D2693A", "inner": "#FFF4EA", "ear": "redpanda", "acc": "#6B2E14", "bg": "#FBE4D8"},
    "xiaojia": {"cn": "小家·小袋鼠", "face": "#D9AE79", "inner": "#F8E8D2", "ear": "kangaroo", "acc": "#8A6236", "bg": "#F7EBDC"},
    "xiaodun": {"cn": "小盾·小象", "face": "#AFC3DA", "inner": "#E7EEF6", "ear": "elephant", "acc": "#5D7EA8", "bg": "#E6EEF7"},
}
EMOTIONS = ["happy", "cheer", "doubt", "surprised", "sad", "sleep", "angry", "support", "bye", "front"]


def ears(kind, a):
    f, i, acc = a["face"], a["inner"], a["acc"]
    if kind == "bear":
        return f'<circle cx="62" cy="62" r="24" fill="{f}"/><circle cx="62" cy="62" r="12" fill="{i}"/><circle cx="194" cy="62" r="24" fill="{f}"/><circle cx="194" cy="62" r="12" fill="{i}"/>'
    if kind == "owl":
        return f'<path d="M58 70 L70 26 L98 58 Z" fill="{acc}"/><path d="M198 70 L186 26 L158 58 Z" fill="{acc}"/>'
    if kind == "turtle":
        return f'<path d="M48 120 Q128 -10 208 120" fill="{acc}" opacity=".9"/><path d="M80 70 L128 50 L176 70 M100 96 L128 58 L156 96" stroke="#CDEBC9" stroke-width="5" fill="none"/>'
    if kind == "shiba":
        return f'<path d="M50 96 L60 30 L108 64 Z" fill="{f}"/><path d="M62 84 L66 46 L94 66 Z" fill="{i}"/><path d="M206 96 L196 30 L148 64 Z" fill="{f}"/><path d="M194 84 L190 46 L162 66 Z" fill="{i}"/>'
    if kind == "rabbit":
        return f'<ellipse cx="96" cy="40" rx="18" ry="50" fill="{f}" stroke="#F0D5DD" stroke-width="3"/><ellipse cx="96" cy="44" rx="8" ry="36" fill="{i}"/><ellipse cx="160" cy="40" rx="18" ry="50" fill="{f}" stroke="#F0D5DD" stroke-width="3"/><ellipse cx="160" cy="44" rx="8" ry="36" fill="{i}"/>'
    if kind == "redpanda":
        return f'<path d="M48 92 L58 34 L104 60 Z" fill="{f}"/><path d="M60 80 L64 46 L90 62 Z" fill="#FFFFFF"/><path d="M208 92 L198 34 L152 60 Z" fill="{f}"/><path d="M196 80 L192 46 L166 62 Z" fill="#FFFFFF"/>'
    if kind == "kangaroo":
        return f'<ellipse cx="84" cy="42" rx="16" ry="38" fill="{f}" transform="rotate(-16 84 42)"/><ellipse cx="84" cy="46" rx="7" ry="26" fill="{i}" transform="rotate(-16 84 46)"/><ellipse cx="172" cy="42" rx="16" ry="38" fill="{f}" transform="rotate(16 172 42)"/><ellipse cx="172" cy="46" rx="7" ry="26" fill="{i}" transform="rotate(16 172 46)"/>'
    if kind == "elephant":
        return f'<ellipse cx="44" cy="128" rx="40" ry="52" fill="{f}" stroke="{acc}" stroke-width="3"/><ellipse cx="48" cy="128" rx="24" ry="34" fill="#F6C9D3"/><ellipse cx="212" cy="128" rx="40" ry="52" fill="{f}" stroke="{acc}" stroke-width="3"/><ellipse cx="208" cy="128" rx="24" ry="34" fill="#F6C9D3"/>'
    return ""


def eyes(emo):
    if emo in ("happy", "support"):
        return '<path d="M86 124 Q98 110 110 124" stroke="#2B2B2B" stroke-width="6" fill="none" stroke-linecap="round"/><path d="M146 124 Q158 110 170 124" stroke="#2B2B2B" stroke-width="6" fill="none" stroke-linecap="round"/>'
    if emo == "sleep":
        return '<path d="M86 122 Q98 132 110 122" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M146 122 Q158 132 170 122" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/>'
    if emo == "angry":
        return '<path d="M82 106 L112 116" stroke="#2B2B2B" stroke-width="6" stroke-linecap="round"/><path d="M174 106 L144 116" stroke="#2B2B2B" stroke-width="6" stroke-linecap="round"/><circle cx="98" cy="128" r="9" fill="#2B2B2B"/><circle cx="158" cy="128" r="9" fill="#2B2B2B"/>'
    if emo == "bye":
        return '<circle cx="98" cy="122" r="11" fill="#2B2B2B"/><circle cx="102" cy="117" r="4" fill="#fff"/><path d="M146 124 Q158 110 170 124" stroke="#2B2B2B" stroke-width="6" fill="none" stroke-linecap="round"/>'
    r = 14 if emo == "surprised" else 11
    s = '<circle cx="98" cy="122" r="{r}" fill="#2B2B2B"/><circle cx="103" cy="116" r="4.5" fill="#fff"/><circle cx="158" cy="122" r="{r}" fill="#2B2B2B"/><circle cx="163" cy="116" r="4.5" fill="#fff"/>'.format(r=r)
    if emo == "sad":
        s += '<path d="M80 104 L110 98" stroke="#2B2B2B" stroke-width="4" stroke-linecap="round"/><path d="M176 104 L146 98" stroke="#2B2B2B" stroke-width="4" stroke-linecap="round"/><path d="M88 138 Q84 152 90 158 Q96 152 92 138" fill="#7EC8F2"/>'
    return s


def mouth(emo):
    return {
        "happy": '<path d="M110 156 Q128 176 146 156 Z" fill="#C2413A"/>',
        "cheer": '<path d="M112 154 Q128 168 144 154" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/>',
        "doubt": '<path d="M114 160 Q124 154 134 160 Q142 165 146 158" stroke="#2B2B2B" stroke-width="4" fill="none" stroke-linecap="round"/>',
        "surprised": '<ellipse cx="128" cy="162" rx="9" ry="12" fill="#C2413A"/>',
        "sad": '<path d="M112 166 Q128 152 144 166" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/>',
        "sleep": '<ellipse cx="128" cy="160" rx="6" ry="4" fill="#C2413A"/>',
        "angry": '<path d="M112 166 Q128 154 144 166" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/>',
        "support": '<path d="M112 154 Q128 170 144 154" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/>',
        "bye": '<path d="M110 154 Q128 174 146 154 Z" fill="#C2413A"/>',
        "front": '<path d="M112 154 Q128 168 144 154" stroke="#2B2B2B" stroke-width="5" fill="none" stroke-linecap="round"/>',
    }[emo]


def extra(emo, a):
    acc = a["acc"]
    return {
        "doubt": f'<text x="200" y="64" font-size="46" font-weight="700" fill="{acc}" font-family="Arial">?</text>',
        "surprised": f'<text x="204" y="64" font-size="46" font-weight="700" fill="#F56D01" font-family="Arial">!</text>',
        "sleep": f'<text x="190" y="58" font-size="28" font-weight="700" fill="{acc}" font-family="Arial">z</text><text x="208" y="38" font-size="20" font-weight="700" fill="{acc}" font-family="Arial">z</text>',
        "angry": '<path d="M196 40 l10 10 m0 -10 l-10 10 M210 54 l10 10 m0 -10 l-10 10" stroke="#E04A3A" stroke-width="5" stroke-linecap="round"/>',
        "support": '<path d="M128 218 C 110 200, 92 214, 108 228 L128 244 L148 228 C 164 214, 146 200, 128 218 Z" fill="#E8546A"/>',
        "cheer": '<path d="M200 44 l6 -14 l6 14 l14 6 l-14 6 l-6 14 l-6 -14 l-14 -6 Z" fill="#F7C23B"/>',
        "bye": f'<ellipse cx="216" cy="168" rx="16" ry="22" fill="{a["face"]}" stroke="{acc}" stroke-width="3" transform="rotate(20 216 168)"/>',
    }.get(emo, "")


def svg(key, a, emo):
    face = a["face"]
    muzzle = f'<ellipse cx="128" cy="156" rx="40" ry="28" fill="{a["inner"]}"/>'
    nose = f'<ellipse cx="128" cy="144" rx="10" ry="7" fill="{a["acc"]}"/>'
    if a["ear"] == "owl":
        muzzle = '<path d="M120 140 L136 140 L128 156 Z" fill="#F2A33A"/>'
        nose = f'<circle cx="98" cy="122" r="26" fill="{a["inner"]}"/><circle cx="158" cy="122" r="26" fill="{a["inner"]}"/>'
    if a["ear"] == "elephant":
        muzzle = f'<path d="M116 138 Q112 200 132 212 Q146 214 142 200 Q134 186 140 140 Z" fill="{face}" stroke="{a["acc"]}" stroke-width="3"/>'
        nose = ""
    if a["ear"] == "redpanda":
        muzzle = '<ellipse cx="128" cy="156" rx="42" ry="28" fill="#FFF4EA"/><ellipse cx="98" cy="112" rx="18" ry="12" fill="#FFF4EA"/><ellipse cx="158" cy="112" rx="18" ry="12" fill="#FFF4EA"/>'
    order = (nose + muzzle) if a["ear"] == "owl" else (muzzle + nose)
    blush = '<ellipse cx="78" cy="150" rx="12" ry="7" fill="#F49AA6" opacity=".55"/><ellipse cx="178" cy="150" rx="12" ry="7" fill="#F49AA6" opacity=".55"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 256 256">'
            f'<title>{a["cn"]}</title>'
            f'<circle cx="128" cy="134" r="118" fill="{a["bg"]}"/>{ears(a["ear"], a)}'
            f'<ellipse cx="128" cy="132" rx="86" ry="80" fill="{face}" stroke="{a["acc"]}" stroke-opacity=".35" stroke-width="3"/>'
            f'{order}{eyes(emo)}{blush}{mouth(emo)}{extra(emo, a)}</svg>')


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/avatars")
    for key, a in ANIMALS.items():
        d = out / key
        d.mkdir(parents=True, exist_ok=True)
        for emo in EMOTIONS:
            (d / f"{emo}.svg").write_text(svg(key, a, emo), encoding="utf-8")
    print("ok", len(ANIMALS) * len(EMOTIONS))
