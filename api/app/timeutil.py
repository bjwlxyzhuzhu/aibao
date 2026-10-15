"""时间工具：统一按北京时间；演示时可用 DEMO_TODAY 固定日期（时刻仍取真实时间）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from .config import DEMO_TODAY

CST = timezone(timedelta(hours=8))


def now_local() -> datetime:
    n = datetime.now(CST).replace(tzinfo=None, microsecond=0)
    if DEMO_TODAY:
        d = date.fromisoformat(DEMO_TODAY)
        n = n.replace(year=d.year, month=d.month, day=d.day)
    return n


def today() -> date:
    return now_local().date()


WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def hm(t: str) -> int:
    h, m = t.strip().split(":")
    return int(h) * 60 + int(m)


# ---------- 工作时间计时（4.6：只算校历内工作日 7:30–18:00） ----------
WORK_START = 7 * 60 + 30
WORK_END = 18 * 60


def is_workday(d: date, holidays: set[date] | None = None) -> bool:
    if d.weekday() >= 5:
        return False
    return not (holidays and d in holidays)


def add_work_minutes(start: datetime, minutes: int, holidays: set[date] | None = None) -> datetime:
    """从 start 起累加 minutes 个工作分钟，夜间、周末、假期不计时。"""
    cur = start
    left = minutes
    for _ in range(400):
        if not is_workday(cur.date(), holidays):
            cur = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time()) + timedelta(minutes=WORK_START)
            continue
        m = cur.hour * 60 + cur.minute
        if m < WORK_START:
            cur = cur.replace(hour=7, minute=30, second=0)
            m = WORK_START
        if m >= WORK_END:
            cur = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time()) + timedelta(minutes=WORK_START)
            continue
        avail = WORK_END - m
        if left <= avail:
            return cur + timedelta(minutes=left)
        left -= avail
        cur = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time()) + timedelta(minutes=WORK_START)
    return cur


def work_minutes_between(a: datetime, b: datetime, holidays: set[date] | None = None) -> int:
    if b <= a:
        return 0
    total = 0
    d = a.date()
    while d <= b.date():
        if is_workday(d, holidays):
            day_s = datetime.combine(d, datetime.min.time()) + timedelta(minutes=WORK_START)
            day_e = datetime.combine(d, datetime.min.time()) + timedelta(minutes=WORK_END)
            s, e = max(a, day_s), min(b, day_e)
            if e > s:
                total += int((e - s).total_seconds() // 60)
        d += timedelta(days=1)
    return total
