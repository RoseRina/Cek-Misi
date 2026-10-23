@echo off
title Shopee Tools Universal Web Dashboard
color 0b
echo ======================================================================
echo       SHOPEE TOOLS ALL-IN-ONE (UNIVERSAL WEB DASHBOARD)
echo ======================================================================
echo.
echo Memeriksa dependensi...
pip install -r requirements.txt --quiet

echo.
echo Menjalankan Web Server di Port 8000...
echo Buka di browser: http://localhost:8000
echo.
python server.py
pause
