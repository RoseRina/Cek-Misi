#!/usr/bin/env python3
"""Modul Klaim Voucher ShopeeFood Otomatis (@shp_tools_bot).

Mendukung otomatisasi klaim voucher ShopeeFood melalui bot Telegram:
1. Mengirim perintah /account
2. Mengklik tombol 'Claim Voucher'
3. Mengirim link voucher yang telah dikonfigurasi
4. Memilih metode identifikasi akun (Email / Username / ID)
5. Mengirim identitas akun dan menangkap balasan bot
6. Menyimpan riwayat incremental ke file output (bot_responses.txt)
7. Menampilkan ringkasan akhir terminal berbingkai rapi
"""

import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
from typing import List, Optional, Tuple, Union

from telethon.errors import FloodWaitError

import shopee_core

# Inisialisasi pewarnaan terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
BOLD = "\033[1m"
RESET = "\033[0m"

DEFAULT_BOT = "@shp_tools_bot"
DEFAULT_VOUCHER_LINK = (
    "https://shopee.co.id/voucher/details?evcode=NEWFOODIES&infocuan&"
    "promotionId=1535384308957184&signature=9d5740e39dedc95c5aeb12ae7ed5455e1163bcbb2f659624052c33b633baf853"
)
DEFAULT_ACCOUNTS_FILE = Path("accounts.txt")
DEFAULT_OUTPUT_FILE = Path("bot_responses.txt")
CONFIG_CLAIM_FILE = Path("voucher_claim_config.json")


def check_telegram_credentials_configured() -> bool:
    """Memeriksa apakah API ID dan API HASH Telegram sudah tersimpan atau dikonfigurasi."""
    api_id, api_hash = shopee_core.load_credentials()
    return bool(api_id and api_hash)


def load_voucher_claim_config() -> str:
    """Mengambil tautan voucher tersimpan dari environment atau file konfigurasi lokal."""
    # 1. Cek environment variable
    env_link = os.environ.get("SHOPEE_VOUCHER_LINK", "").strip()
    if env_link:
        return env_link

    # 2. Cek file konfigurasi JSON lokal
    if CONFIG_CLAIM_FILE.is_file():
        try:
            data = json.loads(CONFIG_CLAIM_FILE.read_text(encoding="utf-8"))
            link = data.get("voucher_link", "").strip()
            if link:
                return link
        except Exception:
            pass

    return DEFAULT_VOUCHER_LINK


def save_voucher_claim_config(voucher_link: str) -> bool:
    """Menyimpan tautan voucher ke file konfigurasi lokal agar tidak perlu diketik berulang."""
    clean_link = (voucher_link or "").strip()
    if not clean_link:
        return False
    try:
        CONFIG_CLAIM_FILE.write_text(
            json.dumps({"voucher_link": clean_link}, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def read_claim_accounts(file_path: Union[str, Path]) -> Tuple[List[str], int]:
    """Membaca daftar identitas akun (email, username, atau ID) dari file teks.

    Mengabaikan baris kosong dan komentar (#), serta menghapus duplikasi
    dengan tetap mempertahankan urutan awal input.
    Mengembalikan (daftar_akun_unik, jumlah_duplikat_dihapus).
    """
    path_obj = Path(file_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"File '{path_obj.name}' tidak ditemukan!")

    raw_lines = path_obj.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    accounts = []
    seen = set()
    duplicates_count = 0

    for line in raw_lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        case_key = cleaned.casefold()
        if case_key in seen:
            duplicates_count += 1
            continue
        seen.add(case_key)
        accounts.append(cleaned)

    return accounts, duplicates_count


def sanitize_log_text(text: str) -> str:
    """Membersihkan informasi sensitif (API HASH, OTP, password, token, nomor telepon) dari teks log."""
    if not text:
        return ""
    # Mask 32-karakter hex (seperti API HASH atau token session)
    cleaned = re.sub(r"\b[0-9a-fA-F]{32}\b", "[REDACTED_HASH]", text)
    # Mask nomor telepon internasional
    cleaned = re.sub(r"(?:\+?62|08)\d{8,13}", "[REDACTED_PHONE]", cleaned)
    # Mask OTP / kode numerik 5-6 digit terisolasi
    cleaned = re.sub(r"\b(?<!\w)\d{5,6}(?!\w)\b", "[REDACTED_CODE]", cleaned)
    return cleaned


def is_intermediate_response(text: str) -> bool:
    """Mengecek apakah teks respons bot merupakan pesan perantara / placeholder
    yang masih dalam antrean / pemrosesan dan bukan hasil akhir klaim."""
    raw_str = (text or "").strip()
    if not raw_str:
        return False
    clean = " ".join(raw_str.casefold().split())
    if not clean:
        return False

    # KECUALI jika mengandung kata hasil akhir:
    final_indicators = (
        "berhasil",
        "gagal",
        "maaf",
        "tidak memenuhi",
        "sudah diklaim",
        "telah diklaim",
        "kuota",
        "expired",
        "kadaluwarsa",
        "kedaluwarsa",
        "tidak ditemukan",
        "tidak valid",
        "failed",
    )
    if any(k in clean for k in final_indicators):
        return False

    # 1. Mengandung ⏳ atau ⌛
    if "⏳" in raw_str or "⌛" in raw_str:
        return True

    # 2. Mengandung kata 'klaim' dan berakhir dengan '...' atau '…'
    if "klaim" in clean and (clean.endswith("...") or clean.endswith("…")):
        return True

    # 3. Mengandung kata proses/tunggu/antre
    intermediate_indicators = (
        "memproses",
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
    )
    if any(k in clean for k in intermediate_indicators):
        return True

    return False


def classify_claim_response(text: str) -> Tuple[str, str]:
    """Mengklasifikasikan respons bot ke salah satu dari 3 kategori mutlak:
    1. 'BERHASIL'        : Klaim sukses diverifikasi
    2. 'GAGAL'           : Klaim ditolak / kuota habis / syarat tidak terpenuhi / sudah diklaim
    3. 'TIDAK DIKETAHUI' : Respons tidak dikenal, pesan perantara, atau terjadi anomali
    """
    raw_str = (text or "").strip()
    clean = " ".join(raw_str.casefold().split())
    if not clean:
        return "TIDAK DIKETAHUI", "Bot tidak memberikan teks balasan"

    # 1. Deteksi pesan perantara / loading (tidak boleh dianggap sukses/gagal final)
    if is_intermediate_response(raw_str):
        return "TIDAK DIKETAHUI", "Respons perantara bot (masih dalam proses, bukan hasil akhir)"

    has_negative_indicators = any(k in clean for k in ("tidak", "belum", "gagal", "bukan", "maaf", "❌", "failed"))

    # 2. Kriteria Berhasil (HANYA jika tidak ada indikator negatif)
    if not has_negative_indicators:
        success_keywords = (
            "berhasil diklaim",
            "claim voucher berhasil",
            "voucher berhasil",
            "berhasil klaim",
            "berhasil ditambahkan",
            "voucher telah masuk",
            "voucher masuk",
            "klaim sukses",
            "sukses klaim",
            "claimed successfully",
            "selamat! voucher",
        )
        if any(k in clean for k in success_keywords):
            return "BERHASIL", "Voucher berhasil diklaim ke akun"

        if "berhasil" in clean:
            return "BERHASIL", "Voucher berhasil diklaim"

    # 3. Kriteria Gagal (Penolakan Kelayakan / Kriteria / Syarat)
    if (
        "belum memenuhi kriteria" in clean
        or "tidak memenuhi kriteria" in clean
        or "belum memenuhi syarat" in clean
        or "tidak memenuhi syarat" in clean
        or "belum memenuhi" in clean
        or "tidak memenuhi" in clean
        or "tidak berhak" in clean
        or "ineligible" in clean
        or "not eligible" in clean
        or ("kriteria" in clean and any(w in clean for w in ("belum", "tidak", "kurang", "bukan")))
        or ("syarat" in clean and any(w in clean for w in ("belum", "tidak", "kurang", "bukan")))
    ):
        return "GAGAL", "TIDAK MEMENUHI KRITERIA: Belum/tidak memenuhi kriteria atau syarat klaim"

    # Kriteria Gagal Lainnya
    if any(k in clean for k in ("sudah pernah", "sudah diklaim", "already claimed", "telah diklaim", "pernah diklaim")):
        return "GAGAL", "Voucher sudah pernah diklaim sebelumnya"

    if "kuota" in clean and any(w in clean for w in ("habis", "penuh", "limit", "kosong", "mencapai batas")):
        return "GAGAL", "Kuota klaim voucher habis"

    if any(k in clean for k in ("expired", "kadaluwarsa", "kedaluwarsa", "telah berakhir")):
        return "GAGAL", "Voucher sudah kedaluwarsa"

    if any(k in clean for k in ("limit", "dibatasi", "banned", "terbatas")):
        return "GAGAL", "Akun atau kuota terkena limit"

    if any(k in clean for k in ("tidak ditemukan", "not found", "user tidak valid", "akun tidak valid", "tidak terdaftar")):
        return "GAGAL", "Identitas akun tidak ditemukan atau tidak valid"

    if "maaf" in clean and any(w in clean for w in ("tidak", "belum", "gagal", "batal")):
        return "GAGAL", "Klaim voucher ditolak bot"

    if "gagal" in clean or "failed" in clean:
        return "GAGAL", "Gagal mengklaim voucher (ditolak bot)"

    snippet = sanitize_log_text(raw_str.replace("\n", " "))
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."
    return "TIDAK DIKETAHUI", f"Respons bot tidak dikenal: {snippet}"


def save_claim_result(
    account: str,
    status: str,
    detail: str,
    raw_response: str,
    output_file: Union[str, Path] = DEFAULT_OUTPUT_FILE,
):
    """Menyimpan hasil klaim voucher secara bertahap (incremental append) ke file output
    dengan menyaring informasi sensitif."""
    out_path = Path(output_file)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sanitized_resp = sanitize_log_text(raw_response or "")
    clean_resp = " ".join(sanitized_resp.split())
    if len(clean_resp) > 200:
        clean_resp = clean_resp[:197] + "..."

    sanitized_acc = sanitize_log_text(account or "-")
    line = f"[{now_str}] [{sanitized_acc}] [{status}] {detail} | Respons: {clean_resp or '-'}\n"
    try:
        with out_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def render_claim_summary_box(
    total_accounts: int,
    completed_count: int,
    success_count: int,
    fail_count: int,
    unknown_count: int,
    box_width: Optional[int] = None,
    output_file_name: Optional[str] = "bot_responses.txt",
) -> str:
    """Membuat laporan ringkasan terminal berbingkai rapi yang konsisten dengan estetika Cek-Misi."""
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

    inner_width = max(38, box_width - 2)

    clr_border = '\033[92m'      # Hijau
    clr_title = '\033[1;93m'     # Kuning tebal
    clr_cyan = '\033[96m'        # Biru muda / cyan
    clr_green = '\033[92m'       # Hijau
    clr_yellow = '\033[93m'      # Kuning
    clr_red = '\033[91m'         # Merah
    clr_num = '\033[1;96m'       # Angka cyan tebal
    clr_reset = '\033[0m'

    def _make_line(content: str) -> str:
        vis = shopee_core.get_visible_width(content)
        pad = max(0, inner_width - vis)
        return f"{clr_border}│{clr_reset}{content}{' ' * pad}{clr_border}│{clr_reset}"

    top = f"{clr_border}╭{'─' * inner_width}╮{clr_reset}"
    sep = f"{clr_border}├{'─' * inner_width}┤{clr_reset}"
    bot = f"{clr_border}╰{'─' * inner_width}╯{clr_reset}"

    title = f"{clr_title}🎟️ KLAIM VOUCHER SHOPEEFOOD 🎟️{clr_reset}"
    t_vis = shopee_core.get_visible_width(title)
    l_pad = max(0, (inner_width - t_vis) // 2)
    r_pad = max(0, inner_width - t_vis - l_pad)
    title_line = f"{clr_border}│{clr_reset}{' ' * l_pad}{title}{' ' * r_pad}{clr_border}│{clr_reset}"

    lines = [
        top,
        title_line,
        sep,
        _make_line(f" 🎯 {clr_cyan}Total akun{clr_reset}       : {clr_num}{total_accounts}{clr_reset}"),
        _make_line(f" 🏁 {clr_cyan}Selesai{clr_reset}          : {clr_num}{completed_count}{clr_reset}"),
        _make_line(f" ✅ {clr_green}Berhasil{clr_reset}         : {clr_num}{success_count}{clr_reset}"),
        _make_line(f" ❌ {clr_red}Gagal{clr_reset}            : {clr_num}{fail_count}{clr_reset}"),
        _make_line(f" ❓ {clr_yellow}Tidak diketahui{clr_reset}  : {clr_num}{unknown_count}{clr_reset}"),
        bot,
    ]
    if output_file_name:
        lines.append("")
        lines.append(f"📂 {clr_cyan}Rincian respons tersimpan di '{output_file_name}'{clr_reset}")

    return "\n".join(lines)


async def click_button(btn, msg, row_idx: int = 0, col_idx: int = 0):
    """Mengklik tombol inline Telegram bot secara aman."""
    if hasattr(btn, "click") and callable(btn.click):
        await btn.click()
    elif hasattr(msg, "click") and callable(msg.click):
        await msg.click(row_idx, col_idx)
    else:
        raise RuntimeError("Objek tombol tidak mendukung interaksi klik")


async def wait_for_bot_message_with_buttons(
    client,
    target_bot: str,
    after_id: int,
    match_fn,
    timeout: float = 15.0,
    poll_interval: float = 1.0,
):
    """Menunggu pesan bot setelah after_id yang memiliki tombol inline yang cocok."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(target_bot, limit=10)
        # Saring pesan bot setelah ID pemicu
        candidates = sorted(
            (m for m in messages if m.id > after_id and not getattr(m, "out", False) and getattr(m, "buttons", None)),
            key=lambda m: m.id,
        )
        for msg in candidates:
            for r_idx, row in enumerate(msg.buttons):
                for c_idx, btn in enumerate(row):
                    btn_text = getattr(btn, "text", "") or ""
                    if match_fn(btn_text):
                        return msg, btn, r_idx, c_idx
        await asyncio.sleep(poll_interval)
    return None, None, -1, -1


async def wait_for_bot_final_response(
    client,
    target_bot: str,
    after_id: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> str:
    """Menunggu pesan respons akhir dari bot setelah pengiriman identitas akun."""
    deadline = asyncio.get_running_loop().time() + timeout
    latest_text = ""
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(target_bot, limit=5)
        candidates = sorted(
            (m for m in messages if m.id > after_id and not getattr(m, "out", False)),
            key=lambda m: m.id,
        )
        for msg in candidates:
            text = (getattr(msg, "text", "") or "").strip()
            if text:
                latest_text = text
                if not is_intermediate_response(text):
                    return text
        await asyncio.sleep(poll_interval)
    return latest_text


async def claim_voucher_for_account(
    client,
    account_identity: str,
    voucher_link: str,
    target_bot: str = DEFAULT_BOT,
    timeout: float = 30.0,
) -> Tuple[str, str, str]:
    """Menjalankan alur klaim voucher untuk 1 akun ke @shp_tools_bot:
    1. Kirim /account
    2. Deteksi & klik tombol 'Claim Voucher'
    3. Kirim link voucher
    4. Deteksi & klik tombol metode identifikasi akun (Email / Username / ID)
    5. Kirim identitas akun
    6. Tangkap respons akhir bot dan klasifikasikan
    Mengembalikan: (status, detail, raw_response)
    """
    clean_id = (account_identity or "").strip()
    if not clean_id:
        return "TIDAK DIKETAHUI", "Identitas akun kosong", ""

    # 1. Kirim perintah /account
    try:
        sent_cmd = await client.send_message(target_bot, "/account")
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengirim /account: {exc}", ""

    # 2. Deteksi tombol Claim Voucher
    def match_claim(text: str) -> bool:
        t = text.casefold()
        return "claim" in t and "voucher" in t

    msg_claim, btn_claim, r_c, c_c = await wait_for_bot_message_with_buttons(
        client, target_bot, sent_cmd.id, match_claim, timeout=timeout
    )
    if not msg_claim or not btn_claim:
        return "TIDAK DIKETAHUI", "Tombol 'Claim Voucher' tidak ditemukan pada balasan bot", ""

    # Klik tombol Claim Voucher
    try:
        await click_button(btn_claim, msg_claim, r_c, c_c)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengklik tombol 'Claim Voucher': {exc}", ""

    await asyncio.sleep(1.5)

    # 3. Kirim link voucher
    try:
        sent_link = await client.send_message(target_bot, voucher_link)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengirim tautan voucher: {exc}", ""

    # 4. Deteksi tombol metode identifikasi
    is_email = "@" in clean_id
    is_numeric = clean_id.isdigit()

    def match_method(text: str) -> bool:
        t = text.casefold()
        if is_email and "email" in t:
            return True
        if is_numeric and ("id" in t or "user" in t):
            return True
        if not is_email and not is_numeric and ("username" in t or "user" in t or "akun" in t):
            return True
        return any(k in t for k in ("email", "username", "id", "akun"))

    msg_method, btn_method, r_m, c_m = await wait_for_bot_message_with_buttons(
        client, target_bot, sent_link.id, match_method, timeout=timeout
    )
    if not msg_method or not btn_method:
        return "TIDAK DIKETAHUI", "Tombol metode identifikasi tidak ditemukan pada balasan bot", ""

    try:
        await click_button(btn_method, msg_method, r_m, c_m)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengklik tombol metode identifikasi: {exc}", ""

    await asyncio.sleep(1.5)

    # 5. Kirim identitas akun
    try:
        sent_id_msg = await client.send_message(target_bot, clean_id)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengirim identitas akun: {exc}", ""

    # 6. Tangkap respons akhir dari bot
    final_text = await wait_for_bot_final_response(
        client, target_bot, sent_id_msg.id, timeout=timeout
    )
    if not final_text:
        return "TIDAK DIKETAHUI", "Timeout menunggu balasan akhir dari bot", ""

    status, detail = classify_claim_response(final_text)
    return status, detail, final_text


async def run_voucher_claim_mode(
    client=None,
    accounts: Optional[List[str]] = None,
    accounts_file: Optional[Union[str, Path]] = None,
    voucher_link: Optional[str] = None,
    step_delay: float = 4.0,
    output_file: Union[str, Path] = DEFAULT_OUTPUT_FILE,
    target_bot: str = DEFAULT_BOT,
    timeout: float = 30.0,
) -> dict:
    """Menjalankan antrean proses klaim voucher ShopeeFood secara berurutan."""
    out_file = Path(output_file)

    # 1. Validasi Tautan Voucher
    active_voucher_link = (voucher_link or load_voucher_claim_config()).strip()
    if not active_voucher_link:
        active_voucher_link = DEFAULT_VOUCHER_LINK

    # 2. Ambil Daftar Akun
    if accounts is None:
        file_to_read = accounts_file or DEFAULT_ACCOUNTS_FILE
        try:
            accounts, dupes = read_claim_accounts(file_to_read)
            if dupes > 0:
                print(f"{YELLOW}ℹ️ Membersihkan {dupes} entri duplikat dari daftar akun.{RESET}")
        except FileNotFoundError as err:
            print(f"{RED}❌ {err}{RESET}")
            return {"total": 0, "completed": 0, "success": 0, "fail": 0, "unknown": 0, "results": []}

    total = len(accounts)
    if total == 0:
        print(f"{RED}❌ Tidak ada akun untuk diproses (daftar kosong).{RESET}")
        return {"total": 0, "completed": 0, "success": 0, "fail": 0, "unknown": 0, "results": []}

    print(f"\n{CYAN}{BOLD}===================================================={RESET}")
    print(f"🎟️ {BOLD}MEMULAI PROSES KLAIM VOUCHER SHOPEEFOOD{RESET}")
    print(f"{CYAN}===================================================={RESET}")
    print(f"🎯 Target Bot   : {BOLD}{target_bot}{RESET}")
    print(f"🔗 Tautan       : {active_voucher_link[:65]}...")
    print(f"📋 Total Akun   : {BOLD}{total} akun/identitas{RESET}")
    print(f"📂 File Output  : {out_file.name}")
    print(f"{CYAN}----------------------------------------------------{RESET}\n")

    # Inisialisasi client jika belum diberikan
    own_client = False
    if client is None:
        client = shopee_core.create_client()
        await shopee_core.start_client(client)
        own_client = True

    completed_count = 0
    success_count = 0
    fail_count = 0
    unknown_count = 0
    results = []

    try:
        for idx, acc in enumerate(accounts, 1):
            bar = shopee_core.render_progress_bar(idx, total)
            print(f"{CYAN}{bar}{RESET} {BOLD}{acc}{RESET}")

            try:
                status, detail, raw_resp = await claim_voucher_for_account(
                    client=client,
                    account_identity=acc,
                    voucher_link=active_voucher_link,
                    target_bot=target_bot,
                    timeout=timeout,
                )
                save_claim_result(acc, status, detail, raw_resp, output_file=out_file)
                completed_count += 1

                if status == "BERHASIL":
                    print(f"  └─ {GREEN}{BOLD}✅ {status}: {detail}{RESET}\n")
                    success_count += 1
                elif status == "GAGAL":
                    print(f"  └─ {RED}❌ {status}: {detail}{RESET}\n")
                    fail_count += 1
                else:
                    print(f"  └─ {YELLOW}❓ {status}: {detail}{RESET}\n")
                    unknown_count += 1

                results.append({"account": acc, "status": status, "detail": detail, "response": raw_resp})

            except FloodWaitError as exc:
                msg = f"Telegram FloodWait {exc.seconds}s. Antrean dihentikan."
                save_claim_result(acc, "TIDAK DIKETAHUI", msg, str(exc), output_file=out_file)
                completed_count += 1
                unknown_count += 1
                results.append({"account": acc, "status": "TIDAK DIKETAHUI", "detail": msg, "response": str(exc)})
                print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s! Antrean dihentikan demi keamanan.{RESET}\n")
                break
            except Exception as exc:
                err_msg = f"Error: {exc}"
                save_claim_result(acc, "TIDAK DIKETAHUI", err_msg, str(exc), output_file=out_file)
                completed_count += 1
                unknown_count += 1
                results.append({"account": acc, "status": "TIDAK DIKETAHUI", "detail": err_msg, "response": str(exc)})
                print(f"  └─ {RED}❌ Error: {exc}{RESET}\n")

            if idx < total:
                await asyncio.sleep(step_delay)

    finally:
        if own_client:
            try:
                await client.disconnect()
            except Exception:
                pass

    # Tampilkan Rekapitulasi Akhir Berbingkai
    report_box = render_claim_summary_box(
        total_accounts=total,
        completed_count=completed_count,
        success_count=success_count,
        fail_count=fail_count,
        unknown_count=unknown_count,
        output_file_name=out_file.name,
    )
    print("\n" + report_box + "\n")

    return {
        "total": total,
        "completed": completed_count,
        "success": success_count,
        "fail": fail_count,
        "unknown": unknown_count,
        "results": results,
    }


async def interactive_voucher_claim_menu():
    """Menu interaktif khusus klaim voucher yang dipanggil dari menu utama."""
    print(f"\n{CYAN}{BOLD}===================================================={RESET}")
    print(f"🎟️ {BOLD}MENU KLAIM VOUCHER SHOPEEFOOD (@shp_tools_bot){RESET}")
    print(f"{CYAN}===================================================={RESET}")

    # 1. Konfigurasi Tautan Voucher
    current_link = load_voucher_claim_config()
    print(f"\n🔗 {BOLD}Tautan Voucher Saat Ini:{RESET}")
    print(f"   {CYAN}{current_link}{RESET}")
    ubah = input(f"{WHITE}Ingin mengganti tautan voucher? (y/N): {RESET}").strip().casefold()
    if ubah in ("y", "ya", "yes"):
        new_link = input("Masukkan tautan voucher baru: ").strip()
        if new_link:
            save_voucher_claim_config(new_link)
            current_link = new_link
            print(f"{GREEN}✅ Tautan voucher berhasil diperbarui!{RESET}")

    # 2. Pemilihan File Sumber Akun
    print(f"\n📁 {BOLD}Pilih File Sumber Akun/Identitas:{RESET}")
    file_options = []
    if DEFAULT_ACCOUNTS_FILE.is_file():
        file_options.append(DEFAULT_ACCOUNTS_FILE)
    for p, _ in shopee_core.get_available_txt_files():
        if p not in file_options and p.name not in ("requirements.txt", "valid_food.txt"):
            file_options.append(p)

    selected_file = None
    if file_options:
        for idx, fpath in enumerate(file_options, 1):
            print(f"  [{idx}] 📄 {fpath.name}")
        print(f"  [{len(file_options) + 1}] ✍️  Ketik nama/path file lain")
        choice = input(f"{WHITE}Pilih file [1-{len(file_options) + 1}] (Default 1): {RESET}").strip()
        try:
            choice_idx = int(choice) if choice else 1
            if 1 <= choice_idx <= len(file_options):
                selected_file = file_options[choice_idx - 1]
        except ValueError:
            pass

    if not selected_file:
        custom_file = input("Masukkan nama/path file akun: ").strip()
        selected_file = Path(custom_file) if custom_file else DEFAULT_ACCOUNTS_FILE

    # 3. Jalankan Klaim
    await run_voucher_claim_mode(
        accounts_file=selected_file,
        voucher_link=current_link,
        step_delay=4.0,
    )


if __name__ == "__main__":
    try:
        asyncio.run(interactive_voucher_claim_menu())
    except (KeyboardInterrupt, EOFError):
        print("\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\n❌ Terjadi kesalahan: {exc}")
