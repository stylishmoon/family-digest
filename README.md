# Family Digest — Lịch gia đình + Tổng hợp thông báo hàng ngày

Tự động đồng bộ lịch học thêm của con vào iCloud Calendar (thông báo native trên iPhone của cả 2 vợ chồng), gom thông báo forward từ group Zalo/FB thành lịch + digest mỗi sáng.

## Kiến trúc

```
Group Zalo/FB ──copy-paste──▶ Telegram bot gia đình
                                     │
GitHub Actions (mỗi 3h + 6h25 sáng)  │
   1. Kéo tin mới từ bot ◀───────────┘
   2. Trích xuất ngày/giờ (Claude API, fallback regex)
   3. Ghi event vào iCloud Calendar qua CalDAV
   4. 6h30 sáng: event "📋 Tóm tắt hôm nay" có alert
                                     │
iPhone anh + vợ (shared iCloud calendar) ◀─ sync gần tức thì
```

## Cài đặt (một lần, ~30 phút)

### 1. iCloud Calendar
1. Trên iPhone: tạo calendar mới tên **"Gia đình"** (Calendar app → Calendars → Add Calendar, chọn iCloud).
2. Share calendar này với Apple ID của vợ (chọn calendar → Add Person).
3. Tạo **app-specific password**: vào https://appleid.apple.com → Sign-In and Security → App-Specific Passwords. Lưu lại chuỗi `xxxx-xxxx-xxxx-xxxx`.
   - ⚠️ Nếu repo dùng chung Apple ID nào thì calendar ghi vào tài khoản đó. Dùng Apple ID của anh, share cho vợ là gọn nhất.

### 2. Telegram bot
1. Chat với **@BotFather** trên Telegram → `/newbot` → đặt tên → nhận **bot token**.
2. Cả anh và vợ mở bot, bấm Start. Từ giờ thấy thông báo quan trọng trong group Zalo/FB thì copy → paste vào bot.

### 3. GitHub
1. Tạo **private repo**, push toàn bộ thư mục này lên.
2. Vào Settings → Secrets and variables → Actions, thêm:
   - `TELEGRAM_BOT_TOKEN`
   - `APPLE_ID` (email Apple ID)
   - `APPLE_APP_PASSWORD`
   - `ANTHROPIC_API_KEY` *(tùy chọn — có thì parse tiếng Việt tự nhiên chính xác hơn nhiều; không có thì dùng regex, chỉ bắt được định dạng rõ ràng kiểu "10/7 lúc 19h30")*
3. Sửa `config/schedule.yaml` theo lịch thật của con.
4. Tab Actions → chọn workflow `family-digest` → **Run workflow** để test lần đầu.

### 4. Kiểm tra
- Sau lần chạy đầu, mở Calendar trên iPhone: lịch đá banh/cầu lông phải xuất hiện dạng lặp hàng tuần, có alert.
- Paste thử một tin vào bot, ví dụ: `Thông báo: thứ 5 tuần này lớp cầu lông nghỉ, học bù CN 9h sáng` → chạy workflow tay → xem event xuất hiện chưa.

## Vận hành hàng ngày
- Thấy thông báo trong group → copy → paste vào bot Telegram. Xong.
- 6h30 sáng cả 2 điện thoại nhận notification "📋 Tóm tắt hôm nay" — mở ra xem lịch trong ngày + các thông báo mới.
- Đổi lịch cố định: sửa `config/schedule.yaml` → push. Event trên iCloud tự cập nhật (UID cố định, không tạo trùng).

## Giới hạn cần biết (nói thẳng)
- **Zalo không forward trực tiếp sang Telegram** — thao tác là copy-paste, mất ~5 giây/tin.
- **Cron GitHub Actions có thể trễ 5–15 phút**, hiếm khi hơn. Digest đặt 6h25 để bù trễ.
- **Parse regex (không có API key) rất hạn chế** với văn phong tự nhiên ("tối mai nghỉ nha các mẹ"). Muốn chính xác thì dùng Claude API — chi phí thực tế không đáng kể với vài tin/ngày.
- Tin parse sai/sót vẫn xuất hiện trong digest dạng thô, không bị mất — chỉ là không thành event riêng.
- `state.json` (offset Telegram + tin chờ digest) được commit lại vào repo sau mỗi lần chạy — đây là lý do repo nên để **private**.
