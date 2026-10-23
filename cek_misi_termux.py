#!/usr/bin/env python3
"""Shopee Tools All-in-One: Cek Misi QRIS & Cek Voucher Shopee Food.

Mendukung eksekusi di Android Termux & PC.
Bisa dijalankan interaktif:
    python cek_misi_termux.py

Atau dengan file daftar akun:
    python cek_misi_termux.py daftar_username.txt
    python cek_misi_termux.py food.txt --mode food
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
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""
{CYAN}{BOLD}======================================================================
     🚀 SHOPEE BOT ALL-IN-ONE (TERMUX & PC AUTOMATION)
======================================================================{RESET}
 {WHITE}1.{RESET} 🎯 {BOLD}Cek Misi Bayar QRIS{RESET}  (Pengecekan Check-in Koin QRIS)
 {WHITE}2.{RESET} 🍔 {BOLD}Cek Voucher Shopee Food{RESET} (Diskon 25RB & Ongkir 12RB)
 {WHITE}3.{RESET} ⚡ {BOLD}Cek Keduanya Sekaligus{RESET}  (Misi QRIS + Voucher Food)
 {WHITE}4.{RESET} ⚙️  {BOLD}Reset Pengaturan{RESET}       (Hapus Sesi & API ID/Hash Telegram)
 {WHITE}0.{RESET} 🚪 {BOLD}Keluar{RESET}
{CYAN}======================================================================{RESET}
"""
    print(banner)


async def run_misi_mode(client, usernames):
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Misi Bayar QRIS untuk {len(usernames)} akun...{RESET}\n")
    success_count = 0
    fail_count = 0

    for idx, user in enumerate(usernames, 1):
        print(f"{CYAN}[{idx}/{len(usernames)}]{RESET} {BOLD}{user}{RESET}")
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
            print(f"  └─ {RED}FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            shopee_core.save_mission_result(user, None, "ERROR", str(exc))
            print(f"  └─ {RED}Error: {exc}{RESET}\n")
            fail_count += 1

        if idx < len(usernames):
            await asyncio.sleep(shopee_core.STEP_DELAY)

    print(f"{CYAN}{BOLD}--- LAPORAN SELESAI ---{RESET}")
    print(f"Total: {len(usernames)} | Berhasil/Ada: {success_count} | Gagal/Kosong: {fail_count}")
    print(f"📂 Hasil tersimpan di: {shopee_core.RESULTS_MISI_FILE.resolve()}\n")


async def run_food_mode(client, usernames):
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Voucher Shopee Food untuk {len(usernames)} akun...{RESET}\n")
    valid_count = 0
    invalid_count = 0
    valid_list = []

    for idx, user in enumerate(usernames, 1):
        print(f"{CYAN}[{idx}/{len(usernames)}]{RESET} {BOLD}{user}{RESET}")
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
            print(f"  └─ {RED}FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            shopee_core.save_food_result(user, False, "ERROR", str(exc), False, False)
            print(f"  └─ {RED}Error: {exc}{RESET}\n")
            invalid_count += 1

        if idx < len(usernames):
            await asyncio.sleep(shopee_core.STEP_DELAY)

    print(f"{CYAN}{BOLD}--- LAPORAN HASIL VOUCHER SHOPEE FOOD ---{RESET}")
    print(f"🎯 Total Akun       : {len(usernames)}")
    print(f"{GREEN}✅ Memenuhi Syarat  : {valid_count}{RESET}")
    print(f"{YELLOW}⚠️ Belum Memenuhi   : {invalid_count}{RESET}")
    if valid_list:
        print(f"\n{GREEN}{BOLD}Daftar Akun Memenuhi Syarat:{RESET}")
        for u in valid_list:
            print(f"  • {u}")
    print(f"\n📂 Akun valid disimpan di : {shopee_core.VALID_FOOD_FILE.resolve()}")
    print(f"📂 Rincian CSV disimpan di: {shopee_core.RESULTS_FOOD_FILE.resolve()}\n")


async def run_both_mode(client, usernames):
    print(f"\n{YELLOW}{BOLD}▶ Memulai Pengecekan Keduanya (Misi QRIS + Voucher Food) untuk {len(usernames)} akun...{RESET}\n")

    for idx, user in enumerate(usernames, 1):
        print(f"{CYAN}[{idx}/{len(usernames)}]{RESET} {BOLD}{user}{RESET}")
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

            await asyncio.sleep(shopee_core.STEP_DELAY)

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
            print(f"  └─ {RED}Telegram FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}\n")
            break
        except Exception as exc:
            print(f"  └─ {RED}Error: {exc}{RESET}\n")

        if idx < len(usernames):
            await asyncio.sleep(shopee_core.STEP_DELAY)

    print(f"{CYAN}{BOLD}--- PENGECEKAN GABUNGAN SELESAI ---{RESET}")
    print(f"📂 Hasil lengkap gabungan tersimpan di: {shopee_core.RESULTS_ALL_FILE.resolve()}\n")


async def main():
    parser = argparse.ArgumentParser(description="Shopee Tools Bot All-in-One")
    parser.add_argument("file", nargs="?", default=None, help="File berisi daftar username Shopee")
    parser.add_argument("--mode", choices=["misi", "food", "both"], help="Mode pengecekan langsung")
    parser.add_argument("--reset", action="store_true", help="Reset konfigurasi dan sesi Telegram tersimpan")
    args = parser.parse_args()

    if args.reset:
        shopee_core.reset_credentials()
        return

    selected_mode = args.mode
    input_file = args.file

    if not selected_mode:
        print_banner()
        while True:
            choice = input(f"{WHITE}Pilih menu [1/2/3/4/0]: {RESET}").strip()
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
                shopee_core.reset_credentials()
                return
            elif choice in ("0", "q", "exit"):
                print("Sampai jumpa!")
                return
            else:
                print("❌ Pilihan tidak valid, silakan ketik 1, 2, 3, 4, atau 0.")

    # Tentukan sumber username
    if not input_file:
        print(f"\n{CYAN}{BOLD}--- SUMBER DAFTAR USERNAME ---{RESET}")
        print(" [1] ✍️  Masukkan manual lewat layar ini")
        print(" [2] 📄 Baca dari file teks (contoh: daftar_username.txt / food.txt)")
        src = input(f"{WHITE}Pilih sumber [1/2] (Default 1): {RESET}").strip()
        if src == "2":
            input_file = input("Nama / path file teks: ").strip()

    usernames = shopee_core.read_usernames(input_file)
    print(f"✅ Ditemukan {len(usernames)} username unik yang akan diproses.")

    # Buat client dan koneksi Telegram
    client = shopee_core.create_client()
    try:
        await shopee_core.start_client(client)
        print(f"{GREEN}✅ Terhubung ke Telegram!{RESET}")

        if selected_mode == "misi":
            await run_misi_mode(client, usernames)
        elif selected_mode == "food":
            await run_food_mode(client, usernames)
        elif selected_mode == "both":
            await run_both_mode(client, usernames)
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\n\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\n❌ Terjadi kesalahan: {exc}")
