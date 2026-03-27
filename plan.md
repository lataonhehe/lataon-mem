# Knowledge Bot — Kế hoạch xây dựng

Bot Telegram ghi chú kiến thức thông minh: tự phân loại, hỏi Socratic, nhắc lại theo spaced repetition, và kết nối kiến thức liên ngành.

---

## Tổng quan kiến trúc

```
Telegram
   │
   ▼
Bot Core (Python)          ← phân loại ý định, điều phối
   │
   ├── Note Engine          ← lưu, gắn tag, liên kết kiến thức
   │       ├── SQLite       ← metadata, spaced repetition
   │       └── Vector DB    ← embedding, semantic search (Phase 2)
   │
   ├── LLM (OpenRouter)     ← phân loại, Socratic, synthesis
   │
   └── Scheduler            ← nhắc ôn tập, daily digest
```

---

## Phase 1 — MVP (2–3 tuần)

**Mục tiêu:** Bot ghi chú cơ bản, phân loại tự động, hỏi Socratic.

### Stack
| Thành phần | Công nghệ |
|---|---|
| Bot framework | python-telegram-bot 20.x |
| LLM | OpenRouter (claude-sonnet-4-5) |
| Database | SQLite + aiosqlite |
| Config | python-dotenv |

### Cấu trúc project
```
knowledge-bot/
├── main.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── bot/
│   ├── handlers.py      ← xử lý message, điều phối flow
│   ├── commands.py      ← /list /search /help
│   └── state.py         ← conversation state per user
├── ai/
│   ├── classifier.py    ← phân loại category + tags
│   ├── socratic.py      ← câu hỏi đào sâu
│   └── prompts.py       ← tất cả system prompts
├── db/
│   ├── database.py      ← init SQLite, tạo bảng
│   ├── models.py        ← dataclass Note
│   └── queries.py       ← save, get, search
├── config/
│   └── settings.py      ← load .env, constants
└── data/
    └── knowledge.db     ← gitignore
```

### Database schema
```sql
CREATE TABLE notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    content     TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'general',
    tags        TEXT NOT NULL DEFAULT '',   -- JSON array
    summary     TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Categories
`it` · `knowledge` · `diary` · `book` · `idea` · `health` · `finance` · `other`

### Commands
| Command | Chức năng |
|---|---|
| _(nhắn text)_ | Lưu ghi chú + phân loại + hỏi Socratic |
| `/list` | 5 ghi chú gần nhất |
| `/search [từ khóa]` | Tìm kiếm theo text |
| `/help` | Menu hướng dẫn |

### Conversation flow
```
User nhắn → IDLE mode
  → classify_note() → lưu DB
  → xác nhận [category] #tags
  → hỏi Socratic → chuyển AWAITING_REPLY

User trả lời → AWAITING_REPLY mode
  → continue_deep_dive() → hỏi tiếp
  → reset về IDLE
```

### Issues đã fix
- `json.loads` fail im lặng → thêm log + strip markdown fences
- `asyncio.run()` conflict với PTB v20 → dùng `post_init` hook
- Summary bị cắt giữa từ → cắt tại khoảng trắng + thêm `…`
- Câu trả lời Socratic bị lưu như ghi chú mới → `AWAITING_REPLY` state

---

## Phase 2 — Smart features (3–4 tuần)

**Mục tiêu:** Tìm kiếm ngữ nghĩa, nhắc ôn tập tự động theo Spaced Repetition.

### Thêm vào stack
| Thành phần | Công nghệ |
|---|---|
| Vector DB | ChromaDB (local) |
| Embedding | OpenRouter hoặc OpenAI text-embedding-3-small |
| Scheduler | APScheduler |

### Database schema bổ sung
```sql
-- Thêm cột vào bảng notes
ALTER TABLE notes ADD COLUMN embedding_id TEXT;
ALTER TABLE notes ADD COLUMN next_review_at TIMESTAMP;
ALTER TABLE notes ADD COLUMN review_interval INTEGER DEFAULT 1;  -- ngày
ALTER TABLE notes ADD COLUMN review_count INTEGER DEFAULT 0;
ALTER TABLE notes ADD COLUMN ease_factor REAL DEFAULT 2.5;       -- SM-2
```

### Cấu trúc bổ sung
```
knowledge-bot/
├── db/
│   ├── vector_store.py  ← ChromaDB: upsert, query
│   └── scheduler.py     ← APScheduler jobs
├── ai/
│   └── embedder.py      ← tạo embedding cho mỗi ghi chú
```

### Commands mới
| Command | Chức năng |
|---|---|
| `/recall [chủ đề]` | Semantic search — tìm theo nghĩa |
| `/stats` | Tổng quan: số ghi chú, streak, sắp đến hạn ôn |
| `/skip` | Bỏ qua ghi chú đang ôn |

### Spaced Repetition (SM-2)
- Mỗi ghi chú có `next_review_at`, `ease_factor`, `review_interval`
- Scheduler 8h sáng: lấy 3 ghi chú đến hạn → gửi Telegram kèm câu hỏi ôn
- User phản hồi chất lượng (dễ / vừa / khó) → tính lại interval

### Embedding pipeline
```
save_note() → tạo embedding → lưu ChromaDB
/recall [query] → embed query → cosine similarity → top 5 kết quả
```

---

## Phase 3 — Synthesis engine (4–6 tuần)

**Mục tiêu:** Tạo ý tưởng mới từ kiến thức liên ngành, daily digest, deep dive mode.

### Cấu trúc bổ sung
```
knowledge-bot/
├── ai/
│   ├── synthesizer.py   ← cross-domain linking, idea generation
│   └── digest.py        ← daily/weekly report
├── db/
│   └── links.py         ← lưu các liên kết kiến thức đã tạo
```

### Database schema bổ sung
```sql
CREATE TABLE knowledge_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id_a   INTEGER REFERENCES notes(id),
    note_id_b   INTEGER REFERENCES notes(id),
    insight     TEXT NOT NULL,   -- điểm chung / ý tưởng mới
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Commands mới
| Command | Chức năng |
|---|---|
| `/deep [topic]` | Deep dive Socratic 5 lượt về 1 chủ đề |
| `/idea` | Lấy 3 ghi chú ngẫu nhiên → tạo 1 ý tưởng mới |
| `/export` | Xuất toàn bộ ghi chú ra file Markdown |

### Tính năng tự động
| Thời gian | Hành động |
|---|---|
| Tối 9h | Daily digest: tổng hợp kiến thức trong ngày + 1 cross-domain insight |
| Chủ nhật | Weekly report: pattern học, topic nổi bật, gợi ý đào sâu |

### Cross-domain synthesis prompt
```
Lấy 2 ghi chú từ category khác nhau
→ prompt: "Tìm điểm chung hoặc ý tưởng mới kết hợp 2 kiến thức này"
→ gửi insight cho user + lưu vào knowledge_links
```

---

## Prompts

### Classifier
- Liệt kê rõ 8 category với mô tả
- 2 ví dụ few-shot (IT + diary)
- Yêu cầu JSON thuần, không markdown

### Socratic (lượt 1)
- Đặt 1 câu duy nhất
- Không yes/no
- Không khen ngợi

### Deep dive (lượt 2+)
- Dựa trên câu trả lời vừa rồi
- Không lặp câu hỏi cũ

### Synthesizer
- Nhận 2 đoạn từ 2 category khác nhau
- Tìm điểm chung hoặc ứng dụng chéo
- Trả về 1 insight ngắn gọn

---

## Hosting (khi sẵn sàng)

| Option | Ưu điểm | Phù hợp |
|---|---|---|
| Railway | Free tier, dễ deploy, auto-sleep | Phase 1–2 |
| Fly.io | Persistent volume cho SQLite | Phase 2+ |
| VPS (DigitalOcean/Vultr) | Toàn quyền kiểm soát | Phase 3 |

> Lưu ý: SQLite không phù hợp cho multi-instance. Nếu scale lên nhiều user → migrate sang Postgres.
