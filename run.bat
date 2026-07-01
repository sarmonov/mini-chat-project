@echo off
chcp 65001 >nul
echo ============================================
echo   Mini Telegram - ishga tushirish
echo ============================================
echo.

echo [1/3] Infratuzilma (Postgres + Redis + RabbitMQ) Docker orqali...
docker compose up -d
if errorlevel 1 (
  echo.
  echo Docker topilmadi yoki ishlamayapti. Docker Desktop ni ishga tushiring.
  echo Yoki Postgres/Redis/RabbitMQ ni qo'lda ishga tushiring.
  pause
  exit /b 1
)

echo.
echo [2/3] Kutubxonalarni o'rnatish...
python -m pip install -r requirements.txt

echo.
echo [3/3] Serverni ishga tushirish...
echo   Ilova:  http://localhost:8000
echo.
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
