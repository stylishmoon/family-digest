"""Kéo tin nhắn mới từ Telegram bot (kênh forward của gia đình)."""
import json
import os
import requests

STATE_FILE = "state.json"
API = "https://api.telegram.org/bot{token}/{method}"


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"telegram_offset": 0, "pending_messages": [], "digested_uids": []}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_new_messages(token: str, state: dict) -> list[dict]:
    """Trả về list {text, from, date_ts}. Cập nhật offset trong state."""
    resp = requests.get(
        API.format(token=token, method="getUpdates"),
        params={"offset": state["telegram_offset"] + 1, "timeout": 0},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")

    messages = []
    for update in data.get("result", []):
        state["telegram_offset"] = max(state["telegram_offset"], update["update_id"])
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        text = msg.get("text") or msg.get("caption") or ""
        photo = msg.get("photo")  # list PhotoSize, phần tử cuối là bản to nhất
        if not text and not photo:
            continue
        entry = {
            "text": text,
            "from": (msg.get("from") or {}).get("first_name", "?"),
            "date_ts": msg.get("date", 0),
        }
        if photo:
            entry["photo_file_id"] = photo[-1]["file_id"]
        messages.append(entry)
    return messages


def download_file(token: str, file_id: str) -> bytes:
    """Tải file (ảnh) từ Telegram theo file_id."""
    r = requests.get(API.format(token=token, method="getFile"),
                     params={"file_id": file_id}, timeout=30)
    r.raise_for_status()
    path = r.json()["result"]["file_path"]
    f = requests.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=60)
    f.raise_for_status()
    return f.content
