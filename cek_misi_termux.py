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
 {WHITE}5.{RESET} ⚙️  {BOLD}Reset Pengaturan{RESET}        (Hapus Sesi & API Telegram)
 {WHITE}0.{RESET} 🚪 {BOLD}Keluar{RESET}
{CYAN}======================================================================{RESET}
"""
    print(banner)


def pilih_daftar_akun_bulk():
    """Menampilkan pilihan file teks di folder atau paste langsung untuk mode bulk."""
    txt_files = shopee_core.get_available_txt_files()

    print(f"\n{CYAN}{BOLD}📦 PILIH SUMBER AKUN MODE MASSAL (BULK):{RESET}")
    menu_idx = 1
    file_map = {}

    if txt_files:
        print("  Ditemukan file teks di folder ini:")
        for path_obj, count in txt_files:
            print(f"  [{menu_idx}] 📄 {BOLD}{path_obj.name}{RESET} ({count} akun)")
            file_map[str(menu_idx)] = path_obj
            menu_idx += 1
        print(f"  [{menu_idx}] 📁 Ketik nama/path file lain")
        other_choice = str(menu_idx)
        menu_idx += 1
        print(f"  [{menu_idx}] ✍️  Paste langsung banyak akun sekaligus")
        paste_choice = str(menu_idx)
    else:
        print(f"  [1] 📁 Masukkan nama/path file teks")
        print(f"  [2] ✍️  Paste langsung banyak akun sekaligus")
        other_choice = "1"
        paste_choice = "2"

    pilihan = input(f"\n{WHITE}Pilih sumber [1-{menu_idx}]: {RESET}").strip()

    if pilihan in file_map:
        return shopee_core.read_usernames(file_map[pilihan])
    elif pilihan == other_choice:
        fname = input("Masukkan path / nama file: ").strip()
        return shopee_core.read_usernames(fname)
    elif pilihan == paste_choice:
        print("\nSilakan tempel (paste) daftar akun Anda di bawah ini.")
        print("(Bisa satu per baris, atau dipisah koma/spasi).")
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
        return shopee_core.parse_raw_usernames("\n".join(lines))
    else:
        print("⚠️ Pilihan tidak valid, mencoba membaca file default...")
        if Path("daftar_username.txt").is_file():
            return shopee_core.read_usernames("daftar_username.txt")
        elif Path("food.txt").is_file():
            return shopee_core.read_usernames("food.txt")
        return shopee_core.read_usernames()


async def run_misi_mode(client, usernames, step_delay=2.5):
    total = len(usernames)
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Misi Bayar QRIS ({total} akun)...{RESET}\n")
    success_count = 0
    fail_count = 0

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        print(f"{CYAN}{bar}{RESET} {BOLD}{user}{RESET}")
        try:
            coins, status, detail = await shopee_core.check_one_mission(client, user)
            shopee_core.save_mission_result(user, coins, status, detail)

            if coins is not None:
                color = GREEN if status == "SELESAI" else YELLOW
                print(f"  └─ {color}{BOLD}Bayar QRIS: {coins:,} koin | {status}{RESET}\n")
                success_count += 1
            else:
                print(f"  └─ {RED}{status}: {detail}{RESET}\n")
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
    print(f"📂 Rincian CSV tersimpan di: {shopee_core.RESULTS_MISI_FILE.resolve()}\n")


async def run_food_mode(client, usernames, step_delay=2.5):
    total = len(usernames)
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Voucher Shopee Food ({total} akun)...{RESET}\n")
    valid_count = 0
    invalid_count = 0
    valid_list = []

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        print(f"{CYAN}{bar}{RESET} {BOLD}{user}{RESET}")
        try:
            is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, user)
            shopee_core.save_food_result(user, is_valid, status, detail, has_25k, has_12k)

            if is_valid:
                print(f"  └─ {GREEN}{BOLD}✅ {status} ({detail}){RESET}\n")
                valid_count += 1
                valid_list.append(user)
            elif status == "PARSIAL":
                print(f"  └─ {YELLOW}⚠️ {status} ({detail}){RESET}\n")
                invalid_count += 1
            else:
                print(f"  └─ {RED}❌ {status} ({detail}){RESET}\n")
                invalid_count += 1
        except FloodWaitError as exc:
            msg = f"Telegram meminta jeda {exc.seconds} detik. Antrean dihentikan."
            shopee_core.save_food_result(user, False, "FLOOD_WAIT", msg, False, False)
            print(f"  └─ {RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            shopee_core.save_food_result(user, False, "ERROR", str(exc), False, False)
            print(f"  └─ {RED}Error: {exc}{RESET}\n")
            invalid_count += 1

        if idx < total:
            await asyncio.sleep(step_delay)

    print(f"{CYAN}{BOLD}==================== LAPORAN HASIL VOUCHER FOOD ===================={RESET}")
    print(f"🎯 Total Akun       : {total}")
    print(f"{GREEN}✅ Memenuhi Syarat  : {valid_count}{RESET}")
    print(f"{YELLOW}⚠️ Belum Memenuhi   : {invalid_count}{RESET}")
    if valid_list:
        print(f"\n{GREEN}{BOLD}★ DAFTAR AKUN MEMENUHI SYARAT (25RB + 12RB):{RESET}")
        for u in valid_list:
            print(f"  • {u}")
    print(f"\n📂 Akun valid disimpan di : {shopee_core.VALID_FOOD_FILE.resolve()}")
    print(f"📂 Rincian CSV tersimpan di: {shopee_core.RESULTS_FOOD_FILE.resolve()}\n")


async def run_both_mode(client, usernames, step_delay=2.5):
    total = len(usernames)
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Keduanya (Misi QRIS + Voucher Food) ({total} akun)...{RESET}\n")

    for idx, user in enumerate(usernames, 1):
        bar = shopee_core.render_progress_bar(idx, total)
        print(f"{CYAN}{bar}{RESET} {BOLD}{user}{RESET}")
        try:
            # 1. Cek Misi QRIS
            print(f"  [1/2] Memeriksa Misi QRIS...")
            coins, m_status, m_detail = await shopee_core.check_one_mission(client, user)
            shopee_core.save_mission_result(user, coins, m_status, m_detail)
            if coins is not None:
                color = GREEN if m_status == "SELESAI" else YELLOW
                print(f"        └─ {color}Bayar QRIS: {coins:,} koin | {m_status}{RESET}")
            else:
                print(f"        └─ {RED}{m_status}: {m_detail}{RESET}")

            await asyncio.sleep(step_delay)

            # 2. Cek Voucher Food
            print(f"  [2/2] Memeriksa Voucher Shopee Food...")
            is_valid, f_status, f_detail, has_25k, has_12k = await shopee_core.check_one_food(client, user)
            shopee_core.save_food_result(user, is_valid, f_status, f_detail, has_25k, has_12k)
            if is_valid:
                print(f"        └─ {GREEN}✅ {f_status} ({f_detail}){RESET}\n")
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
    print(f"📂 Hasil lengkap gabungan tersimpan di: {shopee_core.RESULTS_ALL_FILE.resolve()}\n")


async def main():
    parser = argparse.ArgumentParser(description="Shopee Tools Bot All-in-One (Termux & PC)")
    parser.add_argument("file", nargs="?", default=None, help="File berisi daftar username Shopee")
    parser.add_argument("--mode", choices=["misi", "food", "both"], help="Pilih mode: misi | food | both")
    parser.add_argument("--single", help="Cek 1 akun secara langsung tanpa menu")
    parser.add_argument("--bulk", action="store_true", help="Jalankan dalam mode massal / bulk")
    parser.add_argument("--resume", action="store_true", help="Lewati akun yang sudah pernah dicek di CSV")
    parser.add_argument("--delay", type=float, default=2.5, help="Jeda waktu antar akun (detik, default: 2.5)")
    parser.add_argument("--reset", action="store_true", help="Reset konfigurasi dan sesi Telegram tersimpan")
    args = parser.parse_args()

    if args.reset:
        shopee_core.reset_credentials()
        return

    # Handle Mode Satuan Cepat dari Argumen CLI
    if args.single:
        mode = args.mode or "misi"
        usernames = [args.single.strip()]
        client = shopee_core.create_client()
        try:
            await shopee_core.start_client(client)
            if mode == "misi":
                await run_misi_mode(client, usernames, args.delay)
            elif mode == "food":
                await run_food_mode(client, usernames, args.delay)
            elif mode == "both":
                await run_both_mode(client, usernames, args.delay)
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
        usernames = shopee_core.read_usernames(args.file)
        is_bulk = True

    # Jika mode belum dipilih, tampilkan menu utama interaktif
    if not selected_mode:
        print_banner()
        while True:
            choice = input(f"{WHITE}Pilih menu [1/2/3/4/5/0]: {RESET}").strip()
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
                b_opt = input(f"{WHITE}Pilih fitur [1/2/3] (Default 1): {RESET}").strip()
                if b_opt == "2":
                    selected_mode = "food"
                elif b_opt == "3":
                    selected_mode = "both"
                else:
                    selected_mode = "misi"
                break
            elif choice == "5":
                shopee_core.reset_credentials()
                return
            elif choice in ("0", "q", "exit"):
                print("Sampai jumpa!")
                return
            else:
                print("❌ Pilihan tidak valid, silakan ketik angka 1 sampai 5, atau 0.")

    # Jika usernames belum diisi dari argumen file
    if not usernames:
        if not is_bulk:
            print(f"\n{CYAN}{BOLD}--- TIPE EKSEKUSI ---{RESET}")
            print(" [1] ⚡ Mode Satuan (Cek 1 Akun Cepat)")
            print(" [2] 📦 Mode Massal / Bulk (Banyak Akun dari File / Paste)")
            tipe = input(f"{WHITE}Pilih tipe [1/2] (Default 2): {RESET}").strip()
            if tipe == "1":
                acc = input("\nMasukkan 1 username Shopee: ").strip()
                if not acc:
                    print("❌ Username tidak boleh kosong.")
                    return
                usernames = [acc]
            else:
                is_bulk = True
                usernames = pilih_daftar_akun_bulk()
        else:
            usernames = pilih_daftar_akun_bulk()

    # Opsi Auto-Resume (Lewati akun yang sudah pernah dicek) jika dalam mode bulk
    if is_bulk and len(usernames) > 1 and not auto_resume:
        ask_resume = input(f"\nLewati akun yang sudah ada hasil suksesnya di CSV? (Y/n) [Default: Y]: ").strip().casefold()
        if ask_resume in ("", "y", "ya", "yes"):
            auto_resume = True

    if auto_resume:
        to_process, skipped = shopee_core.filter_unprocessed_usernames(usernames, selected_mode)
        if skipped > 0:
            print(f"\n{GREEN}ℹ️ Fitur Resume Aktif: {skipped} akun sudah pernah dicek dan dilewati.{RESET}")
            print(f"👉 Tersisa {len(to_process)} akun yang akan diproses sekarang.")
            usernames = to_process
            if not usernames:
                print(f"{GREEN}🎉 Semua akun dalam daftar sudah selesai dicek sebelumnya! Tidak ada antrean.{RESET}")
                return

    print(f"\n{GREEN}✅ Total akun yang akan diproses: {len(usernames)} akun.{RESET}")

    # Buat client dan koneksi Telegram
    client = shopee_core.create_client()
    try:
        await shopee_core.start_client(client)
        print(f"{GREEN}✅ Terhubung ke Telegram! Memulai antrean...{RESET}")

        if selected_mode == "misi":
            await run_misi_mode(client, usernames, delay)
        elif selected_mode == "food":
            await run_food_mode(client, usernames, delay)
        elif selected_mode == "both":
            await run_both_mode(client, usernames, delay)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\n\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\n❌ Terjadi kesalahan: {exc}")
