# Knowledge Bot

Bot Telegram ghi chú kiến thức thông minh — tự phân loại, hỏi lại theo phương pháp Socratic, và lưu trữ có tổ chức trên Supabase.

---

## Tính năng

- Nhắn bất kỳ → bot tự phân loại category, gắn tag, tóm tắt
- Hỏi lại 1 câu Socratic để đào sâu vấn đề
- Trả lời câu hỏi → bot tiếp tục đào sâu thêm 1 lượt
- `/list` xem ghi chú gần nhất, `/search` tìm kiếm theo từ khóa
- Dữ liệu lưu trên Supabase — local và server cùng trỏ 1 database

---

## Yêu cầu

- Python 3.10+
- Tài khoản [Supabase](https://supabase.com) (free)
- Tài khoản [OpenRouter](https://openrouter.ai) (free tier)
- Bot Telegram (tạo qua [@BotFather](https://t.me/BotFather))

---

## Cài đặt

**1. Clone và tạo môi trường**

```bash
git clone <repo-url>
cd knowledge-bot
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**2. Cài dependencies**

```bash
pip install -r requirements.txt
```

**3. Tạo file `.env`**

```bash
cp .env.example .env
```

Mở `.env` và điền các giá trị:

```env
TELEGRAM_TOKEN=...
OPENROUTER_API_KEY=...
DATABASE_URL=...
```

**4. Chạy bot**

```bash
python main.py
```

---

## Lấy các API key

### Telegram Token
1. Nhắn [@BotFather](https://t.me/BotFather) trên Telegram
2. Gõ `/newbot` → đặt tên → copy token

### OpenRouter API Key
1. Vào [openrouter.ai](https://openrouter.ai) → đăng nhập
2. Keys → Create Key → copy

### Supabase DATABASE_URL
1. Tạo project mới tại [supabase.com](https://supabase.com)
2. Vào **Project Settings → Database → Connection string → URI**
3. Chọn **Session mode (port 5432)** cho bot long-running
4. Copy URI, thay `[YOUR-PASSWORD]` bằng mật khẩu database

```
postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres
```

> Bảng `notes` sẽ tự tạo lần đầu chạy bot.

---

## Cấu trúc project

```
knowledge-bot/
├── main.py              ← entry point, khởi động bot
├── requirements.txt
├── .env                 ← gitignore
├── .env.example
├── .gitignore
├── plan.md              ← roadmap chi tiết 3 phases
│
├── bot/
│   ├── handlers.py      ← xử lý message, điều phối flow
│   ├── commands.py      ← /list /search /help
│   └── state.py         ← conversation state per user (in-memory)
│
├── ai/
│   ├── classifier.py    ← phân loại category + tags qua LLM
│   ├── socratic.py      ← tạo câu hỏi đào sâu
│   └── prompts.py       ← tất cả system prompts
│
├── db/
│   ├── database.py      ← connection pool, init bảng
│   ├── models.py        ← dataclass Note
│   └── queries.py       ← save, get_recent, search
│
└── config/
    └── settings.py      ← load .env, constants
```

---

## Commands

| Command | Chức năng |
|---|---|
| _(nhắn text bất kỳ)_ | Lưu ghi chú + phân loại + hỏi Socratic |
| `/list` | Xem 5 ghi chú gần nhất |
| `/search [từ khóa]` | Tìm kiếm ghi chú |
| `/help` | Hiện menu hướng dẫn |

---

## Conversation flow

```
Bạn nhắn → bot phân loại → lưu DB → xác nhận → hỏi Socratic
Bạn trả lời → bot đào sâu thêm 1 lượt → reset, sẵn sàng ghi chú mới
```

---

## Đổi model

Mặc định dùng `anthropic/claude-sonnet-4-5`. Để đổi, thêm vào `.env`:

```env
MODEL=google/gemini-2.0-flash-001
```

Danh sách model: [openrouter.ai/models](https://openrouter.ai/models)

---

## Roadmap

Xem [`plan.md`](./plan.md) để biết chi tiết Phase 2 (semantic search, spaced repetition) và Phase 3 (cross-domain synthesis, daily digest).
