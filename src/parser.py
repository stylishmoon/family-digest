"""Trích xuất sự kiện (ngày/giờ/nội dung) từ tin nhắn forward.

Hai chế độ:
- Có ANTHROPIC_API_KEY  -> gọi Claude API, chính xác với văn phong tự nhiên tiếng Việt.
- Không có key          -> regex cơ bản (dd/mm, HH:MM, HHh, "thứ X"). Brittle, chỉ là fallback.

Mỗi event trả về: {title, date: "YYYY-MM-DD", time: "HH:MM"|None,
                   end_time: "HH:MM"|None, note: str}
Nếu không trích được ngày cụ thể -> events rỗng, tin vẫn vào digest dạng thô.
"""
import base64
import datetime as dt
import json
import os
import re
import requests

VN_WEEKDAYS = {"thứ 2": 0, "thứ hai": 0, "thứ 3": 1, "thứ ba": 1,
               "thứ 4": 2, "thứ tư": 2, "thứ 5": 3, "thứ năm": 3,
               "thứ 6": 4, "thứ sáu": 4, "thứ 7": 5, "thứ bảy": 5,
               "chủ nhật": 6, "cn": 6}

MODEL = "claude-haiku-4-5-20251001"


def _build_prompt(today: dt.date, extra: str = "") -> str:
    return (
        "Bạn là bộ trích xuất sự kiện từ tin nhắn/thông báo của gia đình Việt Nam. "
        f"Hôm nay là {today.isoformat()} ({today.strftime('%A')}). "
        "Đọc nội dung và trả về DUY NHẤT một JSON array (không markdown, không giải thích). "
        'Mỗi phần tử: {"title": str, "date": "YYYY-MM-DD", "time": "HH:MM" hoặc null, '
        '"end_time": "HH:MM" hoặc null, "note": str, '
        '"repeat": null hoặc {"days": ["MO"|"TU"|"WE"|"TH"|"FR"|"SA"|"SU", ...], '
        '"until": "YYYY-MM-DD"}}. '
        "Quy đổi mốc tương đối (mai, tối thứ 5, tuần sau...) ra ngày cụ thể. "
        'Nếu tin nêu một KHOẢNG ngày được phép thực hiện việc gì đó '
        '(vd "đóng tiền trong 10-15/7", "nộp hồ sơ từ 1 đến 5/8"): '
        'đây là deadline — chọn "date" là NGÀY CUỐI CÙNG của khoảng, '
        'và ghi rõ khoảng cho phép vào "note". '
        'Nếu tin mô tả lịch lặp (vd "từ 15/7 đến 30/7, thứ 2 thứ 6 hàng tuần"): '
        '"date" là NGÀY DIỄN RA ĐẦU TIÊN khớp các thứ đã nêu, "repeat.days" là các thứ, '
        '"repeat.until" là ngày kết thúc. Lịch một lần thì "repeat": null. '
        'Trường "note" phải tóm tắt đủ chi tiết quan trọng (địa điểm, khung giờ, '
        "lưu ý, số điện thoại liên hệ nếu có). "
        "Nếu không chứa sự kiện nào xác định được ngày, trả về []. "
        + extra
    )


def _call_api(content, api_key: str) -> list[dict]:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"API {resp.status_code}: {resp.text[:300]}")
    raw = "".join(b.get("text", "") for b in resp.json()["content"])
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        events = json.loads(raw)
        return events if isinstance(events, list) else []
    except json.JSONDecodeError:
        return []


def parse_with_claude(text: str, today: dt.date, api_key: str) -> list[dict]:
    return _call_api(_build_prompt(today) + f"\n\nTin nhắn:\n{text}", api_key)


def extract_events_from_image(image_bytes: bytes, today: dt.date,
                              caption: str = "") -> list[dict]:
    """Đọc ảnh chụp thông báo (giấy, chụp màn hình...). Cần ANTHROPIC_API_KEY."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("[warn] Nhận ảnh nhưng không có ANTHROPIC_API_KEY, bỏ qua nội dung ảnh")
        return []
    extra = ("\n\nNội dung là ẢNH CHỤP một thông báo, hãy đọc chữ trong ảnh."
             + (f"\nCaption kèm ảnh: {caption}" if caption else ""))
    content = [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode()}},
        {"type": "text", "text": _build_prompt(today, extra)},
    ]
    try:
        return _call_api(content, api_key)
    except Exception as e:
        print(f"[warn] Đọc ảnh thất bại: {e}")
        return []


def parse_with_regex(text: str, today: dt.date) -> list[dict]:
    """Fallback thô: chỉ bắt được dd/mm(/yyyy) + HH:MM hoặc HHh(MM)."""
    events = []
    date_m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", text)
    time_m = re.search(r"\b(\d{1,2})(?:[:h](\d{2})?)\b", text)

    date = None
    if date_m:
        d, m = int(date_m.group(1)), int(date_m.group(2))
        y = int(date_m.group(3)) if date_m.group(3) else today.year
        if y < 100:
            y += 2000
        try:
            date = dt.date(y, m, d)
            if not date_m.group(3) and date < today - dt.timedelta(days=60):
                date = dt.date(y + 1, m, d)  # ngày đã qua xa -> năm sau
        except ValueError:
            date = None
    else:
        low = text.lower()
        for kw, wd in VN_WEEKDAYS.items():
            if kw in low:
                delta = (wd - today.weekday()) % 7
                date = today + dt.timedelta(days=delta or 7)
                break
        if "mai" in text.lower().split() and date is None:
            date = today + dt.timedelta(days=1)

    if date is None:
        return []

    time = None
    if time_m:
        h = int(time_m.group(1))
        mm = int(time_m.group(2) or 0)
        if 0 <= h <= 23:
            time = f"{h:02d}:{mm:02d}"

    title = text.strip().splitlines()[0][:60]
    events.append({"title": f"📌 {title}", "date": date.isoformat(),
                   "time": time, "end_time": None, "note": text.strip()})
    return events


def extract_events(text: str, today: dt.date) -> list[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            return parse_with_claude(text, today, api_key)
        except Exception as e:  # fallback nếu API lỗi
            print(f"[warn] Claude API failed, dùng regex fallback: {e}")
    return parse_with_regex(text, today)
