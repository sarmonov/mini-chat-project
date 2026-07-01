# Real-time Chat — FastAPI + RabbitMQ + Redis

Sodda, lekin real microservice arxitekturasini simulyatsiya qiluvchi real-time chat ilovasi.
Barcha I/O **async**. WebSocket orqali xabar → **RabbitMQ** queue → consumer → **Redis** → barcha ulanishlarga broadcast.

PowerShell da RabbitMQ va Redis run qilish
Holatni ko'rish:

Get-Service RabbitMQ, Redis

Ishga tushirish (admin kerak):
Start-Service RabbitMQ
Start-Service Redis

To'xtatish (admin kerak):
Stop-Service RabbitMQ
Stop-Service Redis

Qayta ishga tushirish:
Restart-Service RabbitMQ

## Arxitektura

```
                  ┌─────────────────────────────────────────────┐
   Browser  <──WS──>  FastAPI (main.py)                          │
   (index.html)      │   • WebSocket endpoint /ws/{room}/{user}  │
        ▲            │   • ConnectionManager (broadcast)         │
        │            └───────┬───────────────────────┬──────────┘
        │                    │ publish               │ save/read
        │                    ▼                       ▼
        │            ┌───────────────┐       ┌───────────────┐
        │            │   RabbitMQ    │       │     Redis     │
        │            │ chat_messages │       │ online_users  │
        │            │   :{room}     │       │ chat_history  │
        │            └───────┬───────┘       │ typing / rate │
        │                    │ consume       │ read receipts │
        └────broadcast───────┘               └───────────────┘
              (consumer)
```

**Xabar oqimi:** user yozadi → FastAPI RabbitMQ'ga publish qiladi → consumer (background task) queue'dan oladi → Redis tarixiga saqlaydi → o'sha xonadagi barcha WebSocket ulanishlarga broadcast qiladi.

## Funksiyalar

| # | Funksiya | Texnologiya |
|---|----------|-------------|
| 1 | Username asosida sodda auth | Redis Set `online_users` |
| 2 | Real-time umumiy chat | FastAPI WebSocket + RabbitMQ |
| 3 | Online userlar + kirdi/chiqdi notification | Redis Set + broadcast |
| 4 | Oxirgi 50 ta xabar tarixi | Redis List `chat_history:{room}` |
| 5 | Typing indicator ("... yozmoqda") | Redis `SETEX typing:{room}:{user} 3` |
| 6 | Read receipts (✓ / ✓✓) | Redis Hash `read:{room}` |
| 7 | Rate limiting (1 sek / 5 xabar) | Redis `INCR` + `EXPIRE` |
| 8 | Xonalar: general / random / tech | har xonaga alohida queue + Redis kalitlar |

## Loyiha strukturasi

```
mini-chat-project/
├── app/
│   ├── main.py               # FastAPI app, WebSocket endpoint, consumer bog'lash
│   ├── config.py             # Sozlamalar (URL, ROOMS, limitlar)
│   ├── models.py             # Pydantic modellar
│   ├── redis_service.py      # Redis bilan ishlash
│   ├── rabbit_service.py     # RabbitMQ publisher + consumer
│   └── connection_manager.py # WebSocket ulanishlarni boshqarish
├── static/
│   └── index.html            # Frontend (HTML + CSS + vanilla JS)
├── requirements.txt
└── README.md
```

## O'rnatish (Windows 10)

### 1. Erlang (RabbitMQ uchun kerak)
https://www.erlang.org/downloads — yuklab o'rnating.

### 2. RabbitMQ
https://www.rabbitmq.com/install-windows.html — o'rnating (Windows service sifatida avtomatik ishlaydi, port `5672`).

Management UI (ixtiyoriy):
```powershell
rabbitmq-plugins enable rabbitmq_management
# http://localhost:15672  (guest / guest)
```

### 3. Redis
https://github.com/tporadowski/redis/releases — `.msi` faylni o'rnating (Windows service, port `6379`).

Tekshirish:
```powershell
redis-cli ping   # -> PONG
```

## Ishga tushirish

```powershell
# 1. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 2. Serverni ishga tushirish
uvicorn app.main:app --reload

# 3. Browserda ochish
# http://localhost:8000
```

## Ishlash tartibi

1. RabbitMQ va Redis service'lari ishlayotganini tekshiring.
2. Browserda `localhost:8000` ochiladi → username + xona tanlanadi.
3. WebSocket ulanadi → Redis'ga user qo'shiladi → online ro'yxat yangilanadi → oxirgi 50 ta xabar ko'rsatiladi.
4. Xabar yoziladi → RabbitMQ'ga publish → consumer oladi → Redis'ga saqlaydi → hammaga broadcast.
5. User chiqsa → Redis'dan o'chiriladi → hammaga "chiqdi" notification.

> Sinash uchun ikki xil browser oynasida turli username bilan kiring.

## Redis kalitlari

| Kalit | Tur | Maqsad |
|-------|-----|--------|
| `online_users` | Set | Global username band/bo'shligini tekshirish |
| `online_users:{room}` | Set | Xonadagi online userlar |
| `chat_history:{room}` | List | Oxirgi 50 ta xabar (LPUSH + LTRIM) |
| `user:{username}:status` | String (TTL 30s) | Heartbeat orqali online status |
| `typing:{room}:{username}` | String (TTL 3s) | Typing indicator |
| `rate:{username}` | Int (TTL 1s) | Rate limiting (INCR) |
| `read:{room}` | Hash | Har user oxirgi o'qigan message_id |
| `msg_id:{room}` | Int | Ketma-ket xabar ID generatori |

## RabbitMQ queue'lari

Har bir xona uchun alohida **durable** queue: `chat_messages:general`, `chat_messages:random`, `chat_messages:tech`.
Startupda har queue uchun alohida consumer background task ishga tushadi.

## Mock rejim (Redis/RabbitMQ o'rnatilmagan bo'lsa)

Agar Redis yoki RabbitMQ o'rnatilmagan bo'lsa, ilova **in-memory mock** bilan ishlay oladi
(`app/redis_mock.py`, `app/rabbit_mock.py`). Standart holatda mock yoqilgan.

Flaglar (env variable):

| Flag | Default | Vazifasi |
|------|---------|----------|
| `USE_MOCKS` | `true` | Umumiy default (ikkalasi uchun) |
| `USE_REDIS_MOCK` | `USE_MOCKS` | Faqat Redis mock'ini boshqaradi |
| `USE_RABBIT_MOCK` | `USE_MOCKS` | Faqat RabbitMQ mock'ini boshqaradi |

**Haqiqiy RabbitMQ + mock Redis bilan ishga tushirish** (PowerShell):
```powershell
$env:USE_REDIS_MOCK = "true"
$env:USE_RABBIT_MOCK = "false"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**To'liq haqiqiy (Redis ham, RabbitMQ ham):**
```powershell
$env:USE_MOCKS = "false"
uvicorn app.main:app
```

## RabbitMQ'ni service emas, to'g'ridan-to'g'ri ishga tushirish (Windows)

Agar Windows service'da "0 plugins started" muammosi bo'lsa, serverni to'g'ridan-to'g'ri
ishga tushiring (`rabbitmq-env.bat` yo'llarni to'g'ri hisoblaydi):
```powershell
$env:ERLANG_HOME = "C:\Program Files\Erlang OTP"
& "C:\Program Files\RabbitMQ Server\rabbitmq_server-4.1.2\sbin\rabbitmq-server.bat"
```
Management UI: `http://localhost:15672` (guest / guest).

## Sozlamalar

Environment variable orqali o'zgartirish mumkin (`app/config.py`):

```
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```
