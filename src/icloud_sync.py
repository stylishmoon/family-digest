"""Ghi event vào iCloud Calendar qua CalDAV.

Yêu cầu:
- APPLE_ID          : Apple ID (email)
- APPLE_APP_PASSWORD: app-specific password (tạo tại appleid.apple.com)
- Calendar tên đúng như config (tạo sẵn trên iPhone, share với vợ).

UID xác định (deterministic) -> chạy lại không tạo trùng, sửa config là event tự cập nhật.
"""
import datetime as dt
import hashlib
from zoneinfo import ZoneInfo

import caldav
from icalendar import Alarm, Calendar, Event


def connect(apple_id: str, app_password: str, calendar_name: str) -> caldav.Calendar:
    client = caldav.DAVClient(
        url="https://caldav.icloud.com/", username=apple_id, password=app_password
    )
    principal = client.principal()
    for cal in principal.calendars():
        if str(cal.name).strip() == calendar_name:
            return cal
    names = [str(c.name) for c in principal.calendars()]
    raise RuntimeError(
        f"Không tìm thấy calendar '{calendar_name}'. Calendar hiện có: {names}"
    )


def _uid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16] + "@family-digest"


def _build_ics(event: Event) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//family-digest//VN//")
    cal.add("version", "2.0")
    cal.add_component(event)
    return cal.to_ical()


def _with_alarm(ev: Event, minutes_before: int) -> Event:
    alarm = Alarm()
    alarm.add("action", "DISPLAY")
    alarm.add("description", "Nhắc nhở")
    alarm.add("trigger", dt.timedelta(minutes=-minutes_before))
    ev.add_component(alarm)
    return ev


def upsert(cal: caldav.Calendar, event: Event) -> None:
    uid = str(event["uid"])
    try:
        existing = cal.event_by_uid(uid)
        existing.delete()
    except Exception:
        pass
    cal.save_event(_build_ics(event).decode())


def upsert_recurring_activity(cal: caldav.Calendar, act: dict, tz: ZoneInfo) -> None:
    """Lịch cố định hàng tuần (RRULE) trong khoảng course_start..course_end."""
    start_date = dt.date.fromisoformat(str(act["course_start"]))
    end_date = dt.date.fromisoformat(str(act["course_end"]))
    h1, m1 = map(int, act["start_time"].split(":"))
    h2, m2 = map(int, act["end_time"].split(":"))

    # DTSTART = lần đầu tiên rơi vào một ngày trong `days`
    day_idx = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
    wanted = sorted(day_idx[d] for d in act["days"])
    d = start_date
    while d.weekday() not in wanted:
        d += dt.timedelta(days=1)

    ev = Event()
    ev.add("uid", _uid("activity", act["name"]))
    ev.add("summary", act["name"])
    if act.get("location"):
        ev.add("location", act["location"])
    ev.add("dtstart", dt.datetime(d.year, d.month, d.day, h1, m1, tzinfo=tz))
    ev.add("dtend", dt.datetime(d.year, d.month, d.day, h2, m2, tzinfo=tz))
    ev.add("rrule", {
        "freq": "weekly",
        "byday": act["days"],
        # RFC 5545: UNTIL phải ở UTC khi DTSTART có TZID
        "until": dt.datetime(end_date.year, end_date.month, end_date.day,
                             23, 59, tzinfo=tz).astimezone(dt.timezone.utc),
    })
    _with_alarm(ev, int(act.get("alert_minutes_before", 30)))
    upsert(cal, ev)

    # Nhắc trước khi hết khóa
    remind_days = int(act.get("remind_course_end_days", 0))
    if remind_days > 0:
        rd = end_date - dt.timedelta(days=remind_days)
        rev = Event()
        rev.add("uid", _uid("course-end-reminder", act["name"]))
        rev.add("summary", f"⏳ {act['name']}: còn {remind_days} ngày hết khóa "
                           f"({end_date.strftime('%d/%m')})")
        rev.add("dtstart", rd)  # all-day
        rev.add("dtend", rd + dt.timedelta(days=1))
        _with_alarm(rev, 0)
        upsert(cal, rev)

    # Đánh dấu ngày kết thúc khóa
    fev = Event()
    fev.add("uid", _uid("course-end", act["name"]))
    fev.add("summary", f"🏁 Kết thúc khóa: {act['name']}")
    fev.add("dtstart", end_date)
    fev.add("dtend", end_date + dt.timedelta(days=1))
    upsert(cal, fev)


def upsert_parsed_event(cal: caldav.Calendar, e: dict, source_text: str,
                        tz: ZoneInfo) -> str:
    """Event trích từ thông báo group. Trả về UID."""
    uid = _uid("announce", e["date"], e.get("time") or "", e["title"])
    ev = Event()
    ev.add("uid", uid)
    ev.add("summary", e["title"])
    note = e.get("note") or ""
    ev.add("description", f"{note}\n\n— Nguồn (forward):\n{source_text}".strip())
    date = dt.date.fromisoformat(e["date"])
    if e.get("time"):
        h, m = map(int, e["time"].split(":"))
        start = dt.datetime(date.year, date.month, date.day, h, m, tzinfo=tz)
        if e.get("end_time"):
            h2, m2 = map(int, e["end_time"].split(":"))
            end = dt.datetime(date.year, date.month, date.day, h2, m2, tzinfo=tz)
        else:
            end = start + dt.timedelta(hours=1)
        ev.add("dtstart", start)
        ev.add("dtend", end)
        _with_alarm(ev, 60)
    else:
        ev.add("dtstart", date)
        ev.add("dtend", date + dt.timedelta(days=1))
        _with_alarm(ev, 0)
    upsert(cal, ev)
    return uid


def upsert_digest(cal: caldav.Calendar, day: dt.date, digest_time: str,
                  body: str, alert_min: int, tz: ZoneInfo) -> None:
    h, m = map(int, digest_time.split(":"))
    ev = Event()
    ev.add("uid", _uid("digest", day.isoformat()))
    ev.add("summary", "📋 Tóm tắt hôm nay")
    ev.add("description", body)
    start = dt.datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
    ev.add("dtstart", start)
    ev.add("dtend", start + dt.timedelta(minutes=15))
    _with_alarm(ev, alert_min)
    upsert(cal, ev)
