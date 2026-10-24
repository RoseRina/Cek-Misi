#!/usr/bin/env python3
"""Module Core untuk Otomasi Bot Shopee (@shp_tools_bot) via Telethon.

Menyediakan fungsi terpadu untuk:
1. Otentikasi dan sesi Telegram (dengan opsi penyimpanan konfigurasi lokal)
2. Pengecekan Misi Bayar QRIS (Check-in Koin)
3. Pengecekan Voucher Shopee Food (Diskon 25RB & Ongkir 12RB)
4. Pencatatan hasil ke CSV dan file teks
"""

import asyncio
import csv
from datetime import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError, ApiIdInvalidError, PhoneNumberInvalidError

TARGET_BOT = "@shp_tools_bot"
SESSION_NAME = "cek_misi_termux"
CONFIG_FILE = Path("telegram_config.json")
RESULTS_MISI_FILE = Path("hasil_cek_misi.csv")
RESULTS_FOOD_FILE = Path("hasil_voucher_food.csv")
RESULTS_ALL_FILE = Path("hasil_gabungan.csv")
VALID_FOOD_FILE = Path("valid_food.txt")
RESULTS_MISI_TXT = Path("hasil_cek_misi.txt")
RESULTS_FOOD_TXT = Path("hasil_voucher_food.txt")
RESULTS_ALL_TXT = Path("hasil_gabungan.txt")
DISKON_25K_TXT = Path("diskon_25rb.txt")
MISI_SELESAI_TXT = Path("misi_selesai.txt")
DOWNLOAD_DIR = Path("downloads")

STEP_DELAY = 2.5
POLL_INTERVAL = 0.5
BUTTON_TIMEOUT = 20
RESULT_TIMEOUT = 55


# =====================================================================
# PENGELOLAAN KONFIGURASI & SESI TELEGRAM
# =====================================================================

def load_env_file(env_path: Path = Path(".env")):
    """Membaca file .env jika ada dan memasukkan ke os.environ jika belum ada."""
    if env_path.exists():
        try:
            with env_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass


def load_credentials():
    """Memuat API_ID dan API_HASH dari .env, environment variables, atau file konfigurasi."""
    load_env_file()
    # 1. Cek dari environment variables (.env atau sistem)
    env_api_id = os.getenv("TELEGRAM_API_ID") or os.getenv("API_ID")
    env_api_hash = os.getenv("TELEGRAM_API_HASH") or os.getenv("API_HASH")
    if env_api_id and env_api_hash:
        try:
            api_id = int(env_api_id)
            api_hash = env_api_hash.strip()
            if api_id > 0 and re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
                return api_id, api_hash
        except (ValueError, TypeError):
            pass

    # 2. Cek dari file konfigurasi lokal jika ada
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                api_id = int(data.get("api_id", 0))
                api_hash = str(data.get("api_hash", "")).strip()
                if api_id > 0 and re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
                    return api_id, api_hash
        except Exception:
            pass
    return None, None


def save_credentials(api_id: int, api_hash: str):
    """Menyimpan API_ID dan API_HASH ke file konfigurasi lokal."""
    try:
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump({"api_id": api_id, "api_hash": api_hash}, f, indent=2)
        print("✅ Pengaturan API Telegram berhasil disimpan!")
    except Exception as e:
        print(f"⚠️ Gagal menyimpan pengaturan: {e}")


def reset_credentials():
    """Menghapus konfigurasi dan sesi tersimpan."""
    removed = []
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink(missing_ok=True)
        removed.append(str(CONFIG_FILE))
    session_file = Path(f"{SESSION_NAME}.session")
    if session_file.exists():
        session_file.unlink(missing_ok=True)
        removed.append(str(session_file))
    alt_session = Path("session_checker.session")
    if alt_session.exists():
        alt_session.unlink(missing_ok=True)
        removed.append(str(alt_session))

    if removed:
        print(f"✅ Berhasil mereset data: {', '.join(removed)}")
    else:
        print("ℹ️ Tidak ada data sesi atau konfigurasi tersimpan yang perlu dihapus.")


def get_credentials():
    """Mendapatkan API_ID & API_HASH (dari file atau prompt pengguna)."""
    api_id, api_hash = load_credentials()
    if api_id and api_hash:
        return api_id, api_hash

    print("\n" + "=" * 50)
    print("🔑 KONFIGURASI API TELEGRAM")
    print("=" * 50)
    print("Panduan mendapatkan API ID & HASH ada di file README.md")
    print("(Kunjungi https://my.telegram.org)\n")

    while True:
        try:
            val = input("Masukkan API_ID (angka): ").strip()
            api_id = int(val)
            if api_id <= 0:
                print("❌ API_ID harus angka positif.")
                continue
            break
        except ValueError:
            print("❌ API_ID harus berupa angka.")

    while True:
        api_hash = input("Masukkan API_HASH (32 karakter hex): ").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
            print("❌ API_HASH harus 32 karakter kombinasi huruf & angka.")
            continue
        break

    simpan = input("\nSimpan API ID & Hash di perangkat ini agar tidak perlu ketik lagi? (Y/n): ").strip().casefold()
    if simpan in ("", "y", "ya", "yes"):
        save_credentials(api_id, api_hash)

    return api_id, api_hash


def get_available_telegram_sessions() -> list[str]:
    """Mencari seluruh file sesi Telegram (*.session) yang tersimpan di direktori saat ini."""
    sessions = []
    for p in sorted(Path(".").glob("*.session")):
        base_name = p.stem
        if base_name and base_name not in sessions:
            sessions.append(base_name)
    if not sessions:
        sessions.append(SESSION_NAME)
    return sessions


def create_client(session_name: Optional[str] = None):
    """Membuat instance TelegramClient (bisa menentukan nama sesi untuk multi-worker)."""
    api_id, api_hash = get_credentials()
    session = session_name or SESSION_NAME
    if not session_name and not Path(f"{SESSION_NAME}.session").exists() and Path("session_checker.session").exists():
        session = "session_checker"
    return TelegramClient(session, api_id, api_hash)


async def start_client(client: TelegramClient):
    """Memulai koneksi dan login akun Telegram jika belum login."""
    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        print("\n📱 LOGIN AKUN TELEGRAM")
        print("Nomor telepon gunakan format internasional dengan awalan kode negara (contoh: +6281234567890)")

        def phone_input():
            return input("Nomor telepon Telegram: ").strip()

        def code_input():
            return input("Kode login dari aplikasi Telegram: ").strip()

        def pwd_input():
            try:
                return getpass.getpass("Password 2FA (Enter jika tidak ada): ").strip()
            except Exception:
                return input("Password 2FA (Enter jika tidak ada): ").strip()

        try:
            await client.start(
                phone=phone_input,
                code_callback=code_input,
                password=pwd_input,
            )
        except ApiIdInvalidError:
            print("\n❌ API_ID atau API_HASH tidak valid!")
            print("💡 Silakan reset konfigurasi dengan menu [5] atau jalankan 'python cek_misi_termux.py --reset'")
            raise
        except PhoneNumberInvalidError:
            print("\n❌ Format nomor telepon salah! Pastikan menggunakan kode negara, contoh: +6281234567890.")
            raise


# =====================================================================
# PEMBACAAN & PENGELOLAAN DAFTAR AKUN & RAW COOKIE (BULK / MASSAL)
# =====================================================================

def detect_auth_method(account_str: str) -> str:
    """Mendeteksi apakah input berupa raw cookie Shopee atau username/ID biasa."""
    if not account_str:
        return "username"
    s = account_str.strip()
    cookie_tokens = ("spc_ec", "spc_u", "spc_st", "spc_t_id", "spc_t_iv", "shopee_token", "shopee.co.id")
    lower = s.casefold()
    if any(tok in lower for tok in cookie_tokens):
        return "cookie"
    if ";" in s and "=" in s:
        return "cookie"
    return "username"


def format_account_display(account_str: str, auth_method: str = "auto") -> str:
    """Membuat label ringkas & elegan untuk akun atau raw cookie agar tampilan tabel/log rapi."""
    if not account_str:
        return "-"
    method = detect_auth_method(account_str) if auth_method == "auto" else auth_method
    if method == "cookie":
        uid_match = re.search(r"\bSPC_U=(\d+)", account_str, re.IGNORECASE)
        if uid_match:
            return f"🍪 Cookie (UID: {uid_match.group(1)})"
        ec_match = re.search(r"\bSPC_EC=([a-zA-Z0-9_\-]+)", account_str, re.IGNORECASE)
        if ec_match:
            tok = ec_match.group(1)
            preview = f"{tok[:6]}...{tok[-4:]}" if len(tok) > 12 else tok
            return f"🍪 Cookie (EC: {preview})"
        clean = account_str.strip()
        if len(clean) > 28:
            return f"🍪 Cookie ({clean[:12]}...{clean[-8:]})"
        return f"🍪 Cookie ({clean})"
    return account_str.strip()


def parse_raw_accounts(text: str, auth_method: str = "auto"):
    """Mengekstrak akun/cookie unik dari teks multi-baris.
    
    Jika auth_method == 'cookie' atau teks dideteksi sebagai cookie:
    Parsing dilakukan STRICTLY per baris ([\r\n]+) agar titik koma dan spasi
    di dalam cookie TIDAK memecah data cookie.
    Jika auth_method == 'username':
    Token dipisah oleh koma, spasi, tab, atau baris baru.
    """
    if not text:
        return []

    is_cookie_mode = False
    if auth_method == "cookie":
        is_cookie_mode = True
    elif auth_method == "auto":
        lower = text.casefold()
        if ("spc_ec" in lower or "spc_u" in lower) or (";" in text and "=" in text):
            is_cookie_mode = True

    if is_cookie_mode:
        lines = re.split(r"[\r\n]+", text)
        accounts = []
        seen = set()
        for line in lines:
            clean = line.strip().strip("'\"")
            if clean and not clean.startswith("#") and clean not in seen:
                accounts.append(clean)
                seen.add(clean)
        return accounts
    else:
        tokens = re.split(r"[\r\n,;\t\s]+", text)
        usernames = []
        seen = set()
        for token in tokens:
            clean = token.strip().strip("'\"")
            if clean and not clean.startswith("#") and clean not in seen:
                usernames.append(clean)
                seen.add(clean)
        return usernames


def parse_raw_usernames(text: str):
    """Mengekstrak username unik (backward-compatible wrapper)."""
    return parse_raw_accounts(text, auth_method="auto")


def get_available_txt_files():
    """Mencari file .txt di direktori saat ini yang berisi daftar akun."""
    files = []
    # File yang dikecualikan dari daftar akun input
    ignored_names = {
        VALID_FOOD_FILE.name.casefold(),
        "requirements.txt",
    }
    for p in sorted(Path(".").glob("*.txt")):
        if p.name.casefold() in ignored_names:
            continue
        try:
            content = p.read_text(encoding="utf-8-sig", errors="ignore")
            count = len(parse_raw_usernames(content))
            files.append((p, count))
        except Exception:
            pass
    return files


def get_checked_usernames(mode: str = "misi"):
    """Mengambil daftar username yang sudah berhasil dicek sebelumnya dari file CSV (untuk fitur resume)."""
    checked = set()
    target_csv = None
    if mode == "misi":
        target_csv = RESULTS_MISI_FILE
    elif mode == "food":
        target_csv = RESULTS_FOOD_FILE
    elif mode == "both":
        target_csv = RESULTS_ALL_FILE

    if target_csv and target_csv.is_file():
        try:
            with target_csv.open("r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 4:
                        user = row[1].strip()
                        status = row[3].strip().upper() if len(row) > 3 else ""
                        # Abaikan jika status sebelumnya adalah error koneksi atau flood wait agar bisa diulang
                        if user and "FLOOD" not in status and "TIMEOUT" not in status and "ERROR" not in status:
                            checked.add(user)
        except Exception:
            pass
    return checked


def filter_unprocessed_usernames(usernames, mode: str = "misi"):
    """Menyaring username, mengembalikan daftar yang belum pernah dicek dan jumlah yang dilewati."""
    already_checked = get_checked_usernames(mode)
    to_process = [u for u in usernames if u not in already_checked]
    skipped_count = len(usernames) - len(to_process)
    return to_process, skipped_count


def render_progress_bar(current: int, total: int, width: int = 25):
    """Membuat progress bar ASCII yang rapi untuk terminal."""
    if total <= 0:
        return ""
    percent = (current / total) * 100
    filled = int(width * current // total)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {percent:>5.1f}% ({current}/{total})"


def read_usernames(filepath=None, auth_method: str = "auto"):
    """Membaca daftar akun atau raw cookie dari file teks atau interaktif."""
    if filepath:
        path = Path(filepath).expanduser()
        if not path.is_file():
            raise ValueError(f"File daftar tidak ditemukan: {path}")
        content = path.read_text(encoding="utf-8-sig")
        usernames = parse_raw_accounts(content, auth_method=auth_method)
    else:
        print("\nMasukkan username atau raw cookie Shopee.")
        print("(Bisa satu per baris, atau pisahkan dengan koma/spasi untuk username).")
        print("Tekan Enter dua kali (pada baris kosong) jika sudah selesai:")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip() and lines:
                break
            if line.strip():
                lines.append(line)
        usernames = parse_raw_accounts("\n".join(lines), auth_method=auth_method)

    if not usernames:
        raise ValueError("Daftar akun/cookie kosong.")
    return usernames



# =====================================================================
# HELPER BOT TELEGRAM
# =====================================================================

async def wait_for_button(client, after_id, matches, timeout=BUTTON_TIMEOUT):
    """Menunggu tombol inline bot yang cocok dengan kriteria."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=10)
        candidates = sorted(
            (msg for msg in messages if msg.id > after_id and msg.buttons),
            key=lambda msg: msg.id,
        )
        for msg in candidates:
            for row_index, row in enumerate(msg.buttons):
                for column_index, btn in enumerate(row):
                    label = (btn.text or "").casefold()
                    if matches(label):
                        return msg, row_index, column_index, btn.text
        await asyncio.sleep(POLL_INTERVAL)
    return None


def detect_bot_error(text: str):
    """Mendeteksi pesan kesalahan umum dari bot Shopee."""
    normalized = " ".join((text or "").casefold().split())
    if "akun ini sedang dibatasi" in normalized or "banned" in normalized:
        return "AKUN DIBATASI / BANNED"
    if "akun tidak ditemukan" in normalized or "user not found" in normalized:
        return "AKUN TIDAK DITEMUKAN"
    if (
        "cookie tidak valid" in normalized
        or "invalid cookie" in normalized
        or "cookie expired" in normalized
        or "cookie kadaluarsa" in normalized
        or "cookie sudah kadaluwarsa" in normalized
        or "format cookie salah" in normalized
    ):
        return "COOKIE TIDAK VALID"
    if "akun ini bukan milikmu" in normalized:
        return "BUKAN MILIKMU"
    if "tidak ada voucher" in normalized or "voucher kosong" in normalized:
        return "TIDAK ADA VOUCHER"
    return None


# =====================================================================
# 1. FITUR CEK MISI BAYAR QRIS (CHECK-IN)
# =====================================================================

def parse_qris_result(text: str):
    """Mengekstrak informasi koin QRIS dan status dari teks bot."""
    if not text:
        return None
    lower_text = text.casefold()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    has_misi_header = any(h in lower_text for h in ("misi checkin", "misi check-in", "misi check in", "claim misi"))
    qris_lines = [line for line in lines if "bayar qris" in line.casefold() or "qris" in line.casefold()]

    if not has_misi_header and not qris_lines:
        return None

    line = qris_lines[0] if qris_lines else lines[0]

    # Ekstrak jumlah koin jika ada
    amount = None
    matches = re.findall(r"(?<!\d)([\d.,\s]+)\s*koin\b", line, re.IGNORECASE)
    if not matches and qris_lines:
        matches = re.findall(r"(?<!\d)([\d.,\s]+)\s*koin\b", text, re.IGNORECASE)
    for raw_amount in matches:
        digits = re.sub(r"\D", "", raw_amount)
        if digits:
            amount = int(digits)
            break

    lower_line = line.casefold()
    if "belum" in lower_line:
        status = "BELUM SELESAI"
    elif any(k in lower_line for k in ("selesai", "berhasil", "sukses")):
        status = "SELESAI"
    elif "sudah diclaim" in lower_line or "sudah diklaim" in lower_line:
        status = "SUDAH DICLAIM"
    elif any(k in lower_line for k in ("gagal", "error", "dibatasi")):
        status = "GAGAL"
    else:
        status = "SELESAI" if (amount and amount > 0) else "BELUM SELESAI"

    detail = line.replace("➖", "").replace("✅", "").replace("❌", "").strip()
    return amount, status, detail


async def check_one_mission(client, username: str, auth_method: str = "username"):
    """Memeriksa status Misi Bayar QRIS untuk 1 akun."""
    previous = await client.get_messages(TARGET_BOT, limit=1)
    start_id = previous[0].id if previous else 0
    command = await client.send_message(TARGET_BOT, "/mission")
    start_id = max(start_id, command.id)
    await asyncio.sleep(STEP_DELAY)

    # 1. Klik menu Checkin
    checkin = await wait_for_button(
        client,
        start_id,
        lambda label: any(x in label for x in ("checkin", "check-in", "check in")),
        BUTTON_TIMEOUT,
    )
    if not checkin:
        return None, "GAGAL", "Tombol Misi Check-in tidak ditemukan"
    message, row_idx, col_idx, _ = checkin
    await message.click(row_idx, col_idx)
    start_id = message.id
    await asyncio.sleep(STEP_DELAY)

    # 2. Klik pilihan login (Raw Cookie atau Username/Email/ID)
    effective_method = detect_auth_method(username) if auth_method == "auto" else auth_method
    if effective_method == "cookie":
        login_opt = await wait_for_button(
            client,
            start_id - 1,
            lambda label: "raw cookie" in label or "cookie" in label,
            BUTTON_TIMEOUT,
        )
        btn_err_msg = "Tombol Raw Cookie tidak ditemukan"
    else:
        login_opt = await wait_for_button(
            client,
            start_id - 1,
            lambda label: any(term in label for term in ("username", "email", "user id", "id akun"))
            and "cookie" not in label,
            BUTTON_TIMEOUT,
        )
        btn_err_msg = "Tombol Username / Email / ID tidak ditemukan"

    if not login_opt:
        return None, "GAGAL", btn_err_msg
    message, row_idx, col_idx, _ = login_opt
    await message.click(row_idx, col_idx)
    await asyncio.sleep(STEP_DELAY)

    # 3. Kirim username / cookie
    sent_msg = await client.send_message(TARGET_BOT, username.strip())
    last_seen = {}
    deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=15)
        for msg in sorted((m for m in messages if (m.id > sent_msg.id or m.id >= start_id) and not m.out), key=lambda m: m.id):
            text = (msg.text or "").strip()
            if not text or last_seen.get(msg.id) == text:
                continue
            last_seen[msg.id] = text

            err = detect_bot_error(text)
            if err:
                return None, err, text

            result = parse_qris_result(text)
            if result:
                return result
        await asyncio.sleep(POLL_INTERVAL)

    return None, "TIMEOUT", "Timeout menunggu balasan bot"


def save_mission_result(username: str, coins, status: str, detail: str):
    """Menyimpan hasil cek misi ke file CSV dan TXT."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = RESULTS_MISI_FILE.exists() and RESULTS_MISI_FILE.stat().st_size > 0
    with RESULTS_MISI_FILE.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        if not file_exists:
            writer.writerow(["Tanggal & Waktu", "Username", "Koin Bayar QRIS", "Status", "Keterangan"])
        writer.writerow([
            now_str,
            username,
            coins if coins is not None else "-",
            status,
            detail or "-",
        ])

    # Simpan juga ke file TXT rapi
    try:
        with RESULTS_MISI_TXT.open("a", encoding="utf-8") as f_txt:
            c_str = f"{coins:,} koin" if coins is not None else "-"
            f_txt.write(f"[{now_str}] {username} | Bayar QRIS: {c_str} | Status: {status} | {detail or '-'}\n")
        if status == "SELESAI" or (coins is not None and coins > 0):
            with MISI_SELESAI_TXT.open("a", encoding="utf-8") as f_selesai:
                f_selesai.write(f"{username}\n")
    except Exception:
        pass


# =====================================================================
# 2. FITUR CEK VOUCHER SHOPEE FOOD (DISKON 25RB & ONGKIR 12RB)
# =====================================================================

def validate_voucher_html(file_path: Path):
    """Memeriksa apakah file HTML voucher berisi voucher Diskon 25RB & Ongkir 12RB."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        has_ongkir = (
            ("SPPSH243300087635331" in content)
            or ("Diskon Ongkir Rp12RB" in content)
            or ("12RB" in content and "Ongkir" in content)
        )
        has_diskon = (
            ("SPPSF203300087635331" in content)
            or ("Diskon 100% s.d. Rp25RB" in content)
            or ("25RB" in content and "Diskon" in content)
        )
        return has_diskon, has_ongkir
    except Exception:
        return False, False


async def check_one_food(client, username: str, auth_method: str = "username"):
    """Memeriksa status voucher Shopee Food untuk 1 akun."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    previous = await client.get_messages(TARGET_BOT, limit=1)
    start_id = previous[0].id if previous else 0

    # 1. Kirim /account
    command = await client.send_message(TARGET_BOT, "/account")
    start_id = max(start_id, command.id)
    await asyncio.sleep(STEP_DELAY)

    # 2. Klik tombol "Check Voucher"
    btn_voucher = await wait_for_button(
        client,
        start_id,
        lambda label: "check voucher" in label or "voucher" in label,
        BUTTON_TIMEOUT,
    )
    if not btn_voucher:
        return False, "GAGAL", "Tombol Check Voucher tidak ditemukan", False, False
    message, row_idx, col_idx, _ = btn_voucher
    await message.click(row_idx, col_idx)
    start_id = message.id
    await asyncio.sleep(STEP_DELAY)

    # 3. Klik tombol pilihan login (Raw Cookie atau Username/Email/ID)
    effective_method = detect_auth_method(username) if auth_method == "auto" else auth_method
    if effective_method == "cookie":
        btn_login = await wait_for_button(
            client,
            start_id - 1,
            lambda label: "raw cookie" in label or "cookie" in label,
            BUTTON_TIMEOUT,
        )
        login_err_msg = "Tombol Raw Cookie tidak ditemukan"
    else:
        btn_login = await wait_for_button(
            client,
            start_id - 1,
            lambda label: any(term in label for term in ("username", "email", "id")) and "cookie" not in label,
            BUTTON_TIMEOUT,
        )
        login_err_msg = "Tombol Username/Email/ID tidak ditemukan"

    if not btn_login:
        return False, "GAGAL", login_err_msg, False, False
    message, row_idx, col_idx, _ = btn_login
    await message.click(row_idx, col_idx)
    await asyncio.sleep(STEP_DELAY)

    # 4. Kirim data akun
    sent_msg = await client.send_message(TARGET_BOT, username.strip())

    # 5. Tunggu balasan dokumen HTML atau teks bot
    deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
    account_hash = hashlib.md5(username.encode("utf-8")).hexdigest()[:10]
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", username)[:20] or "user"
    html_path = DOWNLOAD_DIR / f"food_{safe_name}_{account_hash}.html"
    file_received = False

    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=12)
        for msg in sorted((m for m in messages if (m.id > sent_msg.id or m.id >= start_id) and not m.out), key=lambda m: m.id):
            # Cek pesan teks penolakan bot
            text = (msg.text or "").strip()
            err = detect_bot_error(text)
            if err:
                return False, err, text, False, False

            # Cek kiriman file HTML
            if msg.document:
                for attr in msg.document.attributes:
                    fname = getattr(attr, "file_name", "") or ""
                    if fname.casefold().endswith(".html"):
                        await msg.download_media(str(html_path))
                        file_received = True
                        break
            if file_received:
                break
        if file_received:
            break
        await asyncio.sleep(POLL_INTERVAL)

    if not file_received or not html_path.exists():
        return False, "TIMEOUT", "Tidak menerima file HTML voucher dari bot", False, False

    # 6. Validasi isi HTML
    has_25k, has_12k = validate_voucher_html(html_path)

    if has_25k and has_12k:
        status = "MEMENUHI SYARAT"
        detail = "Lengkap (Diskon 25RB & Ongkir 12RB)"
        is_valid = True
    elif has_25k:
        status = "PARSIAL"
        detail = "Hanya Diskon 25RB (Ongkir 12RB tidak ada)"
        is_valid = False
    elif has_12k:
        status = "PARSIAL"
        detail = "Hanya Ongkir 12RB (Diskon 25RB tidak ada)"
        is_valid = False
    else:
        status = "TIDAK MEMENUHI"
        detail = "Tidak ditemukan voucher 25RB maupun 12RB"
        is_valid = False

    return is_valid, status, detail, has_25k, has_12k


def save_food_result(username: str, is_valid: bool, status: str, detail: str, has_25k: bool, has_12k: bool):
    """Menyimpan hasil pengecekan voucher Food ke CSV, TXT, dan daftar akun lolos."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = RESULTS_FOOD_FILE.exists() and RESULTS_FOOD_FILE.stat().st_size > 0
    with RESULTS_FOOD_FILE.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        if not file_exists:
            writer.writerow(["Tanggal & Waktu", "Username", "Status", "Diskon 25RB", "Ongkir 12RB", "Keterangan"])
        writer.writerow([
            now_str,
            username,
            status,
            "ADA" if has_25k else "TIDAK",
            "ADA" if has_12k else "TIDAK",
            detail or "-",
        ])

    try:
        # Simpan juga ke file TXT rapi
        with RESULTS_FOOD_TXT.open("a", encoding="utf-8") as f_txt:
            d25 = "ADA" if has_25k else "TIDAK"
            o12 = "ADA" if has_12k else "TIDAK"
            f_txt.write(f"[{now_str}] {username} | Status: {status} | Diskon 25RB: {d25} | Ongkir 12RB: {o12} | {detail or '-'}\n")

        # Akun dengan Diskon 25RB (baik lengkap maupun parsial)
        if has_25k:
            with DISKON_25K_TXT.open("a", encoding="utf-8") as f_25:
                f_25.write(f"{username}\n")

        # Akun lengkap memenuhi syarat (Diskon 25RB + Ongkir 12RB)
        if is_valid:
            with VALID_FOOD_FILE.open("a", encoding="utf-8") as f_val:
                f_val.write(f"{username}\n")
    except Exception:
        pass


# =====================================================================
# 3. FITUR CEK KEDUANYA (GABUNGAN MISI + FOOD)
# =====================================================================

def save_combined_result(username: str, qris_coins, qris_status: str, food_status: str, food_detail: str):
    """Menyimpan laporan ringkas gabungan ke CSV dan TXT."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_exists = RESULTS_ALL_FILE.exists() and RESULTS_ALL_FILE.stat().st_size > 0
    with RESULTS_ALL_FILE.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        if not file_exists:
            writer.writerow(["Tanggal & Waktu", "Username", "Koin QRIS", "Status Misi QRIS", "Status Voucher Food", "Keterangan Food"])
        writer.writerow([
            now_str,
            username,
            qris_coins if qris_coins is not None else "-",
            qris_status,
            food_status,
            food_detail or "-",
        ])

    try:
        # Simpan juga ke file TXT rapi
        with RESULTS_ALL_TXT.open("a", encoding="utf-8") as f_txt:
            q_str = f"{qris_coins:,} koin" if qris_coins is not None else "-"
            f_txt.write(f"[{now_str}] {username} | QRIS: {q_str} ({qris_status}) | Food: {food_status} ({food_detail or '-'})\n")
    except Exception:
        pass
