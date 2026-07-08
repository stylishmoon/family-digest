"""Điều phối: kéo Telegram -> parse -> ghi iCloud -> tạo digest sáng.

Chạy bằng GitHub Actions (xem .github/workflows/daily.yml).
Env cần có: TELEGRAM_BOT_TOKEN, APPLE_ID, APPLE_APP_PASSWORD, (tùy chọn) ANTHROPIC_API_KEY
"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, os.path.dirname(__file__))
import icloud_sync
import parser as msg_parser
import telegram_ingest


def load_config() -> dict:
    with open("config/schedule.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()
    tz = ZoneInfo(cfg.get("timezone", "Asia/Ho_Chi_Minh"))
    now = dt.datetime.now(tz)
    today = now.date()

    state = telegram_ingest.load_state()

    # 1. Kéo tin mới từ Telegram bot
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    new_msgs = telegram_ingest.fetch_new_messages(token, state)
    print(f"[info] {len(new_msgs)} tin nhắn mới từ Telegram")

    # 2. Kết nối iCloud
    cal = icloud_sync.connect(
        os.environ["APPLE_ID"],
        os.environ["APPLE_APP_PASSWORD"],
        cfg["calendar_name"],
    )

    # 3. Đồng bộ lịch cố định (idempotent — chạy lại không tạo trùng)
    for act in cfg.get("activities", []):
        icloud_sync.upsert_recurring_activity(cal, act, tz)
    print(f"[info] Đã đồng bộ {len(cfg.get('activities', []))} hoạt động cố định")

    # 4. Parse tin mới -> tạo event, gom vào pending cho digest sáng hôm sau
    for msg in new_msgs:
        if msg.get("photo_file_id"):
            try:
                img = telegram_ingest.download_file(token, msg["photo_file_id"])
                events = msg_parser.extract_events_from_image(
                    img, today, caption=msg["text"])
            except Exception as e:
                print(f"[warn] Không tải/đọc được ảnh: {e}")
                events = []
            source_label = msg["text"] or "(ảnh chụp thông báo)"
        else:
            events = msg_parser.extract_events(msg["text"], today)
            source_label = msg["text"]
        for e in events:
            uid = icloud_sync.upsert_parsed_event(cal, e, source_label, tz)
            print(f"[info] Tạo event: {e['title']} @ {e['date']} {e.get('time')}")
        state["pending_messages"].append({
            "text": source_label,
            "from": msg["from"],
            "events": [e["title"] for e in events],
            "received": now.isoformat(),
        })

    # 5. Nếu là lượt chạy digest (env DIGEST_RUN=1) -> tạo event tóm tắt hôm nay
    if os.environ.get("DIGEST_RUN") == "1":
        lines = [f"🗓 {today.strftime('%A %d/%m/%Y')}", ""]

        # Các việc trong 7 ngày tới (đọc từ chính calendar)
        start = dt.datetime.combine(today, dt.time.min, tzinfo=tz)
        end = start + dt.timedelta(days=7)
        upcoming = icloud_sync.list_upcoming(cal, start, end)
        if upcoming:
            lines.append("7 ngày tới:")
            for day, time_str, title in upcoming:
                label = "Hôm nay" if day == today else day.strftime("%a %d/%m")
                lines.append(f"• {label} · {time_str} · {title}")
        else:
            lines.append("7 ngày tới chưa có việc gì cần nhớ. 🎉")

        # Thông báo mới từ group kể từ digest trước
        if state["pending_messages"]:
            lines.append("")
            lines.append(f"Thông báo mới ({len(state['pending_messages'])}):")
            for p in state["pending_messages"]:
                first = p["text"].strip().splitlines()[0][:80]
                tag = " ✅ đã lên lịch" if p["events"] else " ⚠️ chưa nhận diện được ngày"
                lines.append(f"• {first}{tag}")
            state["pending_messages"] = []

        icloud_sync.upsert_digest(
            cal, today, cfg["digest"]["time"], "\n".join(lines),
            int(cfg["digest"].get("alert_minutes_before", 0)), tz,
        )
        print("[info] Đã tạo digest hôm nay")

    telegram_ingest.save_state(state)
    print("[done]")


if __name__ == "__main__":
    main()
