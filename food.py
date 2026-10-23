#!/usr/bin/env python3
"""Shopee Food Voucher Checker (Diskon 25RB & Ongkir 12RB).

Mendukung Mode Satuan (1 Akun) dan Mode Massal / Bulk dengan Auto-Resume.

Contoh:
    python food.py
    python food.py food.txt
    python food.py --single user123
"""

import argparse
import asyncio
from pathlib import Path
import sys

from telethon.errors import FloodWaitError

import shopee_core

# Percantik UI dengan Rich / Colorama (Fallback jika modul belum terpasang)
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
    console = Console()
    USE_RICH = True
except ImportError:
    USE_RICH = False

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    CYAN = Fore.CYAN
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


async def main():
    parser = argparse.ArgumentParser(description="Shopee Food Voucher Checker (Diskon 25RB & Ongkir 12RB)")
    parser.add_argument("file", nargs="?", default=None, help="File daftar akun (misal: food.txt)")
    parser.add_argument("--single", help="Cek 1 akun secara langsung")
    parser.add_argument("--resume", action="store_true", help="Lewati akun yang sudah dicek sebelumnya")
    parser.add_argument("--delay", type=float, default=2.5, help="Jeda antar akun (detik, default: 2.5)")
    args = parser.parse_args()

    usernames = []
    if args.single:
        usernames = [args.single.strip()]
    elif args.file:
        usernames = shopee_core.read_usernames(args.file)
    else:
        # Tampilkan pilihan cerdas: auto-detect file di folder
        txt_files = shopee_core.get_available_txt_files()
        print(f"\n{CYAN}{BOLD}🍔 SHOPEE FOOD VOUCHER CHECKER (25K & 12K){RESET}")
        print(" [1] ⚡ Cek 1 Akun Cepat")
        print(" [2] 📦 Cek Massal / Bulk (Pilih File / Paste)")
        choice = input("Pilih mode [1/2] (Default 2): ").strip()

        if choice == "1":
            acc = input("Masukkan username Shopee: ").strip()
            if not acc:
                print("❌ Username tidak boleh kosong.")
                return
            usernames = [acc]
        else:
            if txt_files:
                print(f"\nDitemukan file akun di folder ini:")
                f_map = {}
                for idx, (p, count) in enumerate(txt_files, 1):
                    print(f"  [{idx}] 📄 {p.name} ({count} akun)")
                    f_map[str(idx)] = p
                print(f"  [{len(txt_files) + 1}] 📁 Ketik nama file lain")
                print(f"  [{len(txt_files) + 2}] ✍️  Paste langsung daftar akun")

                pick = input(f"Pilih sumber [1-{len(txt_files) + 2}]: ").strip()
                if pick in f_map:
                    usernames = shopee_core.read_usernames(f_map[pick])
                elif pick == str(len(txt_files) + 1):
                    fn = input("Nama file: ").strip()
                    usernames = shopee_core.read_usernames(fn)
                elif pick == str(len(txt_files) + 2):
                    usernames = shopee_core.read_usernames()
                else:
                    usernames = shopee_core.read_usernames(txt_files[0][0])
            else:
                usernames = shopee_core.read_usernames()

    # Fitur resume jika lebih dari 1 akun
    if len(usernames) > 1 and not args.resume and not args.single:
        ask_r = input("\nLewati akun yang sudah ada hasil suksesnya di CSV? (Y/n) [Default: Y]: ").strip().casefold()
        if ask_r in ("", "y", "ya", "yes"):
            args.resume = True

    if args.resume and len(usernames) > 1:
        to_proc, skipped = shopee_core.filter_unprocessed_usernames(usernames, "food")
        if skipped > 0:
            print(f"\n{GREEN}ℹ️ Fitur Resume: {skipped} akun sudah pernah dicek dan dilewati.{RESET}")
            print(f"👉 Tersisa {len(to_proc)} akun yang akan diproses sekarang.")
            usernames = to_proc
            if not usernames:
                print(f"{GREEN}🎉 Semua akun sudah selesai dicek sebelumnya! Tidak ada antrean.{RESET}")
                return

    total = len(usernames)
    if total == 0:
        print("❌ Tidak ada akun untuk diproses.")
        return

    # Inisialisasi Telegram Client Terpadu
    client = shopee_core.create_client()
    try:
        await shopee_core.start_client(client)
    except Exception as exc:
        print(f"{RED}Gagal login Telegram: {exc}{RESET}")
        return

    # Banner Header
    banner_text = (
        "[bold cyan]🚀 SHOPEE FOOD VOUCHER BULK CHECKER[/bold cyan]\n"
        "[cyan]Auto-checking 25k & 12k Food Vouchers via @shp_tools_bot[/cyan]\n"
        f"[cyan]Target Antrean: [bold white]{total} Akun[/bold white][/cyan]"
    )

    if USE_RICH:
        console.print(Panel(banner_text, border_style="cyan", expand=False))
        console.print(f"\n[bold yellow]Memulai pengecekan untuk {total} akun...[/bold yellow]\n")
    else:
        print(f"\n{CYAN}{BOLD}=== SHOPEE FOOD VOUCHER BULK CHECKER (25K & 12K) ==={RESET}")
        print(f"Target Antrean: {total} akun\n")

    valid_count = 0
    invalid_count = 0
    valid_accounts_list = []

    try:
        if USE_RICH:
            with Progress(
                SpinnerColumn(spinner_name="dots", style="cyan"),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=25, style="cyan", complete_style="green"),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Memeriksa akun...", total=total)

                for i, acc in enumerate(usernames, 1):
                    progress.update(task, description=f"[cyan]Memeriksa ({i}/{total}): [bold white]{acc}[/bold white]")

                    try:
                        is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, acc)
                        shopee_core.save_food_result(acc, is_valid, status, detail, has_25k, has_12k)

                        if is_valid:
                            console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold green]MEMENUHI SYARAT[/bold green]")
                            valid_accounts_list.append(acc)
                            valid_count += 1
                        else:
                            console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold yellow]{status}[/bold yellow] ({detail})")
                            invalid_count += 1
                    except FloodWaitError as exc:
                        console.print(f"[bold red]⚠️ FloodWait {exc.seconds}s. Antrean dihentikan demi keamanan.[/bold red]")
                        break

                    progress.advance(task)
                    if i < total:
                        await asyncio.sleep(args.delay)
        else:
            for i, acc in enumerate(usernames, 1):
                bar = shopee_core.render_progress_bar(i, total)
                try:
                    is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, acc)
                    shopee_core.save_food_result(acc, is_valid, status, detail, has_25k, has_12k)

                    if is_valid:
                        print(f"  {bar} {acc:<15} : {GREEN}{BOLD}MEMENUHI SYARAT{RESET}")
                        valid_accounts_list.append(acc)
                        valid_count += 1
                    else:
                        print(f"  {bar} {acc:<15} : {YELLOW}{status}{RESET} ({detail})")
                        invalid_count += 1
                except FloodWaitError as exc:
                    print(f"{RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}")
                    break

                if i < total:
                    await asyncio.sleep(args.delay)

    finally:
        await client.disconnect()

    # Rekapitulasi Akhir
    valid_list_str = "\n".join([f"    ┗ {acc}" for acc in valid_accounts_list]) if valid_accounts_list else "    ┗ (Tidak ada)"
    recap_text = f"""
[bold cyan]🎯 Total Diproses   : {total}[/bold cyan]
[bold green]✅ Memenuhi Syarat  : {valid_count}[/bold green]
[bold yellow]⚠️ Belum Memenuhi   : {invalid_count}[/bold yellow]

[bold yellow]★ DAFTAR AKUN MEMENUHI SYARAT ★[/bold yellow]
{valid_list_str}
    """

    if USE_RICH:
        console.print("\n")
        console.print(Panel(recap_text.strip(), title="[bold yellow]✨ LAPORAN HASIL CHECK VOUCHER ✨[/bold yellow]", border_style="green", expand=False))
        console.print(f"[bold cyan]📂 Akun valid disimpan di '{shopee_core.VALID_FOOD_FILE}'[/bold cyan]")
        console.print(f"[bold cyan]📂 Rincian CSV tersimpan di '{shopee_core.RESULTS_FOOD_FILE}'[/bold cyan]\n")
    else:
        print("\n" + "=" * 50)
        print("✨ LAPORAN HASIL CHECK VOUCHER ✨")
        print("=" * 50)
        print(f"🎯 Total Diproses  : {total}")
        print(f"✅ Memenuhi Syarat : {valid_count}")
        print(f"⚠️ Belum Memenuhi  : {invalid_count}")
        print("\n★ DAFTAR AKUN MEMENUHI SYARAT ★")
        print(valid_list_str)
        print(f"\n📂 Akun valid disimpan di '{shopee_core.VALID_FOOD_FILE}'")
        print(f"📂 Rincian CSV tersimpan di '{shopee_core.RESULTS_FOOD_FILE}'\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\nTerjadi kesalahan: {exc}")
