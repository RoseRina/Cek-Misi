#!/usr/bin/env bash
# Shopee Tools Universal Web Dashboard Launcher for Linux / Termux / VPS

echo "======================================================================"
echo "      SHOPEE TOOLS ALL-IN-ONE (UNIVERSAL WEB DASHBOARD)"
echo "======================================================================"
echo ""

# Install requirements if needed
pip install -r requirements.txt --quiet

echo ""
echo "Menjalankan Web Server di Port 8000..."
echo "Akses dari browser lokal: http://localhost:8000"
echo "Akses dari HP (satu jaringan): http://$(hostname -I 2>/dev/null | awk '{print $1}'):8000"
echo "======================================================================"
echo ""

python3 server.py
