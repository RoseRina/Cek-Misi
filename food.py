#!/usr/bin/env python3
"""Shopee Food Voucher Bulk Checker (Diskon 25RB & Ongkir 12RB).

Bagian dari kesatuan Shopee Tools Bot Automation (@shp_tools_bot).
Dapat dijalankan langsung dengan:
    python food.py
Atau dengan file daftar tertentu:
    python food.py food.txt
"""

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
    # Menentukan file target akun
    target_file = None
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
    elif Path("food.txt").is_file():
        target_file = "food.txt"
    elif Path("daftar_username.txt").is_file():
        target_file = "daftar_username.txt"

    usernames = shopee_core.read_usernames(target_file)
    total = len(usernames)

    # Inisialisasi Telegram Client Terpadu
    client = shopee_core.create_client()
    try:
        await shopee_core.start_client(client)
    except Exception as exc:
        print(f"{RED}Gagal login Telegram: {exc}{RESET}")
        return

    # Banner Header
    banner_text = (
        "[bold cyan]🚀 NP VOUCHER BULK CHECKER[/bold cyan]\n"
        "[cyan]Auto-checking 25k & 12k Food Vouchers via @shp_tools_bot[/cyan]\n"
        f"[cyan]Total Target: [bold white]{total} Akun[/bold white][/cyan]"
    )

    if USE_RICH:
        console.print(Panel(banner_text, border_style="cyan", expand=False))
        console.print(f"\n[bold yellow]Memulai pengecekan untuk {total} akun...[/bold yellow]\n")
    else:
        print(f"\n{CYAN}{BOLD}=== SHOPEE FOOD VOUCHER CHECKER (25K & 12K) ==={RESET}")
        print(f"Total Target: {total} akun\n")

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
                        console.print(f"[bold red]FloodWait {exc.seconds}s. Antrean dihentikan demi keamanan.[/bold red]")
                        break

                    progress.advance(task)
                    if i < total:
                        await asyncio.sleep(shopee_core.STEP_DELAY)
        else:
            for i, acc in enumerate(usernames, 1):
                try:
                    is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, acc)
                    shopee_core.save_food_result(acc, is_valid, status, detail, has_25k, has_12k)

                    if is_valid:
                        print(f"  [{i}/{total}] {acc:<15} : {GREEN}{BOLD}MEMENUHI SYARAT{RESET}")
                        valid_accounts_list.append(acc)
                        valid_count += 1
                    else:
                        print(f"  [{i}/{total}] {acc:<15} : {YELLOW}{status}{RESET} ({detail})")
                        invalid_count += 1
                except FloodWaitError as exc:
                    print(f"{RED}FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}")
                    break

                if i < total:
                    await asyncio.sleep(shopee_core.STEP_DELAY)

    finally:
        await client.disconnect()

    # Rekapitulasi Akhir
    valid_list_str = "\n".join([f"    ┗ {acc}" for acc in valid_accounts_list]) if valid_accounts_list else "    ┗ (Tidak ada)"
    recap_text = f"""
[bold cyan]🎯 Total Target     : {total}[/bold cyan]
[bold green]✅ Memenuhi Syarat  : {valid_count}[/bold green]
[bold yellow]⚠️ Tidak Memenuhi   : {invalid_count}[/bold yellow]

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
        print(f"🎯 Total Target    : {total}")
        print(f"✅ Memenuhi Syarat : {valid_count}")
        print(f"⚠️ Tidak Memenuhi  : {invalid_count}")
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
