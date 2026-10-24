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
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
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
 {WHITE}0.{RESET} 🚪 {BOLD}Keluar{RESET}
{CYAN}======================================================================{RESET}
"""
    print(banner)


def pilih_daftar_akun_bulk(auth_method: str = "auto"):
    """Menampilkan pilihan file teks di folder atau paste langsung untuk mode bulk."""
    txt_files = shopee_core.get_available_txt_files()

    print(f"\n{CYAN}{BOLD}📦 PILIH SUMBER AKUN MODE MASSAL (BULK):{RESET}")
    menu_idx = 1
    file_map = {}

    if txt_files:
        print("  Ditemukan file teks di folder ini:")
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
        print(f"  [1] 📁 Masukkan nama/path file teks")
        print(f"  [2] ✍️  Paste langsung banyak akun/cookie sekaligus")
        other_choice = "1"
        paste_choice = "2"

    pilihan = input(f"\n{WHITE}Pilih sumber [1-{menu_idx}]: {RESET}").strip()

    if pilihan in file_map:
        return shopee_core.read_usernames(file_map[pilihan], auth_method=auth_method)
    elif pilihan == other_choice:
        fname = input("Masukkan path / nama file: ").strip()
        return shopee_core.read_usernames(fname, auth_method=auth_method)
    elif pilihan == paste_choice:
        print("\nSilakan tempel (paste) daftar akun atau raw cookie Anda di bawah ini.")
        if auth_method == "cookie":
            print("(1 Raw Cookie per baris)")
        else:
            print("(Bisa satu per baris, atau dipisah koma/spasi untuk username).")
        print("Tekan Enter dua kali (pada baris kosong) untuk selesai:")
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
        return shopee_core.parse_raw_accounts("\n".join(lines), auth_method=auth_method)
    else:
        print("⚠️ Pilihan tidak valid, mencoba membaca file default...")
        if Path("daftar_username.txt").is_file():
            return shopee_core.read_usernames("daftar_username.txt", auth_method=auth_method)
        elif Path("food.txt").is_file():
            return shopee_core.read_usernames("food.txt", auth_method=auth_method)
        return shopee_core.read_usernames(auth_method=auth_method)


async def run_misi_mode(client, usernames, auth_method="username", step_delay=2.5):
    total = len(usernames)
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Misi Bayar QRIS ({total} akun/cookie, Metode: {auth_method.upper()})...{RESET}\n")
    success_count = 0
    fail_count = 0

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        display = shopee_core.format_account_display(user, auth_method)
        print(f"{CYAN}{bar}{RESET} {BOLD}{display}{RESET}")
        try:
            coins, status, detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method)
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
            shopee_core.save_mission_result(user, None, "FLOOD_WAIT", msg)
            print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            shopee_core.save_mission_result(user, None, "ERROR", str(exc))
            print(f"  └─ {RED}Error: {exc}{RESET}\n")
            fail_count += 1

        if idx < total:
            await asyncio.sleep(step_delay)

    print(f"{CYAN}{BOLD}==================== LAPORAN SELESAI ===================={RESET}")
    print(f"🎯 Total Akun       : {total}")
    print(f"{GREEN}✅ Berhasil Dicek   : {success_count}{RESET}")
    print(f"{RED}❌ Gagal / Tidak Ada: {fail_count}{RESET}")
    print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_MISI_FILE.name} (CSV) & {shopee_core.RESULTS_MISI_TXT.name} (TXT)\n")


async def run_food_mode(client, usernames, auth_method="username", step_delay=2.5):
    total = len(usernames)
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
        try:
            is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)
            shopee_core.save_food_result(user, is_valid, status, detail, has_25k, has_12k)
            processed_count += 1

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
            shopee_core.save_food_result(user, False, "FLOOD_WAIT", msg, False, False)
            processed_count += 1
            error_count += 1
            print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            shopee_core.save_food_result(user, False, "ERROR", str(exc), False, False)
            print(f"  └─ {RED}Error: {exc}{RESET}\n")
            processed_count += 1
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


async def run_both_mode(client, usernames, auth_method="username", step_delay=2.5):
    total = len(usernames)
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Keduanya (Misi QRIS + Voucher Food) ({total} akun/cookie, Metode: {auth_method.upper()})...{RESET}\n")

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        display = shopee_core.format_account_display(user, auth_method)
        print(f"{CYAN}{bar}{RESET} {BOLD}{display}{RESET}")
        try:
            # 1. Cek Misi QRIS
            print(f"  [1/2] Memeriksa Misi QRIS...")
            coins, m_status, m_detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method)
            shopee_core.save_mission_result(user, coins, m_status, m_detail)
            if m_status in ("SELESAI", "SUDAH DICLAIM", "BELUM SELESAI"):
                color = GREEN if m_status == "SELESAI" else YELLOW
                c_str = f"{coins:,} koin" if coins is not None else "-"
                print(f"        └─ {color}Bayar QRIS: {c_str} | {m_status}{RESET}")
            elif m_status == "TIDAK ADA MISI QRIS":
                print(f"        └─ {YELLOW}⚠️ {m_status}: {m_detail}{RESET}")
            else:
                print(f"        └─ {RED}❌ {m_status}: {m_detail}{RESET}")

            await asyncio.sleep(step_delay)

            # 2. Cek Voucher Food
            print(f"  [2/2] Memeriksa Voucher Shopee Food...")
            is_valid, f_status, f_detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)
            shopee_core.save_food_result(user, is_valid, f_status, f_detail, has_25k, has_12k)
            f_cat = shopee_core.classify_food_status(is_valid, f_status)
            if f_cat == "VALID":
                print(f"        └─ {GREEN}✅ {f_status} ({f_detail}){RESET}\n")
            elif f_cat == "PARSIAL":
                print(f"        └─ {YELLOW}⚠️ {f_status} ({f_detail}){RESET}\n")
            elif f_cat == "ERROR":
                print(f"        └─ {RED}❌ {f_status} ({f_detail}){RESET}\n")
            else:
                print(f"        └─ {YELLOW}⚠️ {f_status} ({f_detail}){RESET}\n")

            # 3. Simpan laporan gabungan
            shopee_core.save_combined_result(user, coins, m_status, f_status, f_detail)

        except FloodWaitError as exc:
            print(f"  └─ {RED}⚠️ Telegram FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            print(f"  └─ {RED}Error: {exc}{RESET}\n")

        if idx < total:
            await asyncio.sleep(step_delay)

    print(f"{CYAN}{BOLD}==================== PENGECEKAN GABUNGAN SELESAI ===================={RESET}")
    print(f"📂 Hasil lengkap tersimpan di: {shopee_core.RESULTS_ALL_FILE.name} (CSV) & {shopee_core.RESULTS_ALL_TXT.name} (TXT)\n")


async def run_worker_pool_mode(clients, usernames, mode="misi", auth_method="auto", step_delay=2.5):
    """Menjalankan pengecekan secara paralel menggunakan multiple worker Telegram."""
    total = len(usernames)
    num_workers = len(clients)
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

            try:
                if mode == "misi":
                    coins, status, detail = await shopee_core.check_one_mission(client, user, auth_method=auth_method)
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
                    shopee_core.save_mission_result(user, coins, m_status, m_detail)
                    await asyncio.sleep(step_delay)
                    is_valid, f_status, f_detail, has_25k, has_12k = await shopee_core.check_one_food(client, user, auth_method=auth_method)
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
    else:
        print(f"📂 Rincian tersimpan di: {shopee_core.RESULTS_ALL_FILE.name} (CSV) & {shopee_core.RESULTS_ALL_TXT.name} (TXT)\n")


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
    parser.add_argument("--mode", choices=["misi", "food", "both", "claim"], help="Pilih mode: misi | food | both | claim")
    parser.add_argument("--voucher-link", help="Tautan voucher untuk klaim (mode claim)")
    parser.add_argument("--method", choices=["username", "cookie", "auto"], default=None, help="Metode login bot: username | cookie | auto")
    parser.add_argument("--cookie", action="store_true", help="Gunakan mode Raw Cookie langsung")
    parser.add_argument("--single", help="Cek 1 akun secara langsung tanpa menu")
    parser.add_argument("--bulk", action="store_true", help="Jalankan dalam mode massal / bulk")
    parser.add_argument("--resume", action="store_true", help="Lewati akun yang sudah pernah dicek di CSV")
    parser.add_argument("--delay", type=float, default=2.5, help="Jeda waktu antar akun (detik, default: 2.5)")
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
                await run_misi_mode(client, usernames, auth_method=eff_method, step_delay=args.delay)
            elif mode == "food":
                await run_food_mode(client, usernames, auth_method=eff_method, step_delay=args.delay)
            elif mode == "both":
                await run_both_mode(client, usernames, auth_method=eff_method, step_delay=args.delay)
            elif mode == "claim":
                await voucher_claim.run_voucher_claim_mode(
                    client=client,
                    accounts=usernames,
                    voucher_link=args.voucher_link,
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
            choice = input(f"{WHITE}Pilih menu [1/2/3/4/5/6/7/0]: {RESET}").strip()
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
            elif choice in ("0", "q", "exit"):
                print("Sampai jumpa!")
                return
            else:
                print("❌ Pilihan tidak valid, silakan ketik angka 1 sampai 7, atau 0.")

    # Jika mode claim, metode login spesifik bot check-in (cookie/username) tidak diperlukan
    if selected_mode == "claim":
        auth_method = auth_method or "username"
    elif not auth_method:
        auth_method = pilih_metode_auth()

    # Jika usernames belum diisi dari argumen file
    if not usernames:
        if not is_bulk:
            print(f"\n{CYAN}{BOLD}--- TIPE EKSEKUSI ---{RESET}")
            print(" [1] ⚡ Mode Satuan (Cek 1 Akun/Cookie Cepat)")
            print(" [2] 📦 Mode Massal / Bulk (Banyak Akun dari File / Paste)")
            tipe = input(f"{WHITE}Pilih tipe [1/2] (Default 2): {RESET}").strip()
            if tipe == "1":
                prompt_label = "raw cookie" if auth_method == "cookie" else "username"
                acc = input(f"\nMasukkan 1 {prompt_label} Shopee: ").strip()
                if not acc:
                    print("❌ Input tidak boleh kosong.")
                    return
                usernames = [acc]
            else:
                is_bulk = True
                usernames = pilih_daftar_akun_bulk(auth_method=auth_method)
        else:
            usernames = pilih_daftar_akun_bulk(auth_method=auth_method)

    # Opsi Auto-Resume (Lewati akun yang sudah pernah dicek) jika dalam mode bulk dan bukan claim
    if is_bulk and len(usernames) > 1 and not auto_resume and selected_mode != "claim":
        ask_resume = input(f"\nLewati akun yang sudah ada hasil suksesnya di CSV? (Y/n) [Default: Y]: ").strip().casefold()
        if ask_resume in ("", "y", "ya", "yes"):
            auto_resume = True

    if auto_resume and selected_mode != "claim":
        to_process, skipped = shopee_core.filter_unprocessed_usernames(usernames, selected_mode)
        if skipped > 0:
            print(f"\n{GREEN}ℹ️ Fitur Resume Aktif: {skipped} akun sudah pernah dicek dan dilewati.{RESET}")
            print(f"👉 Tersisa {len(to_process)} akun yang akan diproses sekarang.")
            usernames = to_process
            if not usernames:
                print(f"{GREEN}🎉 Semua akun dalam daftar sudah selesai dicek sebelumnya! Tidak ada antrean.{RESET}")
                return

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
            await run_worker_pool_mode(active_clients, usernames, mode=selected_mode, auth_method=auth_method, step_delay=delay)
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
                await run_misi_mode(client, usernames, auth_method=auth_method, step_delay=delay)
            elif selected_mode == "food":
                await run_food_mode(client, usernames, auth_method=auth_method, step_delay=delay)
            elif selected_mode == "both":
                await run_both_mode(client, usernames, auth_method=auth_method, step_delay=delay)
            elif selected_mode == "claim":
                await voucher_claim.run_voucher_claim_mode(
                    client=client,
                    accounts=usernames,
                    voucher_link=getattr(args, "voucher_link", None),
                    step_delay=delay,
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
