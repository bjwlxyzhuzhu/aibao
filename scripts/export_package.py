"""导出参赛代码包：自动排除 .env、数据、依赖目录与测试照片，并扫描密钥与园方名单中的真实教职工姓名，命中即中止。
用法：python scripts/export_package.py  → dist_package/爱宝园务大脑_源代码包.zip"""
import re
import sqlite3
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv", "node_modules", "data", "dist", "__pycache__", ".git", "dist_package", "fixtures", ".claude"}
EXCLUDE_FILES = {".env", "import_template_2026autumn.xlsx"}  # 园方名单含真实教师姓名，不进参赛包
EXCLUDE_SUFFIX = {".db", ".db-wal", ".db-shm", ".pyc"}
KEY_PATTERNS = [re.compile(p) for p in (r"sk-[A-Za-z0-9]{20,}", r"LLM_API_KEY\s*=\s*(?!__)[A-Za-z0-9_\-]{16,}", r"AKIA[0-9A-Z]{16}",
                                        r"-----BEGIN (RSA |EC )?PRIVATE KEY-----")]
ROSTER_XLSX = ROOT / "api" / "seed_data" / "import_template_2026autumn.xlsx"
ROSTER_DB = ROOT / "api" / "data" / "aibao.db"
BINARY_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".onnx", ".bin", ".woff", ".woff2", ".ttf", ".mp3", ".mp4", ".wav", ".zip"}
POSITION_RE = re.compile(r"(园长|主任|教师|保育员|班长|管理员|财务室|保健室|伙管室|待定|空缺)$")  # 岗位词不是姓名


def roster_names() -> set[str]:
    """园方名单姓名：导入模板「教职工名单」的姓名列 + 已导入数据库的 staff 表（两者有其一即可）。"""
    names: set[str] = set()
    if ROSTER_XLSX.exists():
        import openpyxl
        wb = openpyxl.load_workbook(ROSTER_XLSX, read_only=True, data_only=True)
        for ws in wb.worksheets:
            if not ws.title.startswith("教职工名单"):
                continue
            rows = ws.iter_rows(values_only=True)
            header = [str(h or "").strip() for h in next(rows, [])]
            if "姓名" in header:
                col = header.index("姓名")
                names |= {str(r[col]).strip() for r in rows if col < len(r) and r[col]}
    if ROSTER_DB.exists():
        with sqlite3.connect(f"file:{ROSTER_DB}?mode=ro", uri=True) as con:
            names |= {r[0].strip() for r in con.execute("SELECT name FROM staff") if r[0]}
    return {n for n in names if 2 <= len(n) <= 6 and re.fullmatch(r"[一-龥·]+", n) and not POSITION_RE.search(n)}


def files():
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if p.is_dir() or any(part in EXCLUDE_DIRS for part in rel.parts) or p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIX:
            continue
        if p.name.startswith("_") and p.suffix in (".png", ".jpg", ".txt"):
            continue
        yield p, rel


def main():
    bad = []
    items = list(files())
    for p, rel in items:
        if p.suffix.lower() in (".py", ".ts", ".tsx", ".md", ".yml", ".yaml", ".json", ".example", ".sh", ".txt", ".conf", ""):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for pat in KEY_PATTERNS:
                if pat.search(text):
                    bad.append(f"{rel}: {pat.pattern}")
    if bad:
        print("发现疑似密钥，已中止：\n" + "\n".join(bad))
        sys.exit(1)
    names = sorted(roster_names(), key=len, reverse=True)
    if not names:
        print("提示：未找到园方名单（xlsx / 数据库），跳过姓名扫描")
    for p, rel in items:
        text = str(rel) + "\n" + ("" if p.suffix.lower() in BINARY_SUFFIX else p.read_text(encoding="utf-8", errors="ignore"))
        hit = [n for n in names if n in text]
        if hit:
            bad.append(f"{rel}: {'、'.join(hit)}")
    if bad:
        print("发现园方名单中的真实教职工姓名，已中止（请改为虚构姓名或岗位称谓）：\n" + "\n".join(bad))
        sys.exit(1)
    out = ROOT / "dist_package" / "爱宝园务大脑_源代码包.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p, rel in items:
            z.write(p, Path("aibao-brain") / rel)
    print(f"已导出 {len(items)} 个文件 → {out}（密钥扫描、名单姓名扫描通过，名单 {len(names)} 人）")


if __name__ == "__main__":
    main()
