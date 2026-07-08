# Family Digest — Nhắc việc bất thường của gia đình

Hộp thư chung của gia đình: việc gì sợ quên (hạn đóng tiền điện/nước/internet, hạn đăng ký học, lịch học đổi bất thường...) thì **paste hoặc gõ vào bot Telegram** — hệ thống tự tạo event có thông báo trên iPhone của cả 2 vợ chồng, kèm bản tóm tắt mỗi sáng.

## Cách hoạt động

```
Group Zalo/FB (copy-paste) hoặc tự gõ ──▶ Telegram bot gia đình
                                                │
GitHub Actions (mỗi 3h + 6h25 sáng)             │
   1. Kéo tin mới từ bot ◀──────────────────────┘
   2. Trích ngày/giờ bằng Claude API (fallback regex nếu không có key)
   3. Ghi event vào iCloud Calendar "Gia đình" qua CalDAV
   4. 6h30 sáng: event "📋 Tóm tắt hôm nay" liệt kê việc 7 ngày tới
                                                │
iPhone 2 vợ chồng (shared iCloud calendar) ◀── sync gần tức thì
```

## Quy tắc nhắc

- Tin có **giờ cụ thể** ("họp phụ huynh 19h thứ 6") → event đúng giờ, nhắc trước 60 phút.
- Tin kiểu **deadline không có giờ** ("hạn đóng tiền internet 15/7") → event cả ngày, nhắc **9h sáng hôm trước** + **7h sáng đúng ngày**.
- Tin mô tả **lịch lặp** ("học bù 15/7–30/7, thứ 2 thứ 6, 18h") → 1 event lặp đúng các thứ trong khoảng (cần Claude API).
- Tin **không nhận diện được ngày** → không tạo event, nhưng vẫn xuất hiện trong digest sáng với cờ ⚠️ để thêm tay.
- Mỗi event đều đính **nguyên văn tin gốc** trong ghi chú — mở event đối chiếu được nguồn.

## Mẹo gõ tin cho bot

Đủ 3 yếu tố: **việc gì – ngày nào – (giờ nào)**. Ví dụ: `đóng tiền điện hạn 20/7` · `19h thứ 6 họp phụ huynh` · `con nghỉ học từ 15/7 đến 30/7 trừ thứ 7`.

## Secrets (GitHub → Settings → Secrets and variables → Actions)

| Secret | Ghi chú |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token từ @BotFather. Cẩn thận đừng paste dính ký tự xuống dòng |
| `APPLE_ID` | Email Apple ID (chủ calendar) |
| `APPLE_APP_PASSWORD` | App-specific password từ appleid.apple.com |
| `ANTHROPIC_API_KEY` | Tùy chọn nhưng rất nên có — không có thì chỉ parse được câu định dạng rõ ("10/7 lúc 19h30") |

## Vận hành & bảo trì

- Quy tắc Git khi sửa code/config: **luôn `git pull --rebase origin main` trước khi push** (bot tự commit `state.json` sau mỗi lần chạy).
- Update file bằng cách copy đè **từng file**, đừng kéo-thả nguyên thư mục trong Finder (Finder thay cả thư mục, mất file).
- Đổi giờ digest: sửa `digest.time` trong `config/schedule.yaml` (nhớ đổi cả cron trong `.github/workflows/daily.yml` cho khớp).
- Cần lịch lặp cố định dài hạn (khóa học cả kỳ): khai báo trong `activities` của `schedule.yaml` — xem lịch sử Git commit đầu tiên để lấy mẫu block, hoặc cứ nhắn bot theo dạng lịch lặp ở trên.
- Xóa event lặp: mở 1 buổi bất kỳ → Delete → Delete All Future Events.

## Giới hạn đã biết

- Zalo/FB không forward trực tiếp — thao tác là copy-paste (~5 giây/tin).
- Cron GitHub Actions có thể trễ 5–15 phút; digest đặt 6h25 để bù.
- Script chỉ thêm/cập nhật event, **không tự xóa** khi thông báo bị hủy — hủy thì xóa tay trên iPhone.
- Repo phải để **private**: `state.json` chứa nội dung tin nhắn gia đình.
