#!/usr/bin/env python3
"""Server Web Shopee Tools All-in-One (Universal Web GUI).

FastAPI backend yang menyediakan:
1. Manajemen autentikasi Telegram via Telethon StringSession (multi-user, terisolasi)
2. WebSocket untuk live progress & log pengecekan Shopee Tools (@shp_tools_bot)
3. REST API untuk parse file/daftar akun dan export hasil
"""

import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    FloodWaitError,
)
from telethon.sessions import StringSession

import shopee_core
import web_checker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ShopeeWebServer")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SESSION_DOWNLOADS_DIR = BASE_DIR / "downloads" / "sessions"

app = FastAPI(title="Shopee Tools Web Universal", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Mounting static files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{8,64}$")


def validate_session_id(session_id: str) -> str:
    """Validasi ketat session ID untuk mencegah path traversal dan injection."""
    clean = (session_id or "").strip()
    if not SESSION_ID_REGEX.fullmatch(clean):
        raise HTTPException(status_code=400, detail="ID Sesi tidak valid atau berpotensi berbahaya.")
    return clean


# =====================================================================
# IN-MEMORY SESSION STORE (MULTI-USER ISOLATED)
# =====================================================================

class UserSession:
    def __init__(self, session_id: str):
        self.session_id: str = validate_session_id(session_id)
        self.api_id: Optional[int] = None
        self.api_hash: Optional[str] = None
        self.phone: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self.string_session: Optional[str] = None
        self.client: Optional[TelegramClient] = None
        self.user_info: Optional[Dict[str, Any]] = None
        self.current_task: Optional[asyncio.Task] = None
        self.is_checking: bool = False
        self.stop_requested: bool = False
        self.last_active: float = time.time()
        # Isolasi folder unduhan per-sesi di dalam subdirektori aman
        self.download_dir: Path = (SESSION_DOWNLOADS_DIR / self.session_id).resolve()
        # Proteksi ekstra: pastikan path tidak keluar dari SESSION_DOWNLOADS_DIR
        if not str(self.download_dir).startswith(str(SESSION_DOWNLOADS_DIR.resolve())):
            raise HTTPException(status_code=400, detail="Akses direktori tidak sah.")
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def touch(self):
        self.last_active = time.time()

    async def disconnect(self):
        if self.current_task and not self.current_task.done():
            self.stop_requested = True
            self.current_task.cancel()
        if self.client and self.client.is_connected():
            try:
                await self.client.disconnect()
            except Exception:
                pass


active_sessions: Dict[str, UserSession] = {}


def get_or_create_session(session_id: str) -> UserSession:
    valid_id = validate_session_id(session_id)
    if valid_id not in active_sessions:
        active_sessions[valid_id] = UserSession(valid_id)
    session = active_sessions[valid_id]
    session.touch()
    return session


# Background Task: Pembersih sesi kedaluwarsa otomatis (Garbage Collector)
async def session_garbage_collector():
    """Membersihkan sesi yang tidak aktif > 1 jam untuk mencegah kebocoran memori."""
    while True:
        try:
            await asyncio.sleep(600)  # Cek setiap 10 menit
            now = time.time()
            to_remove = []
            for s_id, s in list(active_sessions.items()):
                # Jika tidak sedang mengecek dan sudah tidak aktif lebih dari 1 jam
                if not s.is_checking and (now - s.last_active > 3600):
                    to_remove.append(s_id)
            for s_id in to_remove:
                s = active_sessions.pop(s_id, None)
                if s:
                    await s.disconnect()
                    if s.download_dir.exists():
                        shutil.rmtree(s.download_dir, ignore_errors=True)
                    logger.info(f"[{s_id[:8]}] Sesi kedaluwarsa dibersihkan otomatis.")
        except Exception as e:
            logger.error(f"Error session garbage collector: {e}")


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(session_garbage_collector())


# =====================================================================
# REQUEST & RESPONSE MODELS
# =====================================================================

class SendCodeRequest(BaseModel):
    session_id: str
    api_id: int
    api_hash: str
    phone: str


class VerifyCodeRequest(BaseModel):
    session_id: str
    code: str
    password: Optional[str] = None


class RestoreSessionRequest(BaseModel):
    session_id: str
    api_id: int
    api_hash: str
    string_session: str


class ParseTextRequest(BaseModel):
    text: str


# =====================================================================
# REST ENDPOINTS: AUTENTIKASI TELEGRAM
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Shopee Web Server Aktif</h1><p>Memuat template...</p>")


@app.post("/api/auth/send-code")
async def send_code_endpoint(req: SendCodeRequest):
    """Mengirim kode OTP login ke Telegram pengguna."""
    session_id = req.session_id.strip()
    api_id = req.api_id
    api_hash = req.api_hash.strip()
    phone = req.phone.strip()

    if api_id <= 0:
        raise HTTPException(status_code=400, detail="API ID harus berupa angka positif.")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise HTTPException(status_code=400, detail="API Hash harus 32 karakter kombinasi huruf & angka.")
    if not phone.startswith("+"):
        raise HTTPException(status_code=400, detail="Nomor telepon harus diawali dengan tanda + (contoh: +6281234567890).")

    session = get_or_create_session(session_id)
    await session.disconnect()

    try:
        # Inisialisasi client baru dengan StringSession kosong
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()

        res = await client.send_code_request(phone)

        session.client = client
        session.api_id = api_id
        session.api_hash = api_hash
        session.phone = phone
        session.phone_code_hash = res.phone_code_hash

        logger.info(f"[{session_id[:8]}] OTP berhasil dikirim ke {phone}")
        return {
            "ok": True,
            "message": f"Kode OTP telah dikirim oleh Telegram ke nomor {phone}.",
            "phone_code_hash": res.phone_code_hash,
        }
    except ApiIdInvalidError:
        raise HTTPException(status_code=400, detail="API ID atau API HASH salah/tidak valid.")
    except PhoneNumberInvalidError:
        raise HTTPException(status_code=400, detail="Format nomor telepon salah.")
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Terlalu banyak permintaan. Silakan tunggu {e.seconds} detik.")
    except Exception as e:
        logger.error(f"Error send-code: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal mengirim kode: {str(e)}")


@app.post("/api/auth/verify-code")
async def verify_code_endpoint(req: VerifyCodeRequest):
    """Memverifikasi kode OTP (dan 2FA jika ada) untuk login."""
    session_id = req.session_id.strip()
    code = req.code.strip()
    password = (req.password or "").strip()

    if session_id not in active_sessions or not active_sessions[session_id].client:
        raise HTTPException(status_code=400, detail="Sesi tidak ditemukan atau kedaluwarsa. Silakan minta OTP ulang.")

    session = active_sessions[session_id]
    session.touch()
    client = session.client

    try:
        if password:
            await client.sign_in(password=password)
        else:
            await client.sign_in(
                phone=session.phone,
                code=code,
                phone_code_hash=session.phone_code_hash,
            )

        # Login sukses! Simpan StringSession
        string_session = client.session.save()
        session.string_session = string_session

        me = await client.get_me()
        user_info = {
            "id": me.id,
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "username": me.username or "",
            "phone": me.phone or session.phone,
        }
        session.user_info = user_info

        logger.info(f"[{session_id[:8]}] Login sukses: {user_info.get('username') or user_info.get('phone')}")
        return {
            "ok": True,
            "message": "Login Telegram berhasil!",
            "string_session": string_session,
            "user": user_info,
        }
    except SessionPasswordNeededError:
        return {
            "ok": False,
            "need_2fa": True,
            "message": "Akun Anda memiliki verifikasi 2 langkah (2FA). Silakan masukkan password 2FA Anda.",
        }
    except PasswordHashInvalidError:
        raise HTTPException(status_code=400, detail="Password 2FA salah.")
    except (PhoneCodeInvalidError, PhoneCodeExpiredError):
        raise HTTPException(status_code=400, detail="Kode OTP salah atau telah kedaluwarsa.")
    except Exception as e:
        logger.error(f"Error verify-code: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal verifikasi: {str(e)}")


@app.post("/api/auth/restore-session")
async def restore_session_endpoint(req: RestoreSessionRequest):
    """Memulihkan login Telegram menggunakan StringSession yang tersimpan di browser."""
    session_id = req.session_id.strip()
    api_id = req.api_id
    api_hash = req.api_hash.strip()
    string_sess = req.string_session.strip()

    if not string_sess:
        raise HTTPException(status_code=400, detail="StringSession kosong.")

    session = get_or_create_session(session_id)
    await session.disconnect()

    try:
        client = TelegramClient(StringSession(string_sess), api_id, api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            raise HTTPException(status_code=401, detail="Sesi Telegram sudah kedaluwarsa. Silakan login ulang.")

        me = await client.get_me()
        user_info = {
            "id": me.id,
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "username": me.username or "",
            "phone": me.phone or "",
        }

        session.client = client
        session.api_id = api_id
        session.api_hash = api_hash
        session.string_session = string_sess
        session.user_info = user_info

        logger.info(f"[{session_id[:8]}] Sesi berhasil dipulihkan: {user_info.get('username') or user_info.get('phone')}")
        return {
            "ok": True,
            "message": "Sesi berhasil dipulihkan!",
            "user": user_info,
        }
    except Exception as e:
        logger.warning(f"Gagal memulihkan sesi: {e}")
        raise HTTPException(status_code=400, detail=f"Gagal memulihkan sesi: {str(e)}")


@app.post("/api/auth/logout")
async def logout_endpoint(data: Dict[str, str]):
    session_id = data.get("session_id", "")
    if session_id in active_sessions:
        session = active_sessions[session_id]
        await session.disconnect()
        # Bersihkan folder download sesi
        if session.download_dir.exists():
            shutil.rmtree(session.download_dir, ignore_errors=True)
        del active_sessions[session_id]
    return {"ok": True, "message": "Berhasil logout."}


@app.get("/api/auth/status/{session_id}")
async def status_endpoint(session_id: str):
    if session_id in active_sessions:
        session = active_sessions[session_id]
        session.touch()
        if session.client and session.client.is_connected() and session.user_info:
            return {
                "authenticated": True,
                "user": session.user_info,
                "is_checking": session.is_checking,
            }
    return {"authenticated": False, "user": None, "is_checking": False}


# =====================================================================
# REST ENDPOINTS: PARSE DAFTAR AKUN
# =====================================================================

@app.post("/api/parse/text")
async def parse_text_endpoint(req: ParseTextRequest):
    usernames = shopee_core.parse_raw_usernames(req.text)
    return {"ok": True, "count": len(usernames), "usernames": usernames}


@app.post("/api/parse/file")
async def parse_file_endpoint(file: UploadFile = File(...)):
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
    content_bytes = await file.read(MAX_FILE_SIZE + 1)
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Ukuran file terlalu besar. Maksimal 2MB.")
    content = content_bytes.decode("utf-8-sig", errors="ignore")
    usernames = shopee_core.parse_raw_usernames(content)
    return {"ok": True, "filename": file.filename, "count": len(usernames), "usernames": usernames}


# =====================================================================
# WEBSOCKET: LIVE PROGRESS & PENGECEKAN INTERAKTIF
# =====================================================================

@app.websocket("/ws/{session_id}")
async def websocket_checker(websocket: WebSocket, session_id: str):
    try:
        session_id = validate_session_id(session_id)
    except HTTPException:
        await websocket.close(code=1008, reason="ID Sesi tidak valid.")
        return

    await websocket.accept()
    session = get_or_create_session(session_id)
    session.touch()

    async def send_json(data: dict):
        try:
            await websocket.send_text(json.dumps(data))
        except Exception:
            pass

    await send_json({
        "type": "connected",
        "message": "Terhubung ke WebSocket Server.",
        "session_id": session_id,
    })

    try:
        while True:
            raw_data = await websocket.receive_text()
            message = json.loads(raw_data)
            action = message.get("action")

            if action == "ping":
                await send_json({"type": "pong", "time": time.time()})
                continue

            elif action == "stop":
                if session.is_checking:
                    session.stop_requested = True
                    await send_json({"type": "log", "level": "warning", "message": "🛑 Permintaan penghentian diterima..."})
                continue

            elif action == "start":
                if session.is_checking:
                    await send_json({"type": "error", "message": "Pengecekan sedang berjalan!"})
                    continue

                if not session.client or not session.client.is_connected() or not session.user_info:
                    await send_json({"type": "error", "message": "Anda belum login Telegram. Silakan login terlebih dahulu."})
                    continue

                raw_usernames = message.get("usernames", [])
                mode = message.get("mode", "both")
                # Batasi jeda minimum 1.5 detik dan maksimum 10 detik agar akun Telegram tidak terkena flood/ban
                step_delay = max(1.5, min(10.0, float(message.get("delay", 2.5))))

                usernames = [u.strip() for u in raw_usernames if u.strip()]
                if not usernames:
                    await send_json({"type": "error", "message": "Daftar username kosong!"})
                    continue

                # Batasi maksimal 500 akun per batch untuk keamanan memori & koneksi
                if len(usernames) > 500:
                    usernames = usernames[:500]
                    await send_json({
                        "type": "log",
                        "level": "warning",
                        "message": "⚠️ Daftar akun dibatasi maksimal 500 akun per batch demi kestabilan server & akun Telegram Anda.",
                    })

                # Jalankan pengecekan sebagai background task per-user
                session.stop_requested = False
                session.is_checking = True

                async def run_check_task():
                    total = len(usernames)
                    stats = {
                        "total": total,
                        "processed": 0,
                        "valid": 0,
                        "invalid": 0,
                        "error": 0,
                    }

                    await send_json({
                        "type": "start",
                        "total": total,
                        "mode": mode,
                        "message": f"Memulai pengecekan {total} akun Shopee (Mode: {mode.upper()})...",
                    })

                    for idx, username in enumerate(usernames, 1):
                        if session.stop_requested:
                            await send_json({
                                "type": "stopped",
                                "message": f"Pengecekan dihentikan oleh pengguna pada akun ke-{idx-1}/{total}.",
                                "stats": stats,
                            })
                            break

                        await send_json({
                            "type": "progress",
                            "current": idx,
                            "total": total,
                            "percent": round((idx - 1) / total * 100, 1),
                            "username": username,
                        })

                        await send_json({
                            "type": "log",
                            "level": "info",
                            "message": f"[{idx}/{total}] Memeriksa @shp_tools_bot untuk '{username}'...",
                        })

                        try:
                            # Panggil checker adapter terisolasi
                            res = await web_checker.check_user_combined(
                                client=session.client,
                                username=username,
                                mode=mode,
                                download_dir=session.download_dir,
                                step_delay=step_delay,
                            )

                            stats["processed"] += 1
                            if res.get("is_valid"):
                                stats["valid"] += 1
                                log_lvl = "success"
                            else:
                                stats["invalid"] += 1
                                log_lvl = "default"

                            await send_json({
                                "type": "result",
                                "index": idx,
                                "total": total,
                                "data": res,
                                "stats": stats,
                            })

                            await send_json({
                                "type": "log",
                                "level": log_lvl,
                                "message": f"[{idx}/{total}] Hasil '{username}': {res['summary_status']}",
                            })

                        except Exception as e:
                            logger.error(f"Error checking user {username}: {e}")
                            stats["error"] += 1
                            await send_json({
                                "type": "log",
                                "level": "error",
                                "message": f"[{idx}/{total}] Gagal memeriksa '{username}': {str(e)}",
                            })

                        # Delay antar akun
                        if idx < total and not session.stop_requested:
                            await asyncio.sleep(step_delay)

                    session.is_checking = False
                    if not session.stop_requested:
                        await send_json({
                            "type": "completed",
                            "total": total,
                            "stats": stats,
                            "message": f"Selesai! Berhasil memeriksa {stats['processed']}/{total} akun. Valid: {stats['valid']}.",
                        })

                session.current_task = asyncio.create_task(run_check_task())

    except WebSocketDisconnect:
        logger.info(f"[{session_id[:8]}] WebSocket terputus.")
    except Exception as e:
        logger.error(f"[{session_id[:8]}] WebSocket exception: {e}")
    finally:
        session.touch()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print("\n" + "=" * 60)
    print("🚀 SHOPEE TOOLS WEB SERVER AKTIF!")
    print("=" * 60)
    print(f"👉 Buka di browser: http://localhost:{port}")
    print(f"👉 Port aktif: {port}")
    print("=" * 60 + "\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
