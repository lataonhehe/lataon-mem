# Knowledge Bot — Cloudflare Worker

Bản TypeScript của bot, chạy hoàn toàn trên Cloudflare:

```
Telegram ──webhook──▶ Worker (bot.<domain>/tg)
                        ├── Durable Object  UserSession — state theo user, xử lý tuần tự
                        ├── D1              notes
                        ├── Vectorize       embedding (bge-m3, 1024 chiều, cosine)
                        ├── Workers AI      @cf/baai/bge-m3
                        └── fetch           OpenRouter (phân loại, Socratic, quiz, tóm tắt)
```

## Deploy lần đầu

Chạy trong thư mục `worker/`:

```powershell
npm install
npx wrangler login

# 1. D1 — copy database_id in ra vào wrangler.jsonc
npx wrangler d1 create lataon-mem-bot
npx wrangler d1 migrations apply lataon-mem-bot --remote

# 2. Vectorize — PHẢI tạo metadata index trước khi insert vector
npx wrangler vectorize create lataon-mem-notes --dimensions=1024 --metric=cosine
npx wrangler vectorize create-metadata-index lataon-mem-notes --property-name=user_id --type=number

# 3. Sửa wrangler.jsonc: routes → subdomain thật (vd. bot.tenmien.com), MODEL nếu cần

# 4. Secrets (WEBHOOK_SECRET, ADMIN_TOKEN: chuỗi ngẫu nhiên, chỉ gồm A-Z a-z 0-9 _ -)
npx wrangler secret put TELEGRAM_TOKEN
npx wrangler secret put OPENROUTER_API_KEY
npx wrangler secret put WEBHOOK_SECRET
npx wrangler secret put ADMIN_TOKEN

# 5. Deploy + đăng ký webhook
npx wrangler deploy
curl.exe -X POST https://bot.tenmien.com/admin/setup -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Tạo chuỗi ngẫu nhiên: `-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | % {[char]$_})`

> Bot Python và Worker **không chạy song song được**: set webhook xong thì `run_polling` sẽ lỗi. Tắt bot Python trước bước 5.

## Chuyển dữ liệu từ Supabase

```powershell
# Ở thư mục gốc, dùng venv của bot Python (cần DATABASE_URL trong .env)
python scripts/export_supabase.py
cd worker
npx wrangler d1 execute lataon-mem-bot --remote --file ../data/d1_import.sql

# Tạo embedding cho toàn bộ ghi chú, mỗi lần gọi xử lý 50 ghi chú
$after = 0
while ($after -ne $null) {
  $r = Invoke-RestMethod -Method Post "https://bot.tenmien.com/admin/reindex?after=$after" -Headers @{ Authorization = "Bearer <ADMIN_TOKEN>" }
  "processed $($r.processed)"; $after = $r.next
}
```

`/admin/reindex` cũng dùng được để bù embedding nếu có ghi chú lưu được vào D1 nhưng upsert Vectorize lỗi.

## Phát triển

```powershell
npm run typecheck
npx wrangler tail          # xem log production
```

`wrangler dev` chạy được D1/DO local, nhưng Workers AI và Vectorize luôn gọi lên tài khoản thật.
Sau khi đổi binding trong `wrangler.jsonc`, chạy lại `npm run cf-typegen`.

## Khác biệt so với bản Python

- "Hôm nay", streak, ngày hiển thị tính theo giờ VN (UTC+7) — bản Python dùng giờ server (UTC).
- `/search` không phân biệt hoa thường với cả tiếng Việt (cột `search_text` đã lowercase).
- `/done`, `/skip`, `/save` giờ cũng lưu embedding (bản Python bỏ sót → ghi chú nháp không `/recall` được).
- `/edit` embed lại nội dung mới.
- Socratic/Deep không còn gửi câu trả lời của user 2 lần cho LLM.
- Mất state khi restart không còn xảy ra — state nằm trong Durable Object.
