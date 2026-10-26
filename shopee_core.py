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
import shutil
import sys
from typing import Optional, List, Dict, Any, Tuple, Set
import unicodedata

from bs4 import BeautifulSoup
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ApiIdInvalidError, PhoneNumberInvalidError

TARGET_BOT = "@shp_tools_bot"
SESSION_NAME = "cek_misi_termux"
CONFIG_FILE = Path("telegram_config.json")
RESULTS_MISI_FILE = Path("hasil_cek_misi.csv")
RESULTS_FOOD_FILE = Path("hasil_voucher_food.csv")
RESULTS_ALL_FILE = Path("hasil_gabungan.csv")
RESULTS_GANTI_NOMOR_FILE = Path("hasil_ganti_nomor.csv")
RESULTS_CLAIM_FILE = Path("hasil_klaim.csv")
VALID_FOOD_FILE = Path("valid_food.txt")
RESULTS_MISI_TXT = Path("hasil_cek_misi.txt")
RESULTS_FOOD_TXT = Path("hasil_voucher_food.txt")
RESULTS_ALL_TXT = Path("hasil_gabungan.txt")
RESULTS_GANTI_NOMOR_TXT = Path("hasil_ganti_nomor.txt")
RESULTS_CLAIM_TXT = Path("bot_responses.txt")
REEDEM_GANTI_NOMOR_TXT = Path("reedem_gantinomor.txt")
DISKON_25K_TXT = Path("diskon_25rb.txt")
MISI_SELESAI_TXT = Path("misi_selesai.txt")
DOWNLOAD_DIR = Path("downloads")
LAST_DETECTED_CHANGE_NUMBER_LABEL: Optional[str] = None

STEP_DELAY = 2.5
POLL_INTERVAL = 0.5
BUTTON_TIMEOUT = 20
RESULT_TIMEOUT = 55

# Inisialisasi pewarnaan terminal (fallback aman jika colorama tidak terpasang)
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    CYAN = Fore.CYAN
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    WHITE = Fore.WHITE
    MAGENTA = Fore.MAGENTA
    BOLD = Style.BRIGHT
    DIM = getattr(Style, "DIM", "\033[2m")
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


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


def get_checked_accounts_records(mode: str = "misi") -> Dict[str, Dict[str, Any]]:
    """Mengambil data riwayat akun yang sudah berhasil dicek dari CSV (bukan status TIMEOUT/ERROR/FLOOD).
    
    Mengembalikan dict mapping username/account -> {
        "account": row_user,
        "display": row_user,
        "status": st,
        "detail": detail,
        "date": date_str,
        "is_success": bool,
    }
    """
    records: Dict[str, Dict[str, Any]] = {}
    target_csv = None
    if mode == "misi":
        target_csv = RESULTS_MISI_FILE
    elif mode == "food":
        target_csv = RESULTS_FOOD_FILE
    elif mode == "both":
        target_csv = RESULTS_ALL_FILE
    elif mode == "ganti_nomor":
        target_csv = RESULTS_GANTI_NOMOR_FILE
    elif mode == "claim":
        try:
            import voucher_claim
            return voucher_claim.get_checked_claim_records()
        except Exception:
            return {}

    if target_csv and target_csv.is_file():
        try:
            with target_csv.open("r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 3:
                        date_str = row[0].strip() if len(row) > 0 else "-"
                        user = row[1].strip()
                        if not user:
                            continue

                        coins = None
                        if mode == "food":
                            # Kolom CSV Food: [Tanggal & Waktu, Username, Status, Diskon 25RB, Ongkir 12RB, Keterangan]
                            st = row[2].strip() if len(row) > 2 else ""
                            d25 = row[3].strip() if len(row) > 3 else "-"
                            o12 = row[4].strip() if len(row) > 4 else "-"
                            ket = row[5].strip() if len(row) > 5 else "-"
                            detail = f"Diskon 25RB: {d25}, Ongkir 12RB: {o12} ({ket})"
                        elif mode == "both":
                            # Kolom CSV Both: [Tanggal & Waktu, Username, Koin, Status Misi, Status Food, Keterangan]
                            coins = row[2].strip() if len(row) > 2 else "-"
                            st_misi = row[3].strip() if len(row) > 3 else ""
                            st_food = row[4].strip() if len(row) > 4 else ""
                            ket = row[5].strip() if len(row) > 5 else "-"
                            st = f"{st_misi} | {st_food}"
                            detail = f"QRIS: {coins} koin ({st_misi}) | Food: {st_food} ({ket})"
                        elif mode == "ganti_nomor":
                            # Kolom CSV Ganti Nomor: [Tanggal & Waktu, Akun, Status, Keterangan]
                            st = row[2].strip() if len(row) > 2 else ""
                            ket = row[3].strip() if len(row) > 3 else "-"
                            detail = ket
                        else:  # "misi"
                            # Kolom CSV Misi: [Tanggal & Waktu, Username, Koin, Status, Keterangan]
                            coins = row[2].strip() if len(row) > 2 else "-"
                            st = row[3].strip() if len(row) > 3 else ""
                            ket = row[4].strip() if len(row) > 4 else "-"
                            detail = f"Bayar QRIS: {coins} koin ({st}) - {ket}"

                        is_err = any(err in st.upper() for err in ("FLOOD", "TIMEOUT", "ERROR"))
                        records[user] = {
                            "account": user,
                            "display": user,
                            "status": st,
                            "detail": detail,
                            "date": date_str,
                            "is_success": not is_err,
                        }
        except Exception:
            pass
    return records


def find_matching_record(acc: str, records: Dict[str, Dict[str, Any]], auth_method: str = "auto") -> Optional[Dict[str, Any]]:
    """Mencari rekaman hasil lama untuk akun, mendukung perbandingan username mentah maupun masked display."""
    if not acc or not records:
        return None
    if acc in records:
        return records[acc]
    clean = acc.strip()
    if clean in records:
        return records[clean]
    disp = format_account_display(acc, auth_method)
    if disp in records:
        return records[disp]
    return None


def get_checked_usernames(mode: str = "misi"):
    """Mengambil daftar username yang sudah berhasil dicek sebelumnya dari file CSV (untuk fitur resume)."""
    records = get_checked_accounts_records(mode)
    return {user for user, rec in records.items() if rec.get("is_success")}


def filter_unprocessed_usernames(usernames, mode: str = "misi"):
    """Menyaring username, mengembalikan daftar yang belum pernah dicek dan jumlah yang dilewati."""
    already_checked = get_checked_usernames(mode)
    to_process = [u for u in usernames if u not in already_checked]
    skipped_count = len(usernames) - len(to_process)
    return to_process, skipped_count


def handle_reuse_or_recheck_wizard(
    usernames: List[str],
    mode: str = "misi",
    auth_method: str = "auto",
    auto_mode: Optional[str] = None,
) -> Tuple[str, List[str], List[Dict[str, Any]], Set[str]]:
    """Wizard interaktif untuk menentukan pemakaian hasil lama (reuse) vs cek ulang per akun.
    
    Menu Pilihan:
      [1] Pakai hasil lama, lewati yang sudah sukses (default jika tekan Enter)
      [2] Cek ulang semua akun (abaikan hasil lama untuk penentuan antrean)
      [3] Pilih per akun: mana yang dicek ulang, mana yang pakai hasil lama
      [b] Kembali ke langkah sebelumnya (ganti sumber akun)

    Mengembalikan:
      (action, to_process, reused_records, recheck_targets)
      action: "proceed" (siap eksekusi antrean), "finish" (selesai tanpa antrean), atau "back" (kembali)
      to_process: daftar akun yang akan dicek bot di run ini
      reused_records: daftar dict hasil lama yang dipakai ulang
      recheck_targets: set akun yang dicek ulang (untuk proteksi penimpaan saat timeout/error)
    """
    if not usernames:
        return "proceed", [], [], set()

    if mode == "claim":
        import voucher_claim
        action, to_proc, reused, recheck, _ = voucher_claim.handle_claim_reuse_wizard(
            usernames=usernames,
            auth_method=auth_method,
            auto_mode=auto_mode,
        )
        return action, to_proc, reused, recheck

    records = get_checked_accounts_records(mode)
    csv_name = {
        "misi": RESULTS_MISI_FILE.name,
        "food": RESULTS_FOOD_FILE.name,
        "both": RESULTS_ALL_FILE.name,
        "ganti_nomor": RESULTS_GANTI_NOMOR_FILE.name,
        "claim": RESULTS_CLAIM_FILE.name,
    }.get(mode, "CSV")

    success_accounts = []
    unprocessed_accounts = []

    for acc in usernames:
        rec = find_matching_record(acc, records, auth_method)
        if rec and rec.get("is_success"):
            rec_copy = dict(rec)
            rec_copy["display"] = format_account_display(acc, auth_method)
            rec_copy["account"] = acc
            success_accounts.append((acc, rec_copy))
        else:
            unprocessed_accounts.append(acc)

    # Jika tidak ada satupun akun yang pernah sukses, langsung proses semua akun tanpa bertanya
    if not success_accounts:
        return "proceed", usernames, [], set()

    # Mode otomatis (misal dari flag CLI --resume)
    if auto_mode == "reuse":
        to_process = list(unprocessed_accounts)
        reused = [rec for _, rec in success_accounts]
        if not to_process:
            return "finish", [], reused, set()
        return "proceed", to_process, reused, set()

    while True:
        print(f"\n{GREEN}ℹ️  Ditemukan {len(success_accounts)} dari {len(usernames)} akun sudah ada hasil sukses di CSV ({csv_name}).{RESET}")
        print(f"{CYAN}{BOLD}PILIH OPSI PEMROSESAN HASIL:{RESET}")
        print(f"  [1] Pakai hasil lama, lewati yang sudah sukses (default)")
        print(f"  [2] Cek ulang semua akun (abaikan hasil lama untuk penentuan antrean)")
        print(f"  [3] Pilih per akun: mana yang dicek ulang, mana yang pakai hasil lama")
        print(f"  [b] Kembali ke langkah sebelumnya (ganti sumber akun)")

        pilihan = input(f"\n{WHITE}Pilih opsi [1/2/3/b, default: 1]: {RESET}").strip().casefold()

        if pilihan in ("", "1", "default", "y", "ya", "yes"):
            to_process = list(unprocessed_accounts)
            reused = [rec for _, rec in success_accounts]

            # Jika semua akun terlewati (to_process kosong)
            if not to_process:
                print(f"\n{CYAN}{BOLD}===================================================={RESET}")
                print(f"♻️  {GREEN}{BOLD}RINGKASAN HASIL LAMA YANG DIPAKAI ULANG ({len(reused)} Akun):{RESET}")
                print(f"{CYAN}===================================================={RESET}")
                for idx, r in enumerate(reused, 1):
                    print(f"  [{idx}] {r['display']} | Status: {r['status']} | {r['detail']} | Tanggal: {r['date']}")
                print(f"\n{WHITE}Semua akun dalam daftar sudah selesai dicek sebelumnya.{RESET}")
                print("Pilihan:")
                print("  [1] Selesai, pakai hasil lama ini saja (default)")
                print("  [2] Cek ulang sebagian (masuk ke pilihan per akun)")
                print("  [3] Cek ulang semua")

                sub_c = input(f"{WHITE}Pilih [1/2/3, default: 1]: {RESET}").strip()
                if sub_c in ("", "1"):
                    return "finish", [], reused, set()
                elif sub_c == "2":
                    pilihan = "3"
                elif sub_c == "3":
                    recheck_set = set(acc for acc, _ in success_accounts)
                    return "proceed", usernames, [], recheck_set
                else:
                    return "finish", [], reused, set()

            if pilihan != "3":
                return "proceed", to_process, reused, set()

        if pilihan == "2":
            recheck_set = set(acc for acc, _ in success_accounts)
            return "proceed", usernames, [], recheck_set

        elif pilihan == "3":
            print(f"\n{CYAN}{BOLD}📋 DAFTAR AKUN YANG SUDAH MEMILIKI HASIL SUKSES:{RESET}")
            for idx, (acc, rec) in enumerate(success_accounts, 1):
                disp = format_account_display(acc, auth_method)
                print(f"  [{idx}] {disp} | Status: {rec['status']} | {rec['detail']} | Tanggal: {rec['date']}")

            print(f"\n{WHITE}Ketik nomor akun yang ingin DICEK ULANG (pisahkan dengan koma atau spasi, misal '1,3').")
            print(f"Ketik 'semua' untuk cek ulang semua, atau Enter / 'tidak ada' untuk memakai hasil lama semua:{RESET}")

            while True:
                pilih_str = input(f"{WHITE}Nomor akun yang dicek ulang [default: tidak ada]: {RESET}").strip()
                if not pilih_str or pilih_str.casefold() in ("tidak ada", "none"):
                    chosen_indices = []
                    break
                elif pilih_str.casefold() in ("semua", "all"):
                    chosen_indices = list(range(1, len(success_accounts) + 1))
                    break
                else:
                    tokens = [t.strip() for t in re.split(r"[,;\s]+", pilih_str) if t.strip()]
                    valid = True
                    temp_indices = []
                    for tok in tokens:
                        if not tok.isdigit():
                            print(f"{RED}❌ Input '{tok}' bukan angka valid! Masukkan nomor urut 1-{len(success_accounts)}.{RESET}")
                            valid = False
                            break
                        num = int(tok)
                        if num < 1 or num > len(success_accounts):
                            print(f"{RED}❌ Nomor '{num}' di luar rentang (1-{len(success_accounts)})! Silakan coba lagi.{RESET}")
                            valid = False
                            break
                        if num not in temp_indices:
                            temp_indices.append(num)
                    if valid:
                        chosen_indices = temp_indices
                        break

            chosen_set = set(chosen_indices)
            recheck_accs = [success_accounts[i - 1][0] for i in chosen_indices]
            recheck_targets = set(recheck_accs)
            reused = [success_accounts[i - 1][1] for i in range(1, len(success_accounts) + 1) if i not in chosen_set]

            # Pertahankan urutan asli usernames
            to_process = [acc for acc in usernames if acc in unprocessed_accounts or acc in recheck_targets]

            # Jika setelah pilihan per akun to_process tetap kosong
            if not to_process:
                print(f"\n{CYAN}{BOLD}===================================================={RESET}")
                print(f"♻️  {GREEN}{BOLD}RINGKASAN HASIL LAMA YANG DIPAKAI ULANG ({len(reused)} Akun):{RESET}")
                print(f"{CYAN}===================================================={RESET}")
                for idx, r in enumerate(reused, 1):
                    print(f"  [{idx}] {r['display']} | Status: {r['status']} | {r['detail']} | Tanggal: {r['date']}")
                print(f"\n{WHITE}Semua akun dalam daftar sudah selesai dicek sebelumnya.{RESET}")
                print("Pilihan:")
                print("  [1] Selesai, pakai hasil lama ini saja (default)")
                print("  [2] Cek ulang sebagian (masuk ke pilihan per akun)")
                print("  [3] Cek ulang semua")

                sub_c = input(f"{WHITE}Pilih [1/2/3, default: 1]: {RESET}").strip()
                if sub_c in ("", "1"):
                    return "finish", [], reused, set()
                elif sub_c == "2":
                    continue
                elif sub_c == "3":
                    recheck_set = set(acc for acc, _ in success_accounts)
                    return "proceed", usernames, [], recheck_set
                else:
                    return "finish", [], reused, set()

            return "proceed", to_process, reused, recheck_targets

        elif pilihan in ("b", "back", "kembali"):
            return "back", [], [], set()

        else:
            print(f"{YELLOW}⚠️ Pilihan '{pilihan}' tidak valid! Silakan pilih 1, 2, 3, atau b.{RESET}")


def render_combined_execution_summary(
    mode: str,
    total_all: int,
    total_processed: int,
    new_success: int,
    new_fail: int,
    new_error: int,
    reused_records: Optional[List[Dict[str, Any]]] = None,
    preserved_records: Optional[List[Dict[str, Any]]] = None,
    auth_method: str = "auto",
) -> str:
    """Menghasilkan teks laporan akhir 3 kelompok: baru dicek, dipakai ulang, dan total gabungan."""
    reused = reused_records or []
    preserved = preserved_records or []
    total_reused = len(reused)
    total_preserved = len(preserved)
    total_success_combined = new_success + total_reused + total_preserved

    csv_name = {
        "misi": RESULTS_MISI_FILE.name,
        "food": RESULTS_FOOD_FILE.name,
        "both": RESULTS_ALL_FILE.name,
        "ganti_nomor": RESULTS_GANTI_NOMOR_FILE.name,
    }.get(mode, "CSV")
    txt_name = {
        "misi": RESULTS_MISI_TXT.name,
        "food": RESULTS_FOOD_TXT.name,
        "both": RESULTS_ALL_TXT.name,
        "ganti_nomor": RESULTS_GANTI_NOMOR_TXT.name,
    }.get(mode, "TXT")

    lines = []
    lines.append(f"{CYAN}{BOLD}======================================================================{RESET}")
    lines.append(f"📊 {BOLD}LAPORAN RINGKASAN AKHIR EKSEKUSI (REKAPITULASI GABUNGAN){RESET}")
    lines.append(f"{CYAN}======================================================================{RESET}")
    lines.append(f"🎯 Total Keseluruhan Akun : {BOLD}{total_all} akun{RESET}")
    lines.append("")

    # [A] BARU DICEK DI RUN INI
    lines.append(f"{CYAN}[A] HASIL DICEK DI RUN INI ({total_processed} akun):{RESET}")
    if total_processed > 0:
        lines.append(f"    ✅ Sukses / Valid        : {GREEN}{BOLD}{new_success}{RESET} akun")
        lines.append(f"    ⚠️  Gagal / Belum Memenuhi : {YELLOW}{new_fail}{RESET} akun")
        lines.append(f"    ❌ Error / Timeout       : {RED}{new_error}{RESET} akun")
        if total_preserved > 0:
            lines.append(f"    🛡️  Hasil Lama Dipertahankan: {GREEN}{BOLD}{total_preserved}{RESET} akun (cek ulang timeout/error)")
    else:
        lines.append(f"    ℹ️  Tidak ada akun yang dicek di run ini (semua memakai hasil sukses sebelumnya).")
    lines.append("")

    # [B] DIPAKAI ULANG DARI HASIL LAMA
    lines.append(f"{CYAN}[B] DIPAKAI ULANG DARI HASIL LAMA ({total_reused} akun):{RESET}")
    if total_reused > 0:
        for idx, rec in enumerate(reused, 1):
            disp = rec.get("display") or format_account_display(rec.get("account", "-"), auth_method)
            st = rec.get("status", "-")
            det = rec.get("detail", "-")
            dt = rec.get("date", "-")
            lines.append(f"    [{idx}] {disp} | Status: {st} | {det} | Tanggal: {dt}")
    else:
        lines.append(f"    ℹ️  Tidak ada akun yang memakai hasil lama (semua akun dicek di antrean run ini).")
    lines.append("")

    # [C] TOTAL REKAPITULASI GABUNGAN
    lines.append(f"{CYAN}[C] TOTAL REKAPITULASI GABUNGAN:{RESET}")
    lines.append(f"    🏆 Total Akun Sukses / Layak : {GREEN}{BOLD}{total_success_combined}{RESET} dari {total_all} akun")
    lines.append(f"    📂 Rincian data tersimpan di: {csv_name} (CSV) & {txt_name} (TXT)")
    lines.append(f"{CYAN}======================================================================{RESET}")

    return "\n".join(lines)


def print_combined_execution_summary(
    mode: str,
    total_all: int,
    total_processed: int,
    new_success: int,
    new_fail: int,
    new_error: int,
    reused_records: Optional[List[Dict[str, Any]]] = None,
    preserved_records: Optional[List[Dict[str, Any]]] = None,
    auth_method: str = "auto",
):
    """Menampilkan laporan ringkasan akhir gabungan langsung ke stdout."""
    print("\n" + render_combined_execution_summary(
        mode=mode,
        total_all=total_all,
        total_processed=total_processed,
        new_success=new_success,
        new_fail=new_fail,
        new_error=new_error,
        reused_records=reused_records,
        preserved_records=preserved_records,
        auth_method=auth_method,
    ) + "\n")


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


def pilih_metode_auth() -> str:
    """Meminta pengguna memilih metode login ke bot Shopee (Langkah A).
    
    Pilihan:
      [1] Username / Email / ID (Standar)
      [2] Raw Cookie (SPC_EC / SPC_U)
      [3] Campuran / Otomatis (Auto-Detect per entri)
    Default eksplisit tertulis di teks prompt: [1/2/3, default: 1].
    """
    print(f"\n{CYAN}{BOLD}🔑 LANGKAH A - PILIH METODE LOGIN BOT (@shp_tools_bot):{RESET}")
    print(f"  [1] 📧 {BOLD}Username / Email / ID{RESET} (Standar - bot minta kode verifikasi/OTP)")
    print(f"  [2] 🍪 {BOLD}Raw Cookie{RESET} (SPC_EC / SPC_U - login instan tanpa OTP)")
    print(f"  [3] 🔄 {BOLD}Campuran / Otomatis{RESET} (Auto-Detect per entri, untuk file campuran)")
    opt = input(f"{WHITE}Pilih metode login [1/2/3, default: 1]: {RESET}").strip()
    if opt == "2":
        return "cookie"
    elif opt == "3":
        return "auto"
    return "username"


def input_manual_account(auth_method: str = "username") -> Optional[str]:
    """Jalur pengisian 1 akun secara manual di terminal (Mode Satuan).
    
    Fitur:
    - Label prompt dinamis sesuai metode di Langkah A
    - Validasi format dan peringatan ketidakcocokan format
    - Preview tersamar (masking) tanpa pernah menampilkan raw cookie utuh
    - Konfirmasi sebelum eksekusi [Y/n], 'r' untuk isi ulang, 'b' untuk kembali ke menu.
    
    Mengembalikan string akun jika dikonfirmasi, atau None jika pengguna membatalkan ('b').
    """
    if auth_method == "cookie":
        prompt_label = "raw cookie Shopee (SPC_EC / SPC_U)"
    elif auth_method == "username":
        prompt_label = "username / email / ID Shopee"
    else:
        prompt_label = "entri akun Shopee (username atau raw cookie)"

    print(f"\n{CYAN}{BOLD}⚡ PENGISIAN MANUAL (1 AKUN){RESET}")
    print(f"  Metode aktif: {BOLD}{auth_method.upper()}{RESET}")
    print(f"  {DIM}(Ketik 'b' untuk kembali ke menu pilihan){RESET}")

    while True:
        raw_val = input(f"\n{WHITE}Masukkan {prompt_label}: {RESET}").strip()

        if not raw_val:
            print(f"{YELLOW}⚠️ Input tidak boleh kosong. Silakan ketik akun atau 'b' untuk kembali.{RESET}")
            continue

        if raw_val.casefold() in ("b", "back", "kembali"):
            return None

        detected = detect_auth_method(raw_val)

        # Cek kesesuaian format dengan metode yang dipilih
        if auth_method == "cookie" and detected != "cookie":
            print(f"\n{YELLOW}⚠️ PERINGATAN: Anda memilih metode Raw Cookie, namun input tidak terdeteksi")
            print(f"   mengandung format cookie Shopee (SPC_EC / SPC_U).{RESET}")
            tanya = input(f"   Tetap lanjutkan dengan akun ini? [y/N/r (isi ulang)/b (kembali), default: N]: ").strip().casefold()
            if tanya in ("r", "ulang", "retry"):
                continue
            elif tanya in ("b", "back", "kembali"):
                return None
            elif tanya not in ("y", "ya", "yes"):
                continue

        elif auth_method == "username" and detected == "cookie":
            print(f"\n{YELLOW}⚠️ PERINGATAN: Anda memilih metode Username / Email / ID, namun input terdeteksi")
            print(f"   berformat Raw Cookie (SPC_EC / SPC_U).{RESET}")
            tanya = input(f"   Tetap lanjutkan dengan cookie ini? [y/N/r (isi ulang)/b (kembali), default: N]: ").strip().casefold()
            if tanya in ("r", "ulang", "retry"):
                continue
            elif tanya in ("b", "back", "kembali"):
                return None
            elif tanya not in ("y", "ya", "yes"):
                continue

        # Preview tersamar (Masked Preview - aman dari pembocoran token/cookie)
        masked_preview = format_account_display(raw_val, auth_method)
        tipe_entri = "Raw Cookie" if detected == "cookie" else "Username/ID"

        print(f"\n{CYAN}{BOLD}🔍 PREVIEW AKUN SATUAN:{RESET}")
        print(f"  • Entri Tersamar : {BOLD}{masked_preview}{RESET}")
        print(f"  • Tipe Terdeteksi: {tipe_entri}")

        conf = input(f"\n{WHITE}Lanjutkan eksekusi akun ini? [Y/n/r (ulang)/b (kembali), default: Y]: {RESET}").strip().casefold()
        if conf in ("r", "ulang", "retry"):
            continue
        elif conf in ("b", "back", "kembali"):
            return None
        elif conf in ("", "y", "ya", "yes"):
            return raw_val
        elif conf in ("n", "no"):
            print(f"{YELLOW}Input dibatalkan. Silakan ketik ulang atau ketik 'b' untuk kembali.{RESET}")
            continue
        else:
            if conf.startswith("y"):
                return raw_val
            print(f"{YELLOW}Pilihan tidak dikenal. Silakan ketik ulang atau ketik 'b' untuk kembali.{RESET}")
            continue


def print_bulk_format_guidance(auth_method: str = "auto"):
    """Menampilkan panduan format file/input bulk yang diharapkan (Langkah 2)
    beserta contoh PALSU yang aman.
    """
    print(f"\n{CYAN}{BOLD}📋 LANGKAH 2 DARI 3: FORMAT YANG DIHARAPKAN{RESET}")
    if auth_method == "cookie":
        print(f"  • Metode : {BOLD}Raw Cookie{RESET}")
        print("  • Format : 1 raw cookie per baris penuh.")
        print("    (JANGAN dipotong dan JANGAN memecah titik koma ';' di dalam cookie).")
        print("  • Contoh baris yang valid (PALSU / AMAN):")
        print(f"    {DIM}SPC_EC=contoh_token_palsu_alpha123; SPC_U=10000001;{RESET}")
        print(f"    {DIM}SPC_EC=contoh_token_palsu_bravo456; SPC_U=10000002;{RESET}")
    elif auth_method == "username":
        print(f"  • Metode : {BOLD}Username / Email / ID{RESET}")
        print("  • Format : 1 username per baris, atau dipisah koma/spasi.")
        print("  • Contoh baris yang valid (PALSU / AMAN):")
        print(f"    {DIM}user_shopee_01{RESET}")
        print(f"    {DIM}user_shopee_02, user_shopee_03{RESET}")
        print(f"    {DIM}user_email_04@gmail.com{RESET}")
    else:  # auto / campuran
        print(f"  • Metode : {BOLD}Campuran / Auto-Detect{RESET}")
        print("  • Format : 1 entri per baris. Username dan Raw Cookie boleh dicampur.")
        print("  • Contoh baris yang valid (PALSU / AMAN):")
        print(f"    {DIM}user_shopee_01{RESET}")
        print(f"    {DIM}SPC_EC=contoh_token_palsu_alpha123; SPC_U=10000001;{RESET}")
        print(f"    {DIM}user_email_02@gmail.com{RESET}")


def pilih_daftar_akun_bulk(auth_method: str = "auto") -> List[str]:
    """Wizard bertahap untuk memilih sumber akun massal (bulk):
    Langkah 1: Pilih sumber (file yang ada / ketik path file lain / paste langsung).
    Langkah 2: Format yang diharapkan sesuai metode (dengan contoh palsu).
    Langkah 3: Preview tersamar & konfirmasi sebelum eksekusi.
    Langkah 4 (Error handling): Jika file tidak ditemukan, kosong, atau format salah,
               tampilkan pesan jelas dan KEMBALI ke Langkah 1.
    """
    while True:
        txt_files = get_available_txt_files()

        print(f"\n{CYAN}{BOLD}===================================================={RESET}")
        print(f"📦 {BOLD}WIZARD BULK - LANGKAH 1 DARI 3: PILIH SUMBER AKUN{RESET}")
        print(f"{CYAN}===================================================={RESET}")
        menu_idx = 1
        file_map = {}

        if txt_files:
            print("  Daftar file teks yang terdeteksi di folder:")
            for path_obj, count in txt_files:
                print(f"  [{menu_idx}] 📄 {BOLD}{path_obj.name}{RESET} ({count} baris)")
                file_map[str(menu_idx)] = path_obj
                menu_idx += 1
            print(f"  [{menu_idx}] 📁 Ketik nama/path file lain")
            other_choice = str(menu_idx)
            menu_idx += 1
            print(f"  [{menu_idx}] ✍️  Paste langsung banyak akun/cookie sekaligus")
            paste_choice = str(menu_idx)
        else:
            print("  [1] 📁 Masukkan nama/path file teks")
            print("  [2] ✍️  Paste langsung banyak akun/cookie sekaligus")
            other_choice = "1"
            paste_choice = "2"

        pilihan = input(f"\n{WHITE}Pilih sumber [1-{menu_idx}]: {RESET}").strip()

        raw_accounts = []
        source_name = ""

        if pilihan in file_map:
            chosen_path = file_map[pilihan]
            source_name = chosen_path.name
            try:
                raw_accounts = read_usernames(chosen_path, auth_method=auth_method)
            except Exception as e:
                print(f"\n{RED}❌ Gagal membaca file '{chosen_path.name}': {e}{RESET}")
                print(f"{YELLOW}👉 Kembali ke Langkah 1 untuk memilih sumber lain.{RESET}")
                continue

        elif pilihan == other_choice:
            fname = input("Masukkan path / nama file: ").strip()
            if not fname:
                print(f"\n{RED}❌ Nama file tidak boleh kosong!{RESET}")
                print(f"{YELLOW}👉 Kembali ke Langkah 1 untuk memilih sumber lain.{RESET}")
                continue
            path_obj = Path(fname).expanduser()
            if not path_obj.is_file():
                print(f"\n{RED}❌ Error: File '{fname}' tidak ditemukan! Silakan periksa kembali path file.{RESET}")
                print(f"{YELLOW}👉 Kembali ke Langkah 1 untuk memilih sumber lain.{RESET}")
                continue
            source_name = path_obj.name
            try:
                raw_accounts = read_usernames(path_obj, auth_method=auth_method)
            except Exception as e:
                print(f"\n{RED}❌ Gagal membaca file '{fname}': {e}{RESET}")
                print(f"{YELLOW}👉 Kembali ke Langkah 1 untuk memilih sumber lain.{RESET}")
                continue

        elif pilihan == paste_choice:
            source_name = "Paste Langsung"
            print_bulk_format_guidance(auth_method)
            print(f"\n{WHITE}Tempel (paste) daftar akun Anda di bawah ini.")
            print(f"Tekan Enter dua kali (pada baris kosong) jika sudah selesai:{RESET}")
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
            if not lines:
                print(f"\n{RED}❌ Input paste kosong! Tidak ada akun yang dimasukkan.{RESET}")
                print(f"{YELLOW}👉 Kembali ke Langkah 1 untuk memilih sumber lain.{RESET}")
                continue
            raw_accounts = parse_raw_accounts("\n".join(lines), auth_method=auth_method)

        else:
            print(f"\n{YELLOW}⚠️ Pilihan tidak valid (harus 1-{menu_idx}). Silakan coba lagi.{RESET}")
            continue

        if not raw_accounts:
            print(f"\n{RED}❌ Error: Sumber '{source_name}' tidak menghasilkan entri akun yang valid.{RESET}")
            print_bulk_format_guidance(auth_method)
            print(f"{YELLOW}👉 Kembali ke Langkah 1 untuk memilih sumber lain.{RESET}")
            continue

        # Jika bukan paste, tampilkan Langkah 2 (Format yang Diharapkan) sebelum Preview
        if pilihan != paste_choice:
            print_bulk_format_guidance(auth_method)

        # Langkah 3: Preview sebelum jalan & konfirmasi
        total_entri = len(raw_accounts)
        cookie_count = sum(1 for a in raw_accounts if detect_auth_method(a) == "cookie")
        username_count = total_entri - cookie_count

        print(f"\n{CYAN}{BOLD}🔍 LANGKAH 3 DARI 3: PREVIEW SEBELUM JALAN{RESET}")
        print(f"  • Sumber        : {BOLD}{source_name}{RESET}")
        print(f"  • Total Entri   : {BOLD}{total_entri} akun{RESET}")
        print(f"  • Rincian Jenis : {username_count} Username/Email/ID, {cookie_count} Raw Cookie")
        print(f"  • Preview 3 Entri Pertama (Tersamar):")
        for p_idx, acc in enumerate(raw_accounts[:3], 1):
            disp = format_account_display(acc, auth_method)
            tipe_entri = "Raw Cookie" if detect_auth_method(acc) == "cookie" else "Username/ID"
            print(f"    [{p_idx}] {disp} ({tipe_entri})")

        conf = input(f"\n{WHITE}Lanjutkan dengan {total_entri} akun ini? [Y/n, ketik 'b' untuk ganti sumber, default: Y]: {RESET}").strip().casefold()
        if conf in ("b", "back", "kembali", "n", "no"):
            print(f"\n{YELLOW}↩️ Membatalkan pilihan sumber. Kembali ke Langkah 1...{RESET}")
            continue
        elif conf in ("", "y", "ya", "yes"):
            return raw_accounts
        else:
            if conf.startswith("y"):
                return raw_accounts
            print(f"\n{YELLOW}Pilihan tidak dipahami. Kembali ke Langkah 1...{RESET}")
            continue
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


def is_bot_intermediate_reply(text: str) -> bool:
    """Mengecek apakah teks respons bot merupakan pesan perantara / loading / prompt input
    yang belum merupakan hasil akhir pengecekan (polling harus terus berlanjut)."""
    raw_str = (text or "").strip()
    if not raw_str:
        return True
    clean = " ".join(raw_str.casefold().split())
    if not clean:
        return True

    # Prioritas utama: jika pesan sudah memuat informasi / daftar misi bot, JANGAN dianggap perantara!
    if any(m in clean for m in ("bayar qris", "misi checkin", "misi check-in", "misi check in", "claim misi", "misi shopeepay")):
        return False

    # 1. Pesan prompt input akun / cookie / link (bukan hasil evaluasi akhir)
    prompt_indicators = (
        "masukkan email",
        "kirim email",
        "masukkan username",
        "kirim username",
        "silakan kirim",
        "silahkan kirim",
        "masukkan id",
        "kirim id",
        "masukkan cookie",
        "kirim cookie",
        "masukkan link",
        "kirim link",
        "email / username / id",
        "email/username/id",
        "silakan masukkan",
        "silahkan masukkan",
        "kirim raw cookie",
    )
    if any(p in clean for p in prompt_indicators):
        return True

    # 2. Pesan konfirmasi pembatalan (hasil klik Batal sebelumnya)
    cancel_confirmations = (
        "dibatalkan",
        "dibatalkan.",
        "proses dibatalkan",
        "proses dibatalkan.",
        "aksi dibatalkan",
        "aksi dibatalkan.",
        "permintaan dibatalkan",
        "permintaan dibatalkan.",
    )
    if clean in cancel_confirmations:
        return True

    # 2b. Pesan konfirmasi/notifikasi login akun perantara (misal: "✅ Login: <user> (12345)")
    # yang dikirim bot sebelum menyajikan menu/daftar misi sebenarnya.
    if ("login:" in clean or "login :" in clean) and not any(k in clean for k in (
        "gagal", "tidak ditemukan", "tidak terdaftar", "tidak valid", "dibatasi", "banned"
    )):
        return True

    # KECUALI jika mengandung kata hasil akhir definitif (prioritaskan hasil akhir jika ada):
    final_indicators = (
        "berhasil",
        "gagal",
        "maaf",
        "tidak memenuhi",
        "sudah diklaim",
        "telah diklaim",
        "sudah pernah",
        "kuota",
        "expired",
        "kadaluwarsa",
        "kedaluwarsa",
        "tidak ditemukan",
        "tidak valid",
        "failed",
        "belum punya nomor",
        "tidak punya nomor",
        "bukan milikmu",
        "dibatasi",
        "banned",
    )
    if any(k in clean for k in final_indicators):
        # Jika ada kata di atas tetapi teksnya murni frasa loading klaim berakhiran titik-titik
        if "klaim" in clean and (clean.endswith("...") or clean.endswith("…")):
            return True
        return False

    # 3. Mengandung simbol loading ⏳ atau ⌛ tanpa kata hasil akhir
    if "⏳" in raw_str or "⌛" in raw_str:
        return True

    # 4. Kalimat klaim yang berakhiran titik-titik proses
    if "klaim" in clean and (clean.endswith("...") or clean.endswith("…")):
        return True

    # 5. Kata kunci proses / loading umum
    loading_keywords = (
        "memproses",
        "sedang memproses",
        "sedang diproses",
        "diproses",
        "mohon tunggu",
        "harap tunggu",
        "tunggu sebentar",
        "antre",
        "antri",
        "loading",
        "processing",
        "please wait",
        "proses checkin",
    )
    if any(k in clean for k in loading_keywords):
        return True

    return False


def detect_bot_definitive_negative(text: str, mode: str = "general") -> Optional[Tuple[str, str]]:
    """Mendeteksi apakah balasan bot merupakan hasil negatif definitif (bukan loading / bukan timeout).
    
    Mengembalikan (status, detail) jika definitif negatif, atau None jika bukan negatif definitif.
    """
    raw_str = (text or "").strip()
    if not raw_str:
        return None

    # Pastikan bukan pesan perantara / loading / prompt input
    if is_bot_intermediate_reply(raw_str):
        return None

    clean = " ".join(raw_str.casefold().split())

    # 1. Pesan kesalahan standar dari detect_bot_error()
    err = detect_bot_error(raw_str)
    if err:
        return err, raw_str

    # 2. Kasus khusus: Akun belum punya nomor HP
    if any(k in clean for k in ("belum punya nomor hp", "belum punya nomor", "tidak punya nomor hp", "tidak memiliki nomor hp")):
        if mode == "ganti_nomor":
            return "GAGAL", "Belum punya nomor HP — ganti lewat /verify"
        return "GAGAL", raw_str

    # 3. Pesan diawali atau mengandung simbol ❌
    if "❌" in raw_str:
        detail = raw_str.replace("❌", "").strip() or raw_str
        return "GAGAL", detail

    # 4. Akun / user tidak ditemukan / tidak terdaftar
    if any(k in clean for k in (
        "tidak ditemukan",
        "user not found",
        "akun tidak ditemukan",
        "tidak terdaftar",
        "akun tidak terdaftar",
        "user tidak terdaftar",
    )):
        return "GAGAL", raw_str

    # 5. Tidak valid / format salah / expired
    if any(k in clean for k in (
        "tidak valid",
        "invalid",
        "voucher tidak valid",
        "cookie tidak valid",
        "invalid cookie",
        "cookie expired",
        "cookie kadaluarsa",
        "cookie sudah kadaluwarsa",
        "format cookie salah",
    )):
        return "GAGAL", raw_str

    # 6. Tidak memenuhi kriteria / syarat klaim
    if (
        "belum memenuhi kriteria" in clean
        or "tidak memenuhi kriteria" in clean
        or "belum memenuhi syarat" in clean
        or "tidak memenuhi syarat" in clean
        or "tidak memenuhi" in clean
        or "belum memenuhi" in clean
        or "ineligible" in clean
        or "not eligible" in clean
    ):
        return "GAGAL", raw_str

    # 7. Kuota habis / limit
    if "kuota" in clean and any(w in clean for w in ("habis", "penuh", "limit", "kosong", "mencapai batas")):
        return "GAGAL", raw_str

    # 8. Kata gagal / ditolak definitif
    if any(k in clean for k in ("gagal", "failed", "ditolak")):
        return "GAGAL", raw_str

    # 9. Maaf ditolak
    if "maaf" in clean and any(w in clean for w in ("tidak", "belum", "gagal", "batal", "bukan")):
        return "GAGAL", raw_str

    return None


def classify_bot_final_reply(text: str, mode: str = "general") -> Optional[Tuple[str, str, str]]:
    """Helper terpusat untuk mengklasifikasikan balasan bot final di seluruh mode cek.
    
    Mengembalikan:
      - None                         : Jika pesan perantara/loading (polling lanjut)
      - ("NEGATIVE", status, detail) : Jika balasan negatif definitif (polling segera berhenti)
    """
    if is_bot_intermediate_reply(text):
        return None

    neg = detect_bot_definitive_negative(text, mode=mode)
    if neg:
        status, detail = neg
        return "NEGATIVE", status, detail

    return None



# =====================================================================
# 1. FITUR CEK MISI BAYAR QRIS (CHECK-IN)
# =====================================================================

def check_has_recheck_button(msg) -> bool:
    """Mengecek apakah pesan bot sudah selesai dan menampilkan tombol Recheck Misi."""
    if not msg or not getattr(msg, "buttons", None):
        return False
    try:
        for row in msg.buttons:
            for btn in row:
                txt = (getattr(btn, "text", "") or "").casefold()
                if any(k in txt for k in ("recheck", "cek ulang", "refresh", "kembali")):
                    return True
    except Exception:
        pass
    return False


def parse_qris_result(text: str, has_finished_button: bool = False):
    """Mengekstrak informasi koin QRIS dan status dari teks bot."""
    if not text:
        return None
    lower_text = text.casefold()

    # 1. Abaikan pesan proses / loading sementara dari bot agar loop menunggu balasan hasil akhir
    loading_keywords = (
        "memproses",
        "sedang memproses",
        "mohon tunggu",
        "tunggu sebentar",
        "loading",
        "diproses",
        "proses checkin",
    )
    if any(k in lower_text for k in loading_keywords):
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    has_misi_header = any(h in lower_text for h in ("misi checkin", "misi check-in", "misi check in", "claim misi", "misi shopeepay"))
    qris_lines = [line for line in lines if "bayar qris" in line.casefold() or "qris" in line.casefold()]

    # Jika baris QRIS ditemukan di dalam teks bot, langsung ekstrak hasilnya
    if qris_lines:
        line = qris_lines[0]

        # Ekstrak jumlah koin jika ada
        amount = None
        matches = re.findall(r"(?<!\d)([\d.,\s]+)\s*koin\b", line, re.IGNORECASE)
        if not matches:
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

        detail = line.replace("➖", "").replace("✅", "").replace("❌", "").replace("⏳", "").replace("⌛", "").strip()
        return amount, status, detail

    # Jika TIDAK ada baris QRIS:
    # HANYA simpulkan "TIDAK ADA MISI QRIS" jika bot SUDAH SELESAI memuat seluruh misi
    # (ditandai dengan munculnya tombol Recheck Misi dan header misi).
    # Jangan langsung keluar di tengah jalan saat bot masih menyusun baris misi!
    if has_finished_button and has_misi_header:
        has_other_missions = any(m in lower_text for m in ("install shopeepay", "isi saldo", "shopeepay", "transfer", "spin"))
        if has_other_missions:
            return None, "TIDAK ADA MISI QRIS", "Misi Bayar QRIS tidak ditemukan di akun ini"

    # Jika bot belum menampilkan baris QRIS dan belum selesai, kembalikan None agar polling terus menunggu
    return None


async def check_one_mission(client, username: str, auth_method: str = "username", debug: bool = False):
    """Memeriksa status Misi Bayar QRIS untuk 1 akun."""
    is_debug = debug or os.getenv("DEBUG") in ("1", "true", "True") or os.getenv("CEK_MISI_DEBUG") == "1"
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
    last_misi_state = None
    deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=15)
        # Hanya periksa pesan bot yang masuk setelah username dikirim
        for msg in sorted((m for m in messages if m.id > sent_msg.id and not m.out), key=lambda m: m.id):
            text = (msg.text or "").strip()
            if not text:
                continue

            has_btn = check_has_recheck_button(msg)
            cache_key = f"{msg.id}_{has_btn}_{text}"
            if last_seen.get(msg.id) == cache_key:
                continue
            last_seen[msg.id] = cache_key

            # Log diagnostik aman (hanya saat debug, kredensial/token selalu disamarkan)
            if is_debug:
                masked_text = text.replace(username.strip(), "[USER]")
                masked_text = re.sub(r"SPC_EC=[^;\s]+", "SPC_EC=[TOKEN]", masked_text)
                masked_text = re.sub(r"SPC_U=\d+", "SPC_U=[UID]", masked_text)
                masked_text = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[EMAIL]", masked_text)
                preview = " ".join(masked_text.split())[:60]
                inter_val = is_bot_intermediate_reply(text)
                qris_val = parse_qris_result(text, has_finished_button=has_btn)
                neg_val = detect_bot_definitive_negative(text, mode="misi")
                print(
                    f"  {CYAN}[DEBUG-MISI]{RESET} id={msg.id} (rel=+{msg.id - sent_msg.id}) | "
                    f"btn={'Y' if has_btn else 'N'} | inter={inter_val} | "
                    f"qris={'HIT' if qris_val else 'None'} | neg={'HIT' if neg_val else 'None'} | "
                    f"text='{preview}'"
                )

            # 1. Abaikan pesan proses / loading / perantara
            if is_bot_intermediate_reply(text):
                continue

            # 2. Error bot umum
            err = detect_bot_error(text)
            if err:
                return None, err, text

            # 3. Hasil QRIS spesifik
            result = parse_qris_result(text, has_finished_button=has_btn)
            if result:
                return result

            # 4. Balasan negatif definitif non-QRIS (misal akun tidak ditemukan, belum punya no HP, dsb.)
            neg = detect_bot_definitive_negative(text, mode="misi")
            if neg:
                status_neg, detail_neg = neg
                return None, status_neg, detail_neg

            # Catat pesan yang memiliki format misi untuk evaluasi akhir jika timeout
            if any(h in text.casefold() for h in ("misi checkin", "misi check-in", "misi check in", "claim misi")):
                last_misi_state = (text, has_btn)

        await asyncio.sleep(POLL_INTERVAL)

    # Jika timeout tetapi bot sempat mengirim daftar misi lengkap tanpa baris QRIS
    if last_misi_state:
        final_text, _ = last_misi_state
        result = parse_qris_result(final_text, has_finished_button=True)
        if result:
            return result
        return None, "TIDAK ADA MISI QRIS", "Misi Bayar QRIS tidak ditemukan di akun ini"

    if is_debug:
        print(f"  {YELLOW}[DEBUG-MISI] Deadline tercapai ({RESULT_TIMEOUT}s). last_misi_state={'Ada' if last_misi_state else 'None'}{RESET}")

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
        if status == "SELESAI":
            with MISI_SELESAI_TXT.open("a", encoding="utf-8") as f_selesai:
                f_selesai.write(f"{username}\n")
    except Exception:
        pass


# =====================================================================
# 2. FITUR CEK VOUCHER SHOPEE FOOD (DISKON 25RB & ONGKIR 12RB)
# =====================================================================

def parse_voucher_cards(html_content: str) -> list[dict]:
    """Mengekstrak seluruh kartu voucher individual (<article class="vc">) dari HTML."""
    if not html_content or not isinstance(html_content, str):
        return []
    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return []

    # Format bot umumnya adalah <article class="vc" ...> atau elemen dengan class 'vc'
    cards = soup.find_all(lambda tag: tag.name in ("article", "div") and "vc" in tag.get("class", []))
    if not cards:
        cards = soup.find_all("article")

    parsed = []
    for card in cards:
        groups = card.get("data-g", "").casefold().split()
        stub_el = card.find(class_=re.compile(r"\bstub\b"))
        stub_classes = stub_el.get("class", []) if stub_el else []
        stub_text = stub_el.get_text(" ", strip=True) if stub_el else ""

        body_el = card.find(class_="body") or card
        title_el = body_el.find(class_="h")
        title_text = title_el.get_text(" ", strip=True) if title_el else ""

        min_el = body_el.find(class_="m")
        min_text = min_el.get_text(" ", strip=True) if min_el else ""

        val_el = body_el.find(class_=re.compile(r"\bv\b"))
        val_classes = val_el.get("class", []) if val_el else []
        val_text = val_el.get_text(" ", strip=True) if val_el else ""

        chips = [c.get_text(" ", strip=True).casefold() for c in body_el.find_all(class_="chip")]
        code_el = body_el.find("code")
        code_text = code_el.get_text(strip=True) if code_el else ""
        raw_text = card.get_text(" ", strip=True)

        parsed.append({
            "groups": groups,
            "stub_classes": stub_classes,
            "stub_text": stub_text,
            "title": title_text,
            "min_spend": min_text,
            "validity": val_text,
            "val_classes": val_classes,
            "chips": chips,
            "code": code_text,
            "raw_text": raw_text,
        })
    return parsed


def _is_food_category(card: dict) -> bool:
    """Memeriksa apakah kartu voucher merupakan kategori ShopeeFood."""
    if "food" in card["groups"]:
        return True
    if any("food" in c.lower() for c in card["stub_classes"]):
        return True
    st = card["stub_text"].casefold()
    if "shopeefood" in st or "shopee food" in st:
        return True
    return False


def _is_no_min_spend(min_text: str) -> bool:
    """Memeriksa apakah syarat belanja adalah tanpa minimum belanja (Rp0)."""
    if not min_text:
        return False
    if re.search(r"tanpa\s*min(?:imum)?(?:\.?\s*belanja)?", min_text, re.IGNORECASE):
        return True
    if re.search(r"min(?:\.?\s*blj|\.?\s*belanja)?\s*(?:rp)?0\b", min_text, re.IGNORECASE):
        return True
    return False


def _is_target_25k_card(card: dict) -> bool:
    """Validasi ketat per kartu untuk voucher ShopeeFood Diskon 100% s.d. 25RB Tanpa Min. Belanja."""
    # 1. Kategori wajib ShopeeFood
    if not _is_food_category(card):
        return False

    # 2. Syarat pembayaran & metode: Tolak SPayLater / PayLater dan kartu bank / pickup
    # Chip "ShopeePay" saja BUKAN SPayLater dan tidak boleh ditolak
    chip_texts = [str(chip).casefold() for chip in card.get("chips", [])]
    has_spaylater_chip = any("spaylater" in chip or "paylater" in chip for chip in chip_texts)
    has_later_code = "later" in card.get("code", "").casefold()
    has_later_stub = any("later" in str(sc).casefold() for sc in card.get("stub_classes", []))
    title_lower = card.get("title", "").casefold()
    has_later_title = "spaylater" in title_lower or "paylater" in title_lower

    if has_spaylater_chip or has_later_code or has_later_stub or has_later_title:
        return False

    bank_keywords = ("kartu debit", "kartu kredit", "debit", "kredit", "btn", "bri", "bni", "bca", "cimb", "mandiri", "dbs", "digibank")
    if any(any(b in chip for b in bank_keywords) for chip in chip_texts) or any(b in title_lower for b in bank_keywords):
        return False
    if any("pickup" in chip for chip in chip_texts) or "pickup" in title_lower:
        return False

    # 3. Status dan masa berlaku: Tolak voucher yang belum mulai atau sudah kedaluwarsa/habis
    val_classes = [str(vc).casefold() for vc in card.get("val_classes", [])]
    validity_lower = card.get("validity", "").casefold()
    if "soon" in val_classes or "mulai" in validity_lower:
        return False
    if any(exp in validity_lower for exp in ("habis", "kadaluwarsa", "kedaluwarsa", "telah berakhir")):
        return False

    # 4. Minimum belanja: Wajib Tanpa Min. Belanja
    if not _is_no_min_spend(card.get("min_spend", "")):
        return False

    # 5. Nilai & jenis diskon: Wajib 100% s.d. 25RB atau kode resmi campaign SPPSF2533 / SPPSF2033
    if re.search(r"^SPPSF2[05]33", card.get("code", ""), re.IGNORECASE):
        return True

    has_100 = bool(re.search(r"100\s*%", card.get("title", "")))
    has_25k = bool(re.search(r"(?:rp)?25(?:\s*rb|\.?000)\b", card.get("title", ""), re.IGNORECASE))
    if has_100 and has_25k:
        other_pct = re.findall(r"(\d+)\s*%", card.get("title", ""))
        if other_pct and any(int(p) != 100 for p in other_pct):
            return False
        return True

    return False


def _is_target_12k_ongkir_card(card: dict) -> bool:
    """Validasi ketat per kartu untuk voucher Diskon Ongkir 12RB ShopeeFood Tanpa Min. Belanja."""
    # 1. Kategori wajib ShopeeFood (bukan gratis ongkir umum marketplace / FSV)
    if not _is_food_category(card):
        return False
    if "fsv" in card.get("stub_classes", []) and "food" not in card.get("groups", []):
        return False

    # 2. Syarat metode: Tolak SPayLater / PayLater (ONGKIRLATER) & bank card khusus
    chip_texts = [str(chip).casefold() for chip in card.get("chips", [])]
    has_spaylater_chip = any("spaylater" in chip or "paylater" in chip for chip in chip_texts)
    has_later_code = "later" in card.get("code", "").casefold()
    has_later_stub = any("later" in str(sc).casefold() for sc in card.get("stub_classes", []))
    title_lower = card.get("title", "").casefold()
    has_later_title = "spaylater" in title_lower or "paylater" in title_lower

    if has_spaylater_chip or has_later_code or has_later_stub or has_later_title:
        return False

    bank_keywords = ("kartu debit", "kartu kredit", "debit", "kredit", "btn", "bri", "bni", "bca", "cimb", "mandiri", "dbs", "digibank")
    if any(any(b in chip for b in bank_keywords) for chip in chip_texts) or any(b in title_lower for b in bank_keywords):
        return False

    # 3. Status dan masa berlaku
    val_classes = [str(vc).casefold() for vc in card.get("val_classes", [])]
    validity_lower = card.get("validity", "").casefold()
    if "soon" in val_classes or "mulai" in validity_lower:
        return False
    if any(exp in validity_lower for exp in ("habis", "kadaluwarsa", "kedaluwarsa", "telah berakhir")):
        return False

    # 4. Minimum belanja: Wajib Tanpa Min. Belanja
    if not _is_no_min_spend(card.get("min_spend", "")):
        return False

    # 5. Nilai diskon: Diskon Ongkir 12RB atau kode resmi campaign SPPSH2433 / SPPSH2033
    if re.search(r"^SPPSH2[04]33", card.get("code", ""), re.IGNORECASE):
        return True

    has_ongkir = bool(re.search(r"ongkir", card.get("title", ""), re.IGNORECASE))
    has_12k = bool(re.search(r"(?:rp)?12(?:\s*rb|\.?000)\b", card.get("title", ""), re.IGNORECASE))
    return has_ongkir and has_12k


def is_shopeefood_25k_voucher(html_content: str) -> bool:
    """Mendeteksi secara ketat voucher ShopeeFood Diskon 100% s.d. Rp25RB
    (Tanpa min. belanja - Pengguna Baru ShopeePay - SPPSF2533...),
    memvalidasi setiap kartu voucher secara individual.
    """
    if not html_content or not isinstance(html_content, str) or not html_content.strip():
        return False

    cards = parse_voucher_cards(html_content)
    if not cards:
        return False

    return any(_is_target_25k_card(c) for c in cards)


def is_shopeefood_ongkir_12k(html_content: str) -> bool:
    """Mendeteksi secara ketat voucher Diskon Ongkir 12RB ShopeeFood
    (Tanpa min. belanja - SPPSH2433...),
    memvalidasi setiap kartu voucher secara individual.
    """
    if not html_content or not isinstance(html_content, str) or not html_content.strip():
        return False

    cards = parse_voucher_cards(html_content)
    if not cards:
        return False

    return any(_is_target_12k_ongkir_card(c) for c in cards)


def verify_html_account_match(html_content_or_path, username: str, fname: str = "") -> bool:
    """Memverifikasi apakah file/konten HTML yang diterima bot benar-benar milik akun yang diminta,
    bukan balasan lama atau akun lain yang tertukar.
    """
    if not username:
        return True

    content = ""
    if isinstance(html_content_or_path, (str, Path)):
        p = Path(html_content_or_path)
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        else:
            content = str(html_content_or_path)

    if not content:
        return False

    user_clean = username.strip().casefold()
    is_cookie = detect_auth_method(username) == "cookie"

    if not is_cookie:
        title_match = re.search(r"<title[^>]*>.*?Voucher\s+([a-zA-Z0-9_\-]+)", content, re.IGNORECASE)
        user_span_match = re.search(r"<span\s+class=[\"']u[\"'][^>]*>([^<]+)</span>", content, re.IGNORECASE)

        extracted_user = None
        if user_span_match:
            extracted_user = user_span_match.group(1).strip().casefold()
        elif title_match:
            extracted_user = title_match.group(1).strip().casefold()

        if extracted_user:
            if extracted_user != user_clean:
                return False

        if fname:
            fname_clean = fname.casefold()
            fname_user_match = re.search(r"voucher[_\-]([a-zA-Z0-9_\-]+)\.html", fname_clean)
            if fname_user_match:
                fname_user = fname_user_match.group(1).casefold()
                if fname_user != user_clean:
                    return False
    else:
        uid_match = re.search(r"\bSPC_U=(\d+)", username)
        if uid_match:
            uid = uid_match.group(1)
            user_span_match = re.search(r"<span\s+class=[\"']u[\"'][^>]*>([^<]+)</span>", content, re.IGNORECASE)
            if user_span_match:
                extracted = user_span_match.group(1).strip()
                if extracted.isdigit() and extracted != uid:
                    return False

    return True


def validate_voucher_html(file_path: Path):
    """Memeriksa apakah file HTML voucher berisi voucher ShopeeFood Diskon 25RB & Ongkir 12RB."""
    try:
        path = Path(file_path)
        if not path.is_file() or path.stat().st_size == 0:
            return False, False
        content = path.read_text(encoding="utf-8", errors="ignore")
        if not content.strip():
            return False, False
        has_diskon = is_shopeefood_25k_voucher(content)
        has_ongkir = is_shopeefood_ongkir_12k(content)
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

    # Bersihkan file lama jika ada agar tidak ada data residu pemeriksaan sebelumnya
    if html_path.exists():
        html_path.unlink(missing_ok=True)

    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=15)
        # HANYA tangani pesan yang masuk setelah data akun dikirim (m.id > sent_msg.id)
        candidates = sorted((m for m in messages if m.id > sent_msg.id and not m.out), key=lambda m: m.id)
        for msg in candidates:
            # Cek pesan teks penolakan / balasan negatif definitif bot (bukan file HTML)
            text = (msg.text or "").strip()
            if text and not is_bot_intermediate_reply(text):
                err = detect_bot_error(text)
                if err:
                    return False, err, text, False, False

                neg = detect_bot_definitive_negative(text, mode="food")
                if neg:
                    status_neg, detail_neg = neg
                    return False, status_neg, detail_neg, False, False

            # Cek kiriman file HTML
            if msg.document:
                for attr in msg.document.attributes:
                    fname = getattr(attr, "file_name", "") or ""
                    if fname.casefold().endswith(".html"):
                        await msg.download_media(str(html_path))
                        if html_path.exists() and html_path.stat().st_size > 0:
                            # Verifikasi kecocokan akun agar balasan tertukar tidak dipakai
                            if verify_html_account_match(html_path, username, fname):
                                file_received = True
                                break
                            else:
                                html_path.unlink(missing_ok=True)
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
        detail = "Lengkap (Diskon 25RB Food + Ongkir 12RB)"
        is_valid = True
    elif has_25k:
        status = "MEMENUHI SYARAT"
        detail = "Diskon 100% s.d. 25RB Food (Tanpa Min. Belanja)"
        is_valid = True
    elif has_12k:
        status = "PARSIAL"
        detail = "Hanya Ongkir 12RB (Voucher Food 25RB tidak ada)"
        is_valid = False
    else:
        status = "TIDAK MEMENUHI"
        detail = "Tidak ada Voucher ShopeeFood 25RB"
        is_valid = False

    return is_valid, status, detail, has_25k, has_12k


def classify_food_status(is_valid: Any, status: Any) -> str:
    """Mengklasifikasikan status pengecekan ke dalam salah satu dari 4 kategori mutlak:
    1. 'VALID'   : Memenuhi Syarat (is_valid=True DAN status='MEMENUHI SYARAT')
    2. 'PARSIAL' : Parsial (is_valid=False DAN status='PARSIAL')
    3. 'INVALID' : Belum Memenuhi (is_valid=False DAN status in ('TIDAK MEMENUHI', 'TIDAK ADA VOUCHER'))
    4. 'ERROR'   : Gagal / Error / Konflik (Timeout, FloodWait, Bot Error, status kosong, atau konflik boolean vs status)
    """
    # 1. Validasi nilai boolean ketat (hanya True atau False asli)
    if is_valid is not True and is_valid is not False:
        return "ERROR"

    st = (status or "").strip().upper() if isinstance(status, str) else ""
    if not st:
        return "ERROR"

    # 2. Kasus is_valid True: wajib berpasangan dengan status MEMENUHI SYARAT
    if is_valid is True:
        if st == "MEMENUHI SYARAT":
            return "VALID"
        # Konflik boolean True dengan status non-valid (misal True tapi status TIMEOUT/TIDAK MEMENUHI)
        return "ERROR"

    # 3. Kasus is_valid False: jika status MEMENUHI SYARAT, ini konflik kritis
    # Jangan otomatis menganggap valid; tandai sebagai ERROR agar dapat ditelusuri
    if st == "MEMENUHI SYARAT":
        return "ERROR"

    # 4. Status Parsial yang sah
    if st == "PARSIAL":
        return "PARSIAL"

    # 5. Status Belum Memenuhi yang sah
    if st in ("TIDAK MEMENUHI", "TIDAK ADA VOUCHER"):
        return "INVALID"

    # 6. Status error, timeout, bot failure, status tak dikenal
    return "ERROR"


def _sync_account_in_file(file_path: Path, username: str, should_contain: bool):
    """Menyelaraskan keberadaan username di file daftar akun txt:
    - Jika should_contain=True: menambahkan username jika belum ada (deduplikasi aman).
    - Jika should_contain=False: menghapus username jika sebelumnya pernah tercatat
      (misal karena status berubah menjadi error/tidak memenuhi pada sesi baru),
      tanpa menghapus akun valid lain yang tidak terkait.
    """
    clean_user = (username or "").strip()
    if not clean_user:
        return

    user_key = clean_user.casefold()

    if not file_path.exists():
        if should_contain:
            try:
                file_path.write_text(f"{clean_user}\n", encoding="utf-8")
            except Exception:
                pass
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
    except Exception:
        lines = []

    existing_keys = {line.casefold() for line in lines}

    if should_contain:
        if user_key not in existing_keys:
            lines.append(clean_user)
            try:
                file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except Exception:
                pass
    else:
        if user_key in existing_keys:
            new_lines = [line for line in lines if line.casefold() != user_key]
            try:
                file_path.write_text(("\n".join(new_lines) + "\n") if new_lines else "", encoding="utf-8")
            except Exception:
                pass


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
        # Simpan juga ke file TXT rapi (riwayat append-only dengan timestamp)
        with RESULTS_FOOD_TXT.open("a", encoding="utf-8") as f_txt:
            d25 = "ADA" if has_25k else "TIDAK"
            o12 = "ADA" if has_12k else "TIDAK"
            f_txt.write(f"[{now_str}] {username} | Status: {status} | Diskon 25RB: {d25} | Ongkir 12RB: {o12} | {detail or '-'}\n")

        # Klasifikasi akhir secara ketat
        final_category = classify_food_status(is_valid, status)

        # 1. KASUS VALID: Berhasil diverifikasi lengkap (Diskon 25RB + Ongkir 12RB)
        if final_category == "VALID":
            _sync_account_in_file(VALID_FOOD_FILE, username, should_contain=True)
            _sync_account_in_file(DISKON_25K_TXT, username, should_contain=True)

        # 2. KASUS INVALID: Hasil negatif berhasil diverifikasi (Akun terbukti tidak punya voucher)
        elif final_category == "INVALID":
            # Hapus akun dari daftar valid_food.txt dan diskon_25rb.txt setelah hasil negatif terkonfirmasi
            _sync_account_in_file(VALID_FOOD_FILE, username, should_contain=False)
            _sync_account_in_file(DISKON_25K_TXT, username, should_contain=False)

        # 3. KASUS PARSIAL: Hasil parsial berhasil diverifikasi
        elif final_category == "PARSIAL":
            # Terbukti bukan valid lengkap, hapus dari valid_food.txt
            _sync_account_in_file(VALID_FOOD_FILE, username, should_contain=False)
            # Untuk diskon_25rb.txt: hanya disimpan/dipertahankan jika voucher 25RB terbukti ADA
            if has_25k:
                _sync_account_in_file(DISKON_25K_TXT, username, should_contain=True)
            else:
                _sync_account_in_file(DISKON_25K_TXT, username, should_contain=False)

        # 4. KASUS ERROR / TIMEOUT / FLOOD_WAIT / KONFLIK:
        # Pemeriksaan gagal/tidak dapat dipastikan. Jangan langsung menganggap voucher sudah hilang.
        # Pertahankan informasi valid terakhir yang diketahui di disk (jangan dihapus dan jangan ditambah).
        # Laporan sesi saat ini tetap mencatat akun ini sebagai ERROR, bukan VALID.
        else:
            pass
    except Exception:
        pass


# =====================================================================
# FORMATTER LAPORAN AKHIR VOUCHER FOOD (TERMUX / TERMINAL)
# =====================================================================

ANSI_REGEX = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')


def get_visible_width(text: str) -> int:
    """Menghitung lebar visual string di terminal (kolom tampilan monospaced),
    mengabaikan escape sequence ANSI dan memperhitungkan karakter double-width (emoji).
    """
    clean = ANSI_REGEX.sub('', text)
    width = 0
    for ch in clean:
        code = ord(ch)
        if ch in ('\ufe0f', '\u200d'):
            continue
        if code < 32 or (127 <= code < 160):
            continue
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ('W', 'F'):
            width += 2
        elif 0x1F300 <= code <= 0x1FAFF or 0x2700 <= code <= 0x27BF or 0x2600 <= code <= 0x26FF:
            if ch in ('★', '─', '│', '╭', '╮', '╰', '╯', '└'):
                width += 1
            else:
                width += 2
        else:
            width += 1
    return width


def render_food_summary_box(
    total_processed: Optional[int] = None,
    valid_count: int = 0,
    invalid_count: int = 0,
    valid_accounts: Optional[List[str]] = None,
    partial_count: int = 0,
    error_count: int = 0,
    box_width: Optional[int] = None,
    show_csv_path: bool = False,
) -> str:
    """Menghasilkan teks ringkasan akhir berbingkai rapi untuk terminal Termux/konsol.

    Menegakkan konsistensi statistik mutlak:
    Total Diproses = Memenuhi Syarat + Belum Memenuhi + Parsial + Gagal/Error
    """
    if valid_accounts is None:
        valid_accounts = []

    # Pastikan Total Diproses konsisten dengan penjumlahan seluruh kategori
    calculated_total = valid_count + invalid_count + partial_count + error_count
    if total_processed is None or total_processed < calculated_total:
        total_processed = calculated_total

    # Auto-detect lebar terminal agar pas di Termux Android
    if box_width is None:
        try:
            term_cols = shutil.get_terminal_size((48, 20)).columns
            if term_cols < 48:
                box_width = max(40, term_cols)
            elif term_cols <= 64:
                box_width = min(term_cols - 2, 48)
            else:
                box_width = 48
        except Exception:
            box_width = 48

    inner_width = max(36, box_width - 2)

    # Kode warna ANSI
    clr_border = '\033[92m'      # Hijau untuk garis bingkai
    clr_title = '\033[1;93m'     # Kuning tebal untuk judul
    clr_cyan = '\033[96m'        # Biru muda / cyan
    clr_green = '\033[92m'       # Hijau untuk status memenuhi syarat
    clr_yellow = '\033[93m'      # Kuning untuk peringatan
    clr_red = '\033[91m'         # Merah untuk gagal/error
    clr_num = '\033[1;96m'       # Angka biru muda tebal
    clr_subtitle = '\033[1;93m'  # Kuning tebal untuk subjudul daftar akun
    clr_reset = '\033[0m'        # Reset warna

    def _make_line(content: str) -> str:
        vis = get_visible_width(content)
        pad = max(0, inner_width - vis)
        return f"{clr_border}│{clr_reset}{content}{' ' * pad}{clr_border}│{clr_reset}"

    top = f"{clr_border}╭{'─' * inner_width}╮{clr_reset}"
    bot = f"{clr_border}╰{'─' * inner_width}╯{clr_reset}"
    empty_line = f"{clr_border}│{clr_reset}{' ' * inner_width}{clr_border}│{clr_reset}"

    title = f"{clr_title}✨ LAPORAN HASIL CHECK VOUCHER ✨{clr_reset}"
    t_vis = get_visible_width(title)
    l_pad = max(0, (inner_width - t_vis) // 2)
    r_pad = max(0, inner_width - t_vis - l_pad)
    title_line = f"{clr_border}│{clr_reset}{' ' * l_pad}{title}{' ' * r_pad}{clr_border}│{clr_reset}"

    lines = [top, title_line, empty_line]

    # Baris statistik utama
    lines.append(_make_line(f" 🎯 {clr_cyan}Total Diproses{clr_reset}     : {clr_num}{total_processed}{clr_reset}"))
    lines.append(_make_line(f" ✅ {clr_green}Memenuhi Syarat{clr_reset}    : {clr_num}{valid_count}{clr_reset}"))
    lines.append(_make_line(f" ⚠️ {clr_yellow}Belum Memenuhi{clr_reset}     : {clr_num}{invalid_count}{clr_reset}"))

    # Status parsial jika ada akun parsial
    if partial_count > 0:
        lines.append(_make_line(f" ⏳ {clr_yellow}Status Parsial{clr_reset}     : {clr_num}{partial_count}{clr_reset}"))

    # Status error jika ada akun yang gagal / timeout
    if error_count > 0:
        lines.append(_make_line(f" ❌ {clr_red}Gagal / Error{clr_reset}      : {clr_num}{error_count}{clr_reset}"))

    lines.append(empty_line)
    lines.append(_make_line(f" {clr_subtitle}★ DAFTAR AKUN MEMENUHI SYARAT ★{clr_reset}"))

    # Daftar username akun lolos (tanpa duplikat, aman dari text-wrapping)
    unique_valid = list(dict.fromkeys(valid_accounts))
    if unique_valid:
        for acc in unique_valid:
            prefix = "       └ "
            prefix_vis = get_visible_width(prefix)
            max_vis = inner_width - prefix_vis
            display_acc = acc
            while get_visible_width(display_acc) > max_vis and len(display_acc) > 0:
                display_acc = display_acc[:-1]
            if len(display_acc) < len(acc):
                display_acc = display_acc[:-3] + "..." if len(display_acc) >= 3 else "..."
            lines.append(_make_line(f"{prefix}{display_acc}"))
    else:
        lines.append(_make_line("       └ (Tidak ada)"))

    lines.append(bot)
    lines.append("")
    lines.append(f"📂 {clr_cyan}Akun valid disimpan di '{VALID_FOOD_FILE.name}'{clr_reset}")
    if show_csv_path:
        lines.append(f"📂 {clr_cyan}Rincian CSV tersimpan di '{RESULTS_FOOD_FILE.name}'{clr_reset}")

    return "\n".join(lines)


def print_food_summary_report(
    total_processed: int,
    valid_count: int,
    invalid_count: int,
    valid_accounts: Optional[List[str]] = None,
    partial_count: int = 0,
    error_count: int = 0,
    box_width: Optional[int] = None,
    show_csv_path: bool = False,
):
    """Menampilkan ringkasan akhir pengecekan voucher Food langsung ke stdout."""
    print("\n" + render_food_summary_box(
        total_processed=total_processed,
        valid_count=valid_count,
        invalid_count=invalid_count,
        valid_accounts=valid_accounts,
        partial_count=partial_count,
        error_count=error_count,
        box_width=box_width,
        show_csv_path=show_csv_path,
    ) + "\n")


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


# =====================================================================
# 4. FITUR CEK GANTI NOMOR (CHECKER ONLY, TANPA MENGUBAH NOMOR)
# =====================================================================

async def wait_for_bot_prompt(client, after_id: int, phrases: List[str], timeout: float = BUTTON_TIMEOUT):
    """Menunggu pesan bot yang meminta input identitas akun."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=10)
        candidates = sorted(
            (msg for msg in messages if msg.id > after_id and not msg.out),
            key=lambda msg: msg.id,
        )
        for msg in candidates:
            content = " ".join((getattr(msg, "text", "") or getattr(msg, "raw_text", "") or "").casefold().split())
            if any(phrase in content for phrase in phrases):
                return msg
        await asyncio.sleep(POLL_INTERVAL)
    return None


async def click_cancel_button(client, msg=None, after_id=None):
    """Mencari dan mengklik tombol 'Batal' setelah klasifikasi selesai.
    
    PRINSIP KEAMANAN:
    - Checker ini TIDAK PERNAH melanjutkan proses perubahan nomor akun.
    - Selalu klik tombol Batal setelah klasifikasi ditemukan.
    - Jangan pernah mengirim kode OTP, password, atau PIN ke bot dalam kondisi apapun.
    """
    # 1. Cek tombol pada pesan target jika ada
    if msg and getattr(msg, "buttons", None):
        for r_idx, row in enumerate(msg.buttons):
            for c_idx, btn in enumerate(row):
                btn_txt = (getattr(btn, "text", "") or "").casefold()
                if "batal" in btn_txt or "cancel" in btn_txt:
                    try:
                        if hasattr(btn, "click") and callable(btn.click):
                            res = btn.click()
                            if asyncio.iscoroutine(res):
                                await res
                        elif hasattr(msg, "click") and callable(msg.click):
                            res = msg.click(r_idx, c_idx)
                            if asyncio.iscoroutine(res):
                                await res
                        return True
                    except Exception:
                        pass

    # 2. Cari di pesan bot terkini jika belum terklik pada msg
    try:
        messages = await client.get_messages(TARGET_BOT, limit=6)
        candidates = sorted(
            (m for m in messages if not m.out and (after_id is None or m.id >= (after_id or 0))),
            key=lambda x: x.id,
            reverse=True,
        )
        for m in candidates:
            if not getattr(m, "buttons", None):
                continue
            for r_idx, row in enumerate(m.buttons):
                for c_idx, btn in enumerate(row):
                    btn_txt = (getattr(btn, "text", "") or "").casefold()
                    if "batal" in btn_txt or "cancel" in btn_txt:
                        try:
                            if hasattr(btn, "click") and callable(btn.click):
                                res = btn.click()
                                if asyncio.iscoroutine(res):
                                    await res
                            elif hasattr(m, "click") and callable(m.click):
                                res = m.click(r_idx, c_idx)
                                if asyncio.iscoroutine(res):
                                    await res
                            return True
                        except Exception:
                            pass
    except Exception:
        pass
    return False


async def check_one_change_number(client, username: str, auth_method: str = "username"):
    """Memeriksa status kelayakan ganti nomor untuk 1 akun.
    
    PRINSIP KEAMANAN:
    - Checker ini TIDAK PERNAH mengganti nomor akun.
    - Selalu klik tombol Batal setelah klasifikasi ditemukan.
    - Jangan pernah mengirim kode OTP, password, atau PIN ke bot dalam kondisi apapun.
    """
    global LAST_DETECTED_CHANGE_NUMBER_LABEL
    clean_user = (username or "").strip()
    if not clean_user:
        return False, "GAGAL", "Identitas akun kosong"

    previous = await client.get_messages(TARGET_BOT, limit=1)
    start_id = previous[0].id if previous else 0

    # 1. Kirim /account
    command = await client.send_message(TARGET_BOT, "/account")
    start_id = max(start_id, command.id)
    await asyncio.sleep(STEP_DELAY)

    # 2. Klik tombol "Ganti Nomor" (fallback "Ubah Nomor")
    btn_gn = await wait_for_button(
        client,
        start_id,
        lambda label: "ganti nomor" in label or "ubah nomor" in label,
        BUTTON_TIMEOUT,
    )
    if not btn_gn:
        return False, "GAGAL", "Tombol Ganti Nomor tidak ditemukan"
    message, row_idx, col_idx, matched_label = btn_gn
    LAST_DETECTED_CHANGE_NUMBER_LABEL = matched_label
    if hasattr(message, "click") and callable(message.click):
        res = message.click(row_idx, col_idx)
        if asyncio.iscoroutine(res):
            await res
    start_id = message.id
    await asyncio.sleep(STEP_DELAY)

    # 3. Klik tombol pilihan metode login sesuai akun
    effective_method = detect_auth_method(clean_user) if auth_method == "auto" else auth_method
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
            lambda label: any(term in label for term in ("username", "email", "user id", "id akun")) and "cookie" not in label,
            BUTTON_TIMEOUT,
        )
        login_err_msg = "Tombol Username / Email / ID tidak ditemukan"

    if not btn_login:
        return False, "GAGAL", login_err_msg
    message, row_idx, col_idx, _ = btn_login
    if hasattr(message, "click") and callable(message.click):
        res = message.click(row_idx, col_idx)
        if asyncio.iscoroutine(res):
            await res
    start_id = message.id
    await asyncio.sleep(STEP_DELAY)

    # 4. Tunggu prompt bot
    prompt_phrases = [
        "masukkan email",
        "kirim email",
        "masukkan username",
        "kirim username",
        "masukkan id",
        "kirim id",
        "email / username / id",
        "email/username/id",
    ]
    if effective_method == "cookie":
        prompt_phrases.extend(["masukkan cookie", "kirim cookie", "cookie"])

    prompt_msg = await wait_for_bot_prompt(client, start_id, prompt_phrases, BUTTON_TIMEOUT)
    if not prompt_msg:
        return False, "GAGAL", "Prompt input identitas akun tidak muncul dari bot"
    start_id = prompt_msg.id
    await asyncio.sleep(STEP_DELAY)

    # 5. Kirim identitas akun
    sent_msg = await client.send_message(TARGET_BOT, clean_user)

    # 6. Polling balasan bot
    deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=15)
        replies = sorted(
            (m for m in messages if m.id > sent_msg.id and not m.out),
            key=lambda m: m.id,
        )
        for msg in replies:
            text = (getattr(msg, "text", "") or getattr(msg, "raw_text", "") or "").strip()
            if not text:
                continue
            lower_text = text.casefold()

            # 1. Abaikan pesan perantara / loading / prompt input / konfirmasi pembatalan
            if is_bot_intermediate_reply(text):
                continue

            # 2. Deteksi error bot standar
            err = detect_bot_error(text)
            if err:
                await click_cancel_button(client, msg, sent_msg.id)
                return False, err, text

            # 3. Kasus spesifik: Akun belum punya nomor HP
            if any(k in lower_text for k in ("belum punya nomor hp", "belum punya nomor", "tidak punya nomor hp", "tidak memiliki nomor hp")):
                if getattr(msg, "buttons", None):
                    await click_cancel_button(client, msg, sent_msg.id)
                return False, "GAGAL", "Belum punya nomor HP — ganti lewat /verify"

            # 4. Deteksi OTP
            has_otp = (
                "otp akan dikirim" in lower_text
                or "verifikasi lewat otp" in lower_text
                or bool(re.search(r"\botp\b", lower_text))
            )
            if has_otp:
                await click_cancel_button(client, msg, sent_msg.id)
                return False, "GAGAL", "Meminta OTP — dibatalkan, tidak dilanjutkan"

            # 5. Deteksi Pilih Metode / Verifikasi Identitas
            if "pilih metode" in lower_text or "butuh verifikasi identitas" in lower_text:
                has_password_or_pin = False
                buttons = getattr(msg, "buttons", None) or []
                for row in buttons:
                    for btn in row:
                        btn_txt = (getattr(btn, "text", "") or "").casefold()
                        if "password" in btn_txt or "pin shopeepay" in btn_txt:
                            has_password_or_pin = True
                            break
                    if has_password_or_pin:
                        break

                if has_password_or_pin:
                    await click_cancel_button(client, msg, sent_msg.id)
                    return True, "SUKSES", "Butuh Password/PIN — dibatalkan, tercatat layak"
                else:
                    await click_cancel_button(client, msg, sent_msg.id)
                    return False, "GAGAL", "Metode verifikasi bukan Password/PIN — dibatalkan"

            # 6. Deteksi balasan negatif definitif lainnya (misal ❌, gagal, akun tidak terdaftar, dll.)
            neg = detect_bot_definitive_negative(text, mode="ganti_nomor")
            if neg:
                status_neg, detail_neg = neg
                if getattr(msg, "buttons", None):
                    await click_cancel_button(client, msg, sent_msg.id)
                return False, status_neg, detail_neg

        await asyncio.sleep(POLL_INTERVAL)

    # Timeout
    await click_cancel_button(client, after_id=sent_msg.id)
    return False, "TIMEOUT", "Timeout menunggu balasan bot"


def save_ganti_nomor_result(username: str, status: str, detail: str, auth_method: str = "auto"):
    """Menyimpan hasil pengecekan kelayakan ganti nomor ke CSV, TXT, dan daftar akun layak.
    
    Kolom CSV: Tanggal & Waktu, Akun, Status, Keterangan.
    Selalu menggunakan format_account_display() untuk akun cookie agar cookie utuh tidak bocor.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_acc = format_account_display(username, auth_method)
    file_exists = RESULTS_GANTI_NOMOR_FILE.exists() and RESULTS_GANTI_NOMOR_FILE.stat().st_size > 0
    with RESULTS_GANTI_NOMOR_FILE.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        if not file_exists:
            writer.writerow(["Tanggal & Waktu", "Akun", "Status", "Keterangan"])
        writer.writerow([
            now_str,
            display_acc,
            status,
            detail or "-",
        ])

    try:
        with RESULTS_GANTI_NOMOR_TXT.open("a", encoding="utf-8") as f_txt:
            f_txt.write(f"[{now_str}] {display_acc} | Status: {status} | {detail or '-'}\n")

        if status == "SUKSES":
            _sync_account_in_file(REEDEM_GANTI_NOMOR_TXT, display_acc, should_contain=True)
        elif status == "GAGAL":
            _sync_account_in_file(REEDEM_GANTI_NOMOR_TXT, display_acc, should_contain=False)
    except Exception:
        pass


def render_change_number_summary_box(
    total_processed: Optional[int] = None,
    success_count: int = 0,
    fail_count: int = 0,
    error_count: int = 0,
    success_accounts: Optional[List[str]] = None,
    box_width: Optional[int] = None,
    show_csv_path: bool = False,
) -> str:
    """Menghasilkan teks ringkasan akhir berbingkai rapi untuk pengecekan ganti nomor."""
    if success_accounts is None:
        success_accounts = []

    calculated_total = success_count + fail_count + error_count
    if total_processed is None or total_processed < calculated_total:
        total_processed = calculated_total

    if box_width is None:
        try:
            term_cols = shutil.get_terminal_size((48, 20)).columns
            if term_cols < 48:
                box_width = max(40, term_cols)
            elif term_cols <= 64:
                box_width = min(term_cols - 2, 48)
            else:
                box_width = 48
        except Exception:
            box_width = 48

    inner_width = max(36, box_width - 2)

    clr_border = '\033[92m'
    clr_title = '\033[1;93m'
    clr_cyan = '\033[96m'
    clr_green = '\033[92m'
    clr_yellow = '\033[93m'
    clr_red = '\033[91m'
    clr_num = '\033[1;96m'
    clr_subtitle = '\033[1;93m'
    clr_reset = '\033[0m'

    def _make_line(content: str) -> str:
        vis = get_visible_width(content)
        pad = max(0, inner_width - vis)
        return f"{clr_border}│{clr_reset}{content}{' ' * pad}{clr_border}│{clr_reset}"

    top = f"{clr_border}╭{'─' * inner_width}╮{clr_reset}"
    bot = f"{clr_border}╰{'─' * inner_width}╯{clr_reset}"
    empty_line = f"{clr_border}│{clr_reset}{' ' * inner_width}{clr_border}│{clr_reset}"

    title = f"{clr_title}✨ LAPORAN CEK GANTI NOMOR ✨{clr_reset}"
    t_vis = get_visible_width(title)
    l_pad = max(0, (inner_width - t_vis) // 2)
    r_pad = max(0, inner_width - t_vis - l_pad)
    title_line = f"{clr_border}│{clr_reset}{' ' * l_pad}{title}{' ' * r_pad}{clr_border}│{clr_reset}"

    lines = [top, title_line, empty_line]
    lines.append(_make_line(f" 🎯 {clr_cyan}Total Diproses{clr_reset}     : {clr_num}{total_processed}{clr_reset}"))
    lines.append(_make_line(f" ✅ {clr_green}Layak (Password/PIN){clr_reset}: {clr_num}{success_count}{clr_reset}"))
    lines.append(_make_line(f" ⚠️ {clr_yellow}Tidak Layak (OTP){clr_reset}   : {clr_num}{fail_count}{clr_reset}"))

    if error_count > 0:
        lines.append(_make_line(f" ❌ {clr_red}Gagal / Error{clr_reset}      : {clr_num}{error_count}{clr_reset}"))

    lines.append(empty_line)
    lines.append(_make_line(f" {clr_subtitle}★ DAFTAR AKUN LAYAK (TERSAMAR) ★{clr_reset}"))

    unique_success = list(dict.fromkeys(success_accounts))
    if unique_success:
        for acc in unique_success:
            prefix = "       └ "
            prefix_vis = get_visible_width(prefix)
            max_vis = inner_width - prefix_vis
            display_acc = acc
            while get_visible_width(display_acc) > max_vis and len(display_acc) > 0:
                display_acc = display_acc[:-1]
            if len(display_acc) < len(acc):
                display_acc = display_acc[:-3] + "..." if len(display_acc) >= 3 else "..."
            lines.append(_make_line(f"{prefix}{display_acc}"))
    else:
        lines.append(_make_line("       └ (Tidak ada)"))

    lines.append(bot)
    lines.append("")
    lines.append(f"📂 {clr_cyan}Daftar bersih akun layak di '{REEDEM_GANTI_NOMOR_TXT.name}'{clr_reset}")
    if show_csv_path:
        lines.append(f"📂 {clr_cyan}Rincian CSV tersimpan di '{RESULTS_GANTI_NOMOR_FILE.name}'{clr_reset}")
        lines.append(f"📂 {clr_cyan}Riwayat TXT tersimpan di '{RESULTS_GANTI_NOMOR_TXT.name}'{clr_reset}")

    return "\n".join(lines)


def print_change_number_summary_report(
    total_processed: int,
    success_count: int,
    fail_count: int,
    error_count: int = 0,
    success_accounts: Optional[List[str]] = None,
    box_width: Optional[int] = None,
    show_csv_path: bool = False,
):
    """Menampilkan ringkasan akhir pengecekan ganti nomor langsung ke stdout."""
    print("\n" + render_change_number_summary_box(
        total_processed=total_processed,
        success_count=success_count,
        fail_count=fail_count,
        error_count=error_count,
        success_accounts=success_accounts,
        box_width=box_width,
        show_csv_path=show_csv_path,
    ) + "\n")
