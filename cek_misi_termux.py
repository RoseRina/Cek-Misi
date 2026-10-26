#!/usr/bin/env python3
"""Shopee Tools All-in-One: Cek Misi QRIS & Cek Voucher Shopee Food.

Mendukung Mode Satuan (Single) dan Mode Massal (Bulk) untuk Android Termux & PC.

Contoh Penggunaan:
    # 1. Jalankan Menu Interaktif:
    python cek_misi_termux.py

    # 2. Mode Bulk Cepat dengan File:
    python cek_misi_termux.py daftar_username.txt --mode misi
    python cek_misi_termux.py food.txt --mode food
    python cek_misi_termux.py akun.txt --mode both --resume --delay 3

    # 3. Mode Satuan Cepat (1 Akun):
    python cek_misi_termux.py --single shopee_user_123 --mode misi
"""

import argparse
import asyncio
from pathlib import Path
import sys

from telethon.errors import FloodWaitError

import shopee_core
import voucher_claim

# Inisialisasi pewarnaan terminal (fallback aman jika colorama/rich tidak terpasang)
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


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
     🚀 SHOPEE BOT ALL-IN-ONE (TERMUX & PC AUTOMATION)
======================================================================{RESET}
 {WHITE}1.{RESET} 🎯 {BOLD}Cek Misi Bayar QRIS{RESET}      (Check-in Koin QRIS Shopee)
 {WHITE}2.{RESET} 🍔 {BOLD}Cek Voucher Shopee Food{RESET}  (Diskon 25RB & Ongkir 12RB)
 {WHITE}3.{RESET} ⚡ {BOLD}Cek Keduanya Sekaligus{RESET}   (Misi QRIS + Voucher Food)
 {WHITE}4.{RESET} 📦 {BOLD}MODE MASSAL / BULK CEPAT{RESET} (Auto-Detect File .txt & Resume)
 {WHITE}5.{RESET} 👥 {BOLD}Kelola Multi-Worker{RESET}     (Multi-Login Akun Telegram)
 {WHITE}6.{RESET} ⚙️  {BOLD}Reset Pengaturan{RESET}        (Hapus Sesi & API Telegram)
 {WHITE}7.{RESET} 🎟️ {BOLD}Klaim Voucher ShopeeFood{RESET} (Auto-Claim Voucher ke Bot)
 {WHITE}8.{RESET} 🔑 {BOLD}Cek Ganti Nomor{RESET}          (Checker, Tanpa Mengubah Nomor)
 {WHITE}0.{RESET} 🚪 {BOLD}Keluar{RESET}
{CYAN}======================================================================{RESET}
"""
    print(banner)


# Hubungkan helper alur pengisian akun dari shopee_core
pilih_metode_auth = shopee_core.pilih_metode_auth
input_manual_account = shopee_core.input_manual_account
print_bulk_format_guidance = shopee_core.print_bulk_format_guidance
pilih_daftar_akun_bulk = shopee_core.pilih_daftar_akun_bulk


async def run_misi_mode(client, usernames, auth_method="username", step_delay=2.5, reused_records=None, recheck_targets=None, debug=False):
    total = len(usernames)
    recheck_set = set(recheck_targets or [])
    preserved_records = []
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Misi Bayar QRIS ({total} akun/cookie, Metode: {auth_method.upper()})...{RESET}\n")
    success_count = 0
    fail_count = 0
    error_count = 0

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        display = shopee_core.format_account_display(user, auth_method)
        print(f"{CYAN}{bar}{RESET} {BOLD}{display}{RESET}")
        is_recheck = user in recheck_set
        try:
            coins, status, detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method, debug=debug)
            is_err = any(err in (status or "").upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))

            if is_recheck and is_err:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": status,
                    "detail": detail,
                    "reason": f"Cek ulang menghasilkan {status}, hasil sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang {status} ({detail}) -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_mission_result(user, coins, status, detail)

                if status in ("SELESAI", "SUDAH DICLAIM", "BELUM SELESAI"):
                    color = GREEN if status == "SELESAI" else YELLOW
                    c_str = f"{coins:,} koin" if coins is not None else "-"
                    print(f"  └─ {color}{BOLD}Bayar QRIS: {c_str} | {status}{RESET}\n")
                    success_count += 1
                elif status == "TIDAK ADA MISI QRIS":
                    print(f"  └─ {YELLOW}⚠️ {status}: {detail}{RESET}\n")
                    fail_count += 1
                else:
                    print(f"  └─ {RED}❌ {status}: {detail}{RESET}\n")
                    fail_count += 1
        except FloodWaitError as exc:
            msg = f"Telegram meminta jeda {exc.seconds} detik. Antrean dihentikan."
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "FLOOD_WAIT",
                    "detail": msg,
                    "reason": "Cek ulang terkena FloodWait, hasil sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang FloodWait -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_mission_result(user, None, "FLOOD_WAIT", msg)
                error_count += 1
                print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "ERROR",
                    "detail": str(exc),
                    "reason": "Cek ulang error, hasil sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang Error -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_mission_result(user, None, "ERROR", str(exc))
                print(f"  └─ {RED}Error: {exc}{RESET}\n")
                fail_count += 1
                error_count += 1

        if idx < total:
            await asyncio.sleep(step_delay)

    print(f"{CYAN}{BOLD}==================== LAPORAN SELESAI ===================={RESET}")
    print(f"🎯 Total Akun       : {total}")
    print(f"{GREEN}✅ Berhasil Dicek   : {success_count}{RESET}")
    print(f"{RED}❌ Gagal / Tidak Ada: {fail_count}{RESET}")
    print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_MISI_FILE.name} (CSV) & {shopee_core.RESULTS_MISI_TXT.name} (TXT)\n")

    if reused_records or preserved_records:
        shopee_core.print_combined_execution_summary(
            mode="misi",
            total_all=total + (len(reused_records) if reused_records else 0),
            total_processed=total,
            new_success=success_count,
            new_fail=fail_count,
            new_error=error_count,
            reused_records=reused_records or [],
            preserved_records=preserved_records,
            auth_method=auth_method,
        )


async def run_food_mode(client, usernames, auth_method="username", step_delay=2.5, reused_records=None, recheck_targets=None):
    total = len(usernames)
    recheck_set = set(recheck_targets or [])
    preserved_records = []
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Voucher Shopee Food ({total} akun/cookie, Metode: {auth_method.upper()})...{RESET}\n")
    processed_count = 0
    valid_count = 0
    invalid_count = 0
    partial_count = 0
    error_count = 0
    valid_list = []

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        display = shopee_core.format_account_display(user, auth_method)
        print(f"{CYAN}{bar}{RESET} {BOLD}{display}{RESET}")
        is_recheck = user in recheck_set
        try:
            is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)
            processed_count += 1
            is_err = any(err in (status or "").upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))

            if is_recheck and is_err:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": status,
                    "detail": detail,
                    "reason": f"Cek ulang menghasilkan {status}, hasil valid/sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang {status} ({detail}) -> Hasil valid lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_food_result(user, is_valid, status, detail, has_25k, has_12k)
                category = shopee_core.classify_food_status(is_valid, status)
                if category == "VALID":
                    print(f"  └─ {GREEN}{BOLD}✅ {status} ({detail}){RESET}\n")
                    valid_count += 1
                    valid_list.append(user)
                elif category == "PARSIAL":
                    print(f"  └─ {YELLOW}⚠️ {status} ({detail}){RESET}\n")
                    partial_count += 1
                elif category == "ERROR":
                    print(f"  └─ {RED}❌ {status} ({detail}){RESET}\n")
                    error_count += 1
                else:  # INVALID
                    print(f"  └─ {YELLOW}⚠️ {status} ({detail}){RESET}\n")
                    invalid_count += 1
        except FloodWaitError as exc:
            msg = f"Telegram meminta jeda {exc.seconds} detik. Antrean dihentikan."
            processed_count += 1
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "FLOOD_WAIT",
                    "detail": msg,
                    "reason": "Cek ulang terkena FloodWait, hasil valid lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang FloodWait -> Hasil valid lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_food_result(user, False, "FLOOD_WAIT", msg, False, False)
                error_count += 1
                print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            processed_count += 1
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "ERROR",
                    "detail": str(exc),
                    "reason": "Cek ulang error, hasil valid lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang Error -> Hasil valid lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_food_result(user, False, "ERROR", str(exc), False, False)
                print(f"  └─ {RED}Error: {exc}{RESET}\n")
                error_count += 1

        if idx < total:
            await asyncio.sleep(step_delay)

    shopee_core.print_food_summary_report(
        total_processed=processed_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        valid_accounts=valid_list,
        partial_count=partial_count,
        error_count=error_count,
        show_csv_path=True,
    )

    if reused_records or preserved_records:
        shopee_core.print_combined_execution_summary(
            mode="food",
            total_all=total + (len(reused_records) if reused_records else 0),
            total_processed=processed_count,
            new_success=valid_count,
            new_fail=invalid_count + partial_count,
            new_error=error_count,
            reused_records=reused_records or [],
            preserved_records=preserved_records,
            auth_method=auth_method,
        )


async def run_both_mode(client, usernames, auth_method="username", step_delay=2.5, reused_records=None, recheck_targets=None):
    total = len(usernames)
    recheck_set = set(recheck_targets or [])
    preserved_records = []
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Keduanya (Misi QRIS + Voucher Food) ({total} akun/cookie, Metode: {auth_method.upper()})...{RESET}\n")
    processed_count = 0
    success_count = 0
    fail_count = 0
    error_count = 0

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        display = shopee_core.format_account_display(user, auth_method)
        print(f"{CYAN}{bar}{RESET} {BOLD}{display}{RESET}")
        is_recheck = user in recheck_set
        processed_count += 1
        try:
            # 1. Cek Misi QRIS
            print(f"  [1/2] Memeriksa Misi QRIS...")
            coins, m_status, m_detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method)
            await asyncio.sleep(step_delay)

            # 2. Cek Voucher Food
            print(f"  [2/2] Memeriksa Voucher Shopee Food...")
            is_valid, f_status, f_detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)

            is_err = any(err in f"{m_status} {f_status}".upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))
            if is_recheck and is_err:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": f"{m_status} | {f_status}",
                    "detail": f"{m_detail} | {f_detail}",
                    "reason": "Cek ulang timeout/error, hasil sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang timeout/error -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_mission_result(user, coins, m_status, m_detail)
                shopee_core.save_food_result(user, is_valid, f_status, f_detail, has_25k, has_12k)
                shopee_core.save_combined_result(user, coins, m_status, f_status, f_detail)

                f_cat = shopee_core.classify_food_status(is_valid, f_status)
                if f_cat == "VALID" or m_status in ("SELESAI", "SUDAH DICLAIM"):
                    success_count += 1
                    color = GREEN
                else:
                    fail_count += 1
                    color = YELLOW
                c_str = f"{coins:,} koin" if coins is not None else "-"
                print(f"        └─ {color}Misi: {m_status} ({c_str}) | Food: {f_status} ({f_detail}){RESET}\n")

        except FloodWaitError as exc:
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "FLOOD_WAIT",
                    "detail": f"FloodWait {exc.seconds}s",
                    "reason": "Cek ulang terkena FloodWait, hasil sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang FloodWait -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
            else:
                error_count += 1
                print(f"  └─ {RED}⚠️ Telegram FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "ERROR",
                    "detail": str(exc),
                    "reason": "Cek ulang error, hasil sukses lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang Error -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
            else:
                fail_count += 1
                error_count += 1
                print(f"  └─ {RED}Error: {exc}{RESET}\n")

        if idx < total:
            await asyncio.sleep(step_delay)

    print(f"{CYAN}{BOLD}==================== PENGECEKAN GABUNGAN SELESAI ===================={RESET}")
    print(f"📂 Hasil lengkap tersimpan di: {shopee_core.RESULTS_ALL_FILE.name} (CSV) & {shopee_core.RESULTS_ALL_TXT.name} (TXT)\n")

    if reused_records or preserved_records:
        shopee_core.print_combined_execution_summary(
            mode="both",
            total_all=total + (len(reused_records) if reused_records else 0),
            total_processed=processed_count,
            new_success=success_count,
            new_fail=fail_count,
            new_error=error_count,
            reused_records=reused_records or [],
            preserved_records=preserved_records,
            auth_method=auth_method,
        )


async def run_change_number_mode(client, usernames, auth_method="username", step_delay=2.5, reused_records=None, recheck_targets=None):
    """Menjalankan antrean pengecekan status kelayakan ganti nomor (Checker Only).
    
    PRINSIP KEAMANAN:
    - Hanya bertindak sebagai checker (bukan untuk benar-benar mengganti nomor).
    - Selalu membatalkan (klik tombol Batal) setelah status verifikasi terdeteksi.
    - Tidak pernah mengirimkan OTP, password, atau PIN ke bot Telegram.
    - Masking format_account_display aktif untuk semua tampilan terminal dan file hasil.
    """
    total = len(usernames)
    recheck_set = set(recheck_targets or [])
    preserved_records = []
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Ganti Nomor (Checker Only) ({total} akun/cookie, Metode: {auth_method.upper()})...{RESET}")
    print(f"  {DIM}ℹ️  Mode aman: Hanya mengecek syarat verifikasi, selalu dibatalkan & nomor TIDAK diubah.{RESET}\n")
    processed_count = 0
    success_count = 0
    fail_count = 0
    error_count = 0
    success_list = []

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        display = shopee_core.format_account_display(user, auth_method)
        print(f"{CYAN}{bar}{RESET} {BOLD}{display}{RESET}")
        is_recheck = user in recheck_set
        try:
            is_eligible, status, detail = await shopee_core.check_one_change_number(client, user, auth_method=auth_method)
            processed_count += 1
            is_err = any(err in (status or "").upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))

            if is_recheck and is_err:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": status,
                    "detail": detail,
                    "reason": f"Cek ulang menghasilkan {status}, hasil layak lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang {status} ({detail}) -> Hasil layak lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_ganti_nomor_result(user, status, detail, auth_method=auth_method)
                if status == "SUKSES":
                    print(f"  └─ {GREEN}{BOLD}✅ {status} ({detail}){RESET}\n")
                    success_count += 1
                    success_list.append(display)
                elif status == "GAGAL":
                    print(f"  └─ {YELLOW}⚠️ {status} ({detail}){RESET}\n")
                    fail_count += 1
                else:
                    print(f"  └─ {RED}❌ {status} ({detail}){RESET}\n")
                    error_count += 1
        except FloodWaitError as exc:
            msg = f"Telegram meminta jeda {exc.seconds} detik. Antrean dihentikan."
            processed_count += 1
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "FLOOD_WAIT",
                    "detail": msg,
                    "reason": "Cek ulang terkena FloodWait, hasil layak lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang FloodWait -> Hasil layak lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_ganti_nomor_result(user, "FLOOD_WAIT", msg, auth_method=auth_method)
                error_count += 1
                print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            processed_count += 1
            if is_recheck:
                preserved_records.append({
                    "account": user,
                    "display": display,
                    "status": "ERROR",
                    "detail": str(exc),
                    "reason": "Cek ulang error, hasil layak lama dipertahankan",
                })
                print(f"  └─ {YELLOW}🛡️ Cek ulang Error -> Hasil layak lama DIPERTAHANKAN.{RESET}\n")
            else:
                shopee_core.save_ganti_nomor_result(user, "ERROR", str(exc), auth_method=auth_method)
                print(f"  └─ {RED}Error: {exc}{RESET}\n")
                error_count += 1

        if idx < total:
            await asyncio.sleep(step_delay)

    shopee_core.print_change_number_summary_report(
        total_processed=processed_count,
        success_count=success_count,
        fail_count=fail_count,
        error_count=error_count,
        success_accounts=success_list,
        show_csv_path=True,
    )

    if reused_records or preserved_records:
        shopee_core.print_combined_execution_summary(
            mode="ganti_nomor",
            total_all=total + (len(reused_records) if reused_records else 0),
            total_processed=processed_count,
            new_success=success_count,
            new_fail=fail_count,
            new_error=error_count,
            reused_records=reused_records or [],
            preserved_records=preserved_records,
            auth_method=auth_method,
        )


async def run_worker_pool_mode(clients, usernames, mode="misi", auth_method="auto", step_delay=2.5, reused_records=None, recheck_targets=None):
    """Menjalankan pengecekan secara paralel menggunakan multiple worker Telegram."""
    total = len(usernames)
    num_workers = len(clients)
    recheck_set = set(recheck_targets or [])
    preserved_records = []
    print(f"\n{YELLOW}{BOLD}🚀 Memulai Multi-Worker Parallel Engine ({num_workers} Worker Telegram, {total} Akun)...{RESET}\n")

    # Ambil info identitas setiap worker
    worker_infos = []
    for idx, c in enumerate(clients, 1):
        try:
            me = await c.get_me()
            lbl = f"Worker {idx} (@{me.username or me.phone})"
        except Exception:
            lbl = f"Worker {idx}"
        worker_infos.append(lbl)

    queue = asyncio.Queue()
    for idx, u in enumerate(usernames, 1):
        await queue.put((idx, u))

    lock = asyncio.Lock()
    processed_count = 0
    success_count = 0
    fail_count = 0

    async def worker_loop(w_idx: int, client):
        nonlocal processed_count, success_count, fail_count
        w_name = worker_infos[w_idx]

        while not queue.empty():
            try:
                idx, user = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            bar = shopee_core.render_progress_bar(idx, total)
            display = shopee_core.format_account_display(user, auth_method)
            print(f"{CYAN}{bar}{RESET} [{MAGENTA}{w_name}{RESET}] {BOLD}{display}{RESET}")
            is_recheck = user in recheck_set

            try:
                if mode == "misi":
                    coins, status, detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method)
                    is_err = any(err in (status or "").upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))

                    if is_recheck and is_err:
                        async with lock:
                            preserved_records.append({
                                "account": user,
                                "display": display,
                                "status": status,
                                "detail": detail,
                                "reason": f"Cek ulang menghasilkan {status}, hasil sukses lama dipertahankan",
                            })
                            processed_count += 1
                        print(f"  └─ [{w_name}] {YELLOW}🛡️ Cek ulang {status} -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
                    else:
                        shopee_core.save_mission_result(user, coins, status, detail)
                        if status in ("SELESAI", "SUDAH DICLAIM", "BELUM SELESAI"):
                            color = GREEN if status == "SELESAI" else YELLOW
                            c_txt = f"{coins:,} koin" if coins is not None else "-"
                            print(f"  └─ [{w_name}] {color}Bayar QRIS: {c_txt} | Status: {status}{RESET}\n")
                            async with lock:
                                success_count += 1
                                processed_count += 1
                        elif status == "TIDAK ADA MISI QRIS":
                            print(f"  └─ [{w_name}] {YELLOW}⚠️ {status}: {detail}{RESET}\n")
                            async with lock:
                                fail_count += 1
                                processed_count += 1
                        else:
                            print(f"  └─ [{w_name}] {RED}❌ {status}: {detail}{RESET}\n")
                            async with lock:
                                fail_count += 1
                                processed_count += 1

                elif mode == "food":
                    is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)
                    is_err = any(err in (status or "").upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))

                    if is_recheck and is_err:
                        async with lock:
                            preserved_records.append({
                                "account": user,
                                "display": display,
                                "status": status,
                                "detail": detail,
                                "reason": f"Cek ulang menghasilkan {status}, hasil valid lama dipertahankan",
                            })
                            processed_count += 1
                        print(f"  └─ [{w_name}] {YELLOW}🛡️ Cek ulang {status} -> Hasil valid lama DIPERTAHANKAN.{RESET}\n")
                    else:
                        shopee_core.save_food_result(user, is_valid, status, detail, has_25k, has_12k)
                        cat = shopee_core.classify_food_status(is_valid, status)
                        is_cat_valid = (cat == "VALID")
                        color = GREEN if is_cat_valid else (YELLOW if cat == "PARSIAL" else RED)
                        icon = "✅" if is_cat_valid else ("⚠️" if cat == "PARSIAL" else "❌")
                        print(f"  └─ [{w_name}] {color}{icon} {status} ({detail}){RESET}\n")
                        async with lock:
                            if is_cat_valid:
                                success_count += 1
                            else:
                                fail_count += 1
                            processed_count += 1

                elif mode == "both":
                    coins, m_status, m_detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method)
                    await asyncio.sleep(step_delay)
                    is_valid, f_status, f_detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)

                    is_err = any(err in f"{m_status} {f_status}".upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))
                    if is_recheck and is_err:
                        async with lock:
                            preserved_records.append({
                                "account": user,
                                "display": display,
                                "status": f"{m_status} | {f_status}",
                                "detail": f"{m_detail} | {f_detail}",
                                "reason": "Cek ulang timeout/error, hasil sukses lama dipertahankan",
                            })
                            processed_count += 1
                        print(f"  └─ [{w_name}] {YELLOW}🛡️ Cek ulang timeout/error -> Hasil sukses lama DIPERTAHANKAN.{RESET}\n")
                    else:
                        shopee_core.save_mission_result(user, coins, m_status, m_detail)
                        shopee_core.save_food_result(user, is_valid, f_status, f_detail, has_25k, has_12k)
                        shopee_core.save_combined_result(user, coins, m_status, f_status, f_detail)
                        cat = shopee_core.classify_food_status(is_valid, f_status)
                        is_cat_valid = (cat == "VALID")
                        color = GREEN if is_cat_valid else YELLOW
                        c_txt = f"{coins:,} koin" if coins is not None else "-"
                        print(f"  └─ [{w_name}] {color}Misi: {m_status} ({c_txt}) | Food: {f_status} ({f_detail}){RESET}\n")
                        async with lock:
                            processed_count += 1
                            success_count += 1

                elif mode == "ganti_nomor":
                    is_eligible, status, detail = await shopee_core.check_one_change_number(client, user, auth_method=auth_method)
                    is_err = any(err in (status or "").upper() for err in ("TIMEOUT", "ERROR", "FLOOD"))

                    if is_recheck and is_err:
                        async with lock:
                            preserved_records.append({
                                "account": user,
                                "display": display,
                                "status": status,
                                "detail": detail,
                                "reason": f"Cek ulang menghasilkan {status}, hasil layak lama dipertahankan",
                            })
                            processed_count += 1
                        print(f"  └─ [{w_name}] {YELLOW}🛡️ Cek ulang {status} -> Hasil layak lama DIPERTAHANKAN.{RESET}\n")
                    else:
                        shopee_core.save_ganti_nomor_result(user, status, detail, auth_method=auth_method)
                        if status == "SUKSES":
                            print(f"  └─ [{w_name}] {GREEN}{BOLD}✅ {status} ({detail}){RESET}\n")
                            async with lock:
                                success_count += 1
                                processed_count += 1
                        else:
                            print(f"  └─ [{w_name}] {YELLOW}⚠️ {status} ({detail}){RESET}\n")
                            async with lock:
                                fail_count += 1
                                processed_count += 1

            except FloodWaitError as exc:
                print(f"  └─ [{w_name}] {RED}⚠️ Telegram FloodWait {exc.seconds}s! Mengembalikan target ke antrean...{RESET}\n")
                await queue.put((idx, user))
                queue.task_done()
                break
            except Exception as exc:
                print(f"  └─ [{w_name}] {RED}Error: {exc}{RESET}\n")
                async with lock:
                    fail_count += 1
                    processed_count += 1
            finally:
                try:
                    queue.task_done()
                except ValueError:
                    pass

            await asyncio.sleep(step_delay)

    tasks = [asyncio.create_task(worker_loop(i, c)) for i, c in enumerate(clients)]
    await asyncio.gather(*tasks)

    print(f"\n{CYAN}{BOLD}==================== LAPORAN MULTI-WORKER SELESAI ===================={RESET}")
    print(f"🎯 Total Akun       : {total}")
    print(f"👥 Worker Aktif     : {num_workers}")
    print(f"{GREEN}✅ Berhasil Dicek   : {success_count}{RESET}")
    print(f"{RED}❌ Gagal / Sisa     : {fail_count + queue.qsize()}{RESET}")
    if mode == "misi":
        print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_MISI_FILE.name} (CSV) & {shopee_core.RESULTS_MISI_TXT.name} (TXT)\n")
    elif mode == "food":
        print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_FOOD_FILE.name} (CSV) & {shopee_core.RESULTS_FOOD_TXT.name} (TXT)\n")
        print(f"📂 Akun valid (25k + 12k): {shopee_core.VALID_FOOD_FILE.name} | Akun Diskon 25RB: {shopee_core.DISKON_25K_TXT.name}\n")
    elif mode == "ganti_nomor":
        print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_GANTI_NOMOR_FILE.name} (CSV) & {shopee_core.RESULTS_GANTI_NOMOR_TXT.name} (TXT)\n")
    else:
        print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_ALL_FILE.name} (CSV) & {shopee_core.RESULTS_ALL_TXT.name} (TXT)\n")

    if reused_records or preserved_records:
        shopee_core.print_combined_execution_summary(
            mode=mode,
            total_all=total + (len(reused_records) if reused_records else 0),
            total_processed=processed_count,
            new_success=success_count,
            new_fail=fail_count,
            new_error=queue.qsize(),
            reused_records=reused_records or [],
            preserved_records=preserved_records,
            auth_method=auth_method,
        )


async def kelola_workers_menu():
    """Menu interaktif untuk menambah, melihat, dan menghapus sesi worker Telegram."""
    while True:
        sessions = shopee_core.get_available_telegram_sessions()
        print(f"\n{CYAN}{BOLD}===================================================={RESET}")
        print(f"👥 {BOLD}PENGELOLAAN MULTI-WORKER TELEGRAM{RESET}")
        print(f"{CYAN}===================================================={RESET}")
        print(f"Total sesi terdaftar: {len(sessions)} worker")
        for i, s in enumerate(sessions, 1):
            print(f"  [{i}] 📱 {s}.session")
        print("\nPilihan:")
        print("  [1] ➕ Tambah Akun Telegram Worker Baru")
        print("  [2] 📋 Tes & Tampilkan Status Semua Worker")
        print("  [3] 🗑️ Hapus Salah Satu Sesi Worker")
        print("  [0] ↩️ Kembali ke Menu Utama")

        p = input(f"{WHITE}Pilih menu [1/2/3/0]: {RESET}").strip()
        if p == "1":
            new_name = input("\nMasukkan nama file unik worker baru (contoh: worker2, akun_b): ").strip()
            if not new_name:
                new_name = f"worker_{len(sessions) + 1}"
            client = shopee_core.create_client(new_name)
            try:
                await shopee_core.start_client(client)
                me = await client.get_me()
                name = me.first_name or "Telegram User"
                uname = f"@{me.username}" if me.username else f"+{me.phone}"
                print(f"\n{GREEN}{BOLD}🎉 Berhasil menambahkan Worker Baru: {name} ({uname}) [{new_name}.session]!{RESET}")
            except Exception as e:
                print(f"\n{RED}❌ Gagal menambahkan worker: {e}{RESET}")
            finally:
                if client.is_connected():
                    await client.disconnect()
        elif p == "2":
            print(f"\n{YELLOW}🔍 Memeriksa status koneksi seluruh sesi worker...{RESET}")
            for s in sessions:
                c = shopee_core.create_client(s)
                try:
                    await c.connect()
                    if await c.is_user_authorized():
                        me = await c.get_me()
                        name = me.first_name or "User"
                        uname = f"@{me.username}" if me.username else f"+{me.phone}"
                        print(f"  • {GREEN}🟢 {s}.session{RESET} -> {name} ({uname}) [UID: {me.id}]")
                    else:
                        print(f"  • {RED}🔴 {s}.session{RESET} -> Belum login / Sesi kedaluwarsa")
                except Exception as e:
                    print(f"  • {RED}❌ {s}.session{RESET} -> Error: {e}")
                finally:
                    if c.is_connected():
                        await c.disconnect()
        elif p == "3":
            if not sessions:
                print("Tidak ada sesi yang dapat dihapus.")
                continue
            print("\nPilih sesi yang ingin dihapus:")
            for i, s in enumerate(sessions, 1):
                print(f"  [{i}] {s}.session")
            del_idx = input(f"Ketik nomor sesi yang ingin dihapus (1-{len(sessions)}, 0 batal): ").strip()
            if del_idx.isdigit() and 1 <= int(del_idx) <= len(sessions):
                target = sessions[int(del_idx) - 1]
                p_file = Path(f"{target}.session")
                if p_file.exists():
                    p_file.unlink()
                    print(f"{GREEN}✅ File sesi {target}.session berhasil dihapus!{RESET}")
        elif p in ("0", "q", "exit"):
            break


def pilih_metode_auth():
    """Meminta pengguna memilih metode login ke bot Shopee."""
    print(f"\n{CYAN}{BOLD}🔑 PILIH METODE LOGIN BOT (@shp_tools_bot):{RESET}")
    print(f"  [1] 📧 {BOLD}Username / Email / ID{RESET} (Standar)")
    print(f"  [2] 🍪 {BOLD}Raw Cookie{RESET} (SPC_EC / SPC_U)")
    print(f"  [3] 🔄 {BOLD}Otomatis / Auto-Detect{RESET}")
    opt = input(f"{WHITE}Pilih metode login [1/2/3, default 1]: {RESET}").strip()
    if opt == "2":
        return "cookie"
    elif opt == "3":
        return "auto"
    return "username"


async def main():
    parser = argparse.ArgumentParser(description="Shopee Tools Bot All-in-One (Termux & PC)")
    parser.add_argument("file", nargs="?", default=None, help="File berisi daftar username atau raw cookie Shopee")
    parser.add_argument("--mode", choices=["misi", "food", "both", "claim", "ganti_nomor"], help="Pilih mode: misi | food | both | claim | ganti_nomor")
    parser.add_argument("--voucher-link", help="Tautan voucher 1 (diskon) untuk klaim (mode claim)")
    parser.add_argument("--voucher-link-2", help="Tautan voucher 2 (ongkir gratis) untuk klaim (mode claim)")
    parser.add_argument("--method", choices=["username", "cookie", "auto"], default=None, help="Metode login bot: username | cookie | auto")
    parser.add_argument("--cookie", action="store_true", help="Gunakan mode Raw Cookie langsung")
    parser.add_argument("--single", help="Cek 1 akun secara langsung tanpa menu")
    parser.add_argument("--bulk", action="store_true", help="Jalankan dalam mode massal / bulk")
    parser.add_argument("--resume", action="store_true", help="Lewati akun yang sudah pernah dicek di CSV")
    parser.add_argument("--delay", type=float, default=2.5, help="Jeda waktu antar akun (detik, default: 2.5)")
    parser.add_argument("--debug", action="store_true", help="Tampilkan log diagnostik detail (tersamar tanpa kredensial)")
    parser.add_argument("--reset", action="store_true", help="Reset konfigurasi dan sesi Telegram tersimpan")
    args = parser.parse_args()

    if args.reset:
        shopee_core.reset_credentials()
        return

    # Tentukan metode login awal
    if args.cookie:
        auth_method = "cookie"
    elif args.method:
        auth_method = args.method
    else:
        auth_method = None

    # Handle Mode Satuan Cepat dari Argumen CLI
    if args.single:
        mode = args.mode or "misi"
        single_acc = args.single.strip()
        usernames = [single_acc]
        eff_method = auth_method or shopee_core.detect_auth_method(single_acc)
        client = shopee_core.create_client()
        try:
            await shopee_core.start_client(client)
            if mode == "misi":
                await run_misi_mode(client, usernames, auth_method=eff_method, step_delay=args.delay, debug=args.debug)
            elif mode == "food":
                await run_food_mode(client, usernames, auth_method=eff_method, step_delay=args.delay)
            elif mode == "both":
                await run_both_mode(client, usernames, auth_method=eff_method, step_delay=args.delay)
            elif mode == "ganti_nomor":
                await run_change_number_mode(client, usernames, auth_method=eff_method, step_delay=args.delay)
            elif mode == "claim":
                v_links = None
                if getattr(args, "voucher_link", None):
                    v_links = [args.voucher_link]
                    if getattr(args, "voucher_link_2", None):
                        v_links.append(args.voucher_link_2)
                await voucher_claim.run_voucher_claim_mode(
                    client=client,
                    accounts=usernames,
                    voucher_links=v_links,
                    step_delay=args.delay,
                )
        finally:
            await client.disconnect()
        return

    selected_mode = args.mode
    is_bulk = args.bulk
    auto_resume = args.resume
    delay = args.delay
    usernames = []

    # Jika file diberikan di command line, otomatis dianggap mode bulk
    if args.file:
        eff_method = auth_method or "auto"
        usernames = shopee_core.read_usernames(args.file, auth_method=eff_method)
        is_bulk = True

    # Jika mode belum dipilih, tampilkan menu utama interaktif
    if not selected_mode:
        while True:
            print_banner()
            choice = input(f"{WHITE}Pilih menu [1/2/3/4/5/6/7/8/0]: {RESET}").strip()
            if choice == "1":
                selected_mode = "misi"
                break
            elif choice == "2":
                selected_mode = "food"
                break
            elif choice == "3":
                selected_mode = "both"
                break
            elif choice == "4":
                # Mode Massal / Bulk Cepat
                is_bulk = True
                print(f"\n{CYAN}{BOLD}📦 MODE MASSAL / BULK CEPAT{RESET}")
                print(" Mau cek apa untuk daftar massal ini?")
                print("  [1] 🎯 Cek Misi Bayar QRIS")
                print("  [2] 🍔 Cek Voucher Shopee Food")
                print("  [3] ⚡ Cek Keduanya Sekaligus")
                print("  [4] 🎟️ Klaim Voucher ShopeeFood")
                b_opt = input(f"{WHITE}Pilih fitur [1/2/3/4] (Default 1): {RESET}").strip()
                if b_opt == "2":
                    selected_mode = "food"
                elif b_opt == "3":
                    selected_mode = "both"
                elif b_opt == "4":
                    selected_mode = "claim"
                else:
                    selected_mode = "misi"
                break
            elif choice == "5":
                await kelola_workers_menu()
                continue
            elif choice == "6":
                shopee_core.reset_credentials()
                return
            elif choice in ("7", "claim", "klaim"):
                await voucher_claim.interactive_voucher_claim_menu()
                return
            elif choice in ("8", "ganti_nomor", "gn"):
                selected_mode = "ganti_nomor"
                break
            elif choice in ("0", "q", "exit"):
                print("Sampai jumpa!")
                return
            else:
                print("❌ Pilihan tidak valid, silakan ketik angka 1 sampai 8, atau 0.")

    # Jika mode claim, metode login spesifik bot check-in (cookie/username) tidak diperlukan
    if selected_mode == "claim":
        auth_method = auth_method or "username"
    elif not auth_method:
        auth_method = pilih_metode_auth()

    reused_records = []
    recheck_targets = set()
    account_vouchers_plan = None

    # Loop pemilihan akun & penanganan resume/reuse
    while True:
        # Jika usernames belum diisi dari argumen file atau pengguna memilih 'b' untuk ganti sumber
        if not usernames:
            if not is_bulk:
                while True:
                    print(f"\n{CYAN}{BOLD}⚙️ LANGKAH B - PILIH TIPE EKSEKUSI PENGISIAN AKUN:{RESET}")
                    print(f"  [1] ⚡ {BOLD}Isi Manual (1 Akun){RESET}")
                    print(f"      👉 Langsung ketik 1 akun (username atau cookie) di terminal.")
                    print(f"      👉 Dilengkapi validasi format, preview tersamar, & konfirmasi.")
                    print(f"  [2] 📦 {BOLD}Mode Massal / Bulk{RESET}")
                    print(f"      👉 Dituntun wizard 3 langkah: pilih sumber file / paste,")
                    print(f"         panduan format sesuai metode, & preview tersamar.")
                    tipe = input(f"{WHITE}Pilih tipe eksekusi [1/2, default: 2]: {RESET}").strip()
                    if tipe == "1":
                        acc = input_manual_account(auth_method=auth_method)
                        if not acc:
                            print(f"{YELLOW}↩️ Kembali ke pilihan tipe eksekusi.{RESET}")
                            continue
                        usernames = [acc]
                        break
                    elif tipe in ("", "2"):
                        is_bulk = True
                        usernames = pilih_daftar_akun_bulk(auth_method=auth_method)
                        break
                    else:
                        print(f"{YELLOW}⚠️ Pilihan tidak valid, silakan ketik 1 atau 2.{RESET}")
            else:
                usernames = pilih_daftar_akun_bulk(auth_method=auth_method)

        if not usernames:
            return

        # Opsi Auto-Resume / Reuse hasil sebelumnya jika dalam mode bulk
        if is_bulk and len(usernames) > 1:
            if selected_mode == "claim":
                v_links = None
                if getattr(args, "voucher_link", None):
                    v_links = [args.voucher_link]
                    if getattr(args, "voucher_link_2", None):
                        v_links.append(args.voucher_link_2)
                action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                    usernames=usernames,
                    voucher_links=v_links,
                    auth_method=auth_method,
                    auto_mode="reuse" if auto_resume else None,
                )
                if action == "back":
                    print(f"\n{YELLOW}↩️ Kembali ke pemilihan sumber akun...{RESET}")
                    usernames = None
                    continue
                elif action == "finish":
                    voucher_claim.print_claim_combined_summary(
                        total_accounts=len(usernames),
                        total_tasks=len(usernames) * 2,
                        newly_results=[],
                        reused_records=reused,
                        preserved_records=[],
                        auth_method=auth_method,
                    )
                    return
                else:
                    usernames = to_proc
                    reused_records = reused
                    recheck_targets = recheck_accs
                    account_vouchers_plan = plan
                    break
            else:
                action, to_proc, reused, recheck_accs = shopee_core.handle_reuse_or_recheck_wizard(
                    usernames=usernames,
                    mode=selected_mode,
                    auth_method=auth_method,
                    auto_mode="reuse" if auto_resume else None,
                )
                if action == "back":
                    print(f"\n{YELLOW}↩️ Kembali ke pemilihan sumber akun...{RESET}")
                    usernames = None
                    continue
                elif action == "finish":
                    # Pengguna memilih selesai, tampilkan laporan gabungan langsung
                    shopee_core.print_combined_execution_summary(
                        mode=selected_mode,
                        total_all=len(usernames),
                        total_processed=0,
                        new_success=0,
                        new_fail=0,
                        new_error=0,
                        reused_records=reused,
                        preserved_records=[],
                        auth_method=auth_method,
                    )
                    return
                else:
                    usernames = to_proc
                    reused_records = reused
                    recheck_targets = recheck_accs
                    break
        else:
            break

    print(f"\n{GREEN}✅ Total akun/cookie yang akan diproses: {len(usernames)} akun (Metode: {auth_method.upper()}).{RESET}")

    # Cek ketersediaan Multi-Worker
    sessions = shopee_core.get_available_telegram_sessions()
    use_multi = False
    if len(sessions) > 1 and len(usernames) > 1 and selected_mode != "claim":
        print(f"\n{CYAN}{BOLD}👥 TERDETEKSI {len(sessions)} SESI TELEGRAM WORKER:{RESET}")
        for s in sessions:
            print(f"  • {s}.session")
        print(" [1] 🚀 Jalankan Multi-Worker Paralel (Lebih cepat, beban dibagi rata)")
        print(" [2] 👤 Jalankan 1 Akun Telegram Saja (Standar)")
        w_choice = input(f"{WHITE}Pilih mode eksekusi [1/2, default 1]: {RESET}").strip()
        if w_choice in ("", "1"):
            use_multi = True

    if use_multi:
        clients = [shopee_core.create_client(s) for s in sessions]
        active_clients = []
        try:
            for c in clients:
                await shopee_core.start_client(c)
                active_clients.append(c)
            print(f"\n{GREEN}✅ {len(active_clients)} Worker Telegram siap bertugas!{RESET}")
            await run_worker_pool_mode(
                active_clients,
                usernames,
                mode=selected_mode,
                auth_method=auth_method,
                step_delay=delay,
                reused_records=reused_records,
                recheck_targets=recheck_targets,
            )
        finally:
            for c in active_clients:
                try:
                    await c.disconnect()
                except Exception:
                    pass
    else:
        # Single client
        primary_session = sessions[0] if sessions else None
        client = shopee_core.create_client(primary_session)
        try:
            await shopee_core.start_client(client)
            print(f"{GREEN}✅ Terhubung ke Telegram! Memulai antrean...{RESET}")

            if selected_mode == "misi":
                await run_misi_mode(
                    client,
                    usernames,
                    auth_method=auth_method,
                    step_delay=delay,
                    reused_records=reused_records,
                    recheck_targets=recheck_targets,
                    debug=getattr(args, "debug", False),
                )
            elif selected_mode == "food":
                await run_food_mode(
                    client,
                    usernames,
                    auth_method=auth_method,
                    step_delay=delay,
                    reused_records=reused_records,
                    recheck_targets=recheck_targets,
                )
            elif selected_mode == "both":
                await run_both_mode(
                    client,
                    usernames,
                    auth_method=auth_method,
                    step_delay=delay,
                    reused_records=reused_records,
                    recheck_targets=recheck_targets,
                )
            elif selected_mode == "ganti_nomor":
                await run_change_number_mode(
                    client,
                    usernames,
                    auth_method=auth_method,
                    step_delay=delay,
                    reused_records=reused_records,
                    recheck_targets=recheck_targets,
                )
            elif selected_mode == "claim":
                v_links = None
                if getattr(args, "voucher_link", None):
                    v_links = [args.voucher_link]
                    if getattr(args, "voucher_link_2", None):
                        v_links.append(args.voucher_link_2)
                await voucher_claim.run_voucher_claim_mode(
                    client=client,
                    accounts=usernames,
                    voucher_links=v_links,
                    step_delay=delay,
                    reused_records=reused_records,
                    recheck_targets=recheck_targets,
                    account_vouchers_plan=account_vouchers_plan,
                )
        finally:
            await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\n\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\n❌ Terjadi kesalahan: {exc}")
