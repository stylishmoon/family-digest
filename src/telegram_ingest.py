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
        text = msg.get("text") or msg.get("caption")
        if not text:
            continue
        messages.append({
            "text": text,
            "from": (msg.get("from") or {}).get("first_name", "?"),
            "date_ts": msg.get("date", 0),
        })
    return messages
