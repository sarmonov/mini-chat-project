@echo off
echo Kutubxonalarni o'rnatish...
python -m pip install -r requirements.txt

echo.
echo Serverni ishga tushirish...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
