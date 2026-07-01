Mini Chat Loyihasi Tahlili
Ushbu loyiha FastAPI, RabbitMQ, va Redis asosida qurilgan, real vaqtda ishlovchi (real-time) chat mikroservisidir. Quyida uning ishlash arxitekturasi va har bir fayl qanday vazifani bajarishi haqida to'liq ma'lumot keltirilgan.

🏗 Arxitektura va Ma'lumotlar Oqimi
Loyiha asinxron (async) I/O tamoyiliga asoslangan. Bu degani u bir vaqtning o'zida minglab ulanishlarni qotib qolmasdan ishlata oladi.

Ulanish: Foydalanuvchi brauzer orqali xonaga (room) kirganida FastAPI orqali WebSocket ulanishi o'rnatiladi.
Xabar yozish: Foydalanuvchi xabar yuborganida, FastAPI bu xabarni to'g'ridan-to'g'ri boshqalarga tarqatmaydi. Buning o'rniga uni RabbitMQ (xabarlar brokeri) ga yuboradi (publish qiladi).
Navbat (Queue): RabbitMQ xabarni tegishli xonaning navbatiga (chat_messages:{room}) joylashtiradi.
Qabul qilish (Consume): Orqa fonda ishlayotgan Consumer jarayoni RabbitMQ'dan yangi xabarni olib o'qiydi.
Saqlash: O'qilgan xabar avval Redis'ga (chat tarixi uchun) saqlanadi.
Tarqatish (Broadcast): Va nihoyat, saqlangan xabar ConnectionManager orqali shu xonadagi barcha faol WebSocket'larga tarqatiladi.
Bu uslub "Pub/Sub" (Publish-Subscribe) deb ataladi. U serverlar ko'payganda ham xabarlarni yo'qotmasdan va tartib bilan yetkazishni ta'minlaydi.

📂 Fayllar Vazifalari (app/ papkasi ichida)
1. main.py (Asosiy kirish nuqtasi)
Bu loyihaning "yuragi".

Vazifasi: FastAPI ilovasini yaratish, HTTP va WebSocket yo'nalishlarini (endpoints) boshqarish.
Nima ish qiladi:
Ilova ishga tushganda Redis va RabbitMQ ga ulanadi (lifespan).
Frontend (index.html) uchun / endpointini taqdim etadi.
/ws/{room}/{username} orqali foydalanuvchilarni qabul qiladi. Ulanishni tekshiradi, ism band emasligiga ishonch hosil qiladi va ulanishni tasdiqlaydi (websocket.accept()).
Foydalanuvchidan kelayotgan xabarlarni kutib turadi, tekshiradi (rate-limit, bo'sh xabar emasligi) va RabbitMQ ga jo'natadi.
2. config.py (Sozlamalar)
Vazifasi: Loyihaning barcha o'zgaruvchan sozlamalarini o'zida saqlaydi.
Nima ish qiladi: Environment (muhit) o'zgaruvchilarini o'qiydi. Redis va RabbitMQ manzillari, xonalar ro'yxati, tarix chegarasi (50 ta xabar), spam himoyasi (1 soniyada 5 ta xabar) kabi chegaralarni (limitlarni) saqlaydi. USE_MOCKS bayrog'ini ham shu yer boshqaradi.
3. models.py (Ma'lumotlar qolipi)
Vazifasi: Kiruvchi va chiquvchi ma'lumotlarni tekshirish (Pydantic yordamida).
Nima ish qiladi:
IncomingMessage: Brauzerdan kelayotgan JSON to'g'riligini tekshiradi (xabar, typing, heartbeat kabi turlarga ajratadi).
ChatMessage: RabbitMQ va Redis ichida yuradigan xabar obyektining qanday tuzilishda bo'lishini qatiy belgilaydi (ID, username, text, vaqt).
4. redis_service.py (Holat xotirasi)
Vazifasi: Tezkor ma'lumotlar bazasi (Redis) bilan aloqa.
Nima ish qiladi: Loyihadagi barcha "vaqtinchalik" va "tezkor" ma'lumotlarni saqlaydi:
Online users (Set): Kim qaysi xonada ekanini va umuman saytda qaysi ismlar bandligini saqlaydi.
Chat tarixi (List): Xonadagi oxirgi 50 ta xabarni o'zida ushlab turadi, yangisi kelganda eng eskisini o'chiradi (ltrim).
Rate limiting (Incr/Expire): Foydalanuvchi 1 soniyada 5 tadan ortiq xabar yozishining oldini oladi (Spam himoyasi).
Typing indicator (Setex): Foydalanuvchi "yozmoqda..." maqomini 3 soniyaga xotirada saqlaydi.
Heartbeat/Status: Foydalanuvchi hali ham tarmoqdaligini har 30 soniyada yangilab turuvchi kalitlar.
5. rabbit_service.py (Xabarlar xabarchisi)
Vazifasi: Mikroservislar o'rtasida xabar tashish (RabbitMQ bilan aloqa).
Nima ish qiladi:
Queue yaratish: Har bir xona uchun alohida bardoshli (durable) chat_messages:{room} nomli navbatlar yaratadi.
Publish: main.py dan kelgan xabarni shu navbatga tashlaydi.
Consumer: Orqa fonda to'xtovsiz ishlaydigan sikl ochib, navbatga yangi xabar tushishini kutib turadi. Xabar tushgan zahoti uni o'qiydi va main.py dagi on_rabbit_message funksiyasiga qaytarib beradi.
6. connection_manager.py (Jonli tarmoq boshqaruvi)
Vazifasi: Faol (aktiv) WebSocket ulanishlarini xotirada (RAM) ro'yxatga olib turish.
Nima ish qiladi:
Kim qaysi xonaga kirdi (connect) va qachon chiqib ketdi (disconnect) — shuni Python dikshinerisi (lug'at) yordamida saqlaydi.
Eng asosiy vazifasi — broadcast(). Qachonki bitta yangi xabar kelsa, u shu xonadagi barcha faol foydalanuvchilarning rozetkasiga (socket) xabarni birma-bir jo'natib chiqadi. Agar kimgadir yuborishda xato bersa (masalan interneti uzilgan bo'lsa), uni o'lik (dead) ulanish sifatida ro'yxatdan o'chiradi.
7. Mock fayllar (redis_mock.py, rabbit_mock.py)
Haqiqiy Redis va RabbitMQ yo'q bo'lgan vaqtlarda, xuddi ular boridek o'zini tutuvchi (emulyator) Python classlaridir. Barcha ma'lumotlarni o'zgaruvchilar (dict, list) yordamida RAM da saqlaydi. Dasturni har qanday sharoitda ishga tushirish imkonini beradi.