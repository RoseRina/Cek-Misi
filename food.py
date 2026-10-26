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
    reused_records = []
    recheck_targets = set()
    preserved_records = []

    if args.single:
        usernames = [args.single.strip()]
    elif args.file:
        usernames = shopee_core.read_usernames(args.file)
        if len(usernames) > 1 and not args.resume:
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                usernames, "food", "otp"
            )
            if action == "finish":
                shopee_core.print_combined_execution_summary(
                    mode="food",
                    total_all=len(reused),
                    total_processed=0,
                    new_success=0,
                    new_fail=0,
                    new_error=0,
                    reused_records=reused,
                    preserved_records=[],
                    auth_method="otp",
                )
                return
            usernames = to_proc
            reused_records = reused
            recheck_targets = recheck
    else:
        while True:
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
                break
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

                if not usernames:
                    print("❌ Tidak ada akun yang dimuat.")
                    return

                if len(usernames) > 1 and not args.resume:
                    action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                        usernames, "food", "otp"
                    )
                    if action == "back":
                        continue
                    elif action == "finish":
                        shopee_core.print_combined_execution_summary(
                            mode="food",
                            total_all=len(reused),
                            total_processed=0,
                            new_success=0,
                            new_fail=0,
                            new_error=0,
                            reused_records=reused,
                            preserved_records=[],
                            auth_method="otp",
                        )
                        return
                    usernames = to_proc
                    reused_records = reused
                    recheck_targets = recheck
                break

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

    processed_count = 0
    valid_count = 0
    invalid_count = 0
    partial_count = 0
    error_count = 0
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
                        if acc in recheck_targets and not is_valid and status in ("TIMEOUT", "ERROR"):
                            old_rec = next((r for r in shopee_core.get_checked_accounts_records("food") if r.get("account") == acc), None)
                            if old_rec:
                                preserved_records.append({**old_rec, "reason": f"cek ulang {status.lower()}"})
                                console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold yellow]{status} (hasil sukses lama dipertahankan)[/bold yellow]")
                                processed_count += 1
                                progress.advance(task)
                                if i < total:
                                    await asyncio.sleep(args.delay)
                                continue
                        shopee_core.save_food_result(acc, is_valid, status, detail, has_25k, has_12k)

                        category = shopee_core.classify_food_status(is_valid, status)
                        if category == "VALID":
                            console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold green]MEMENUHI SYARAT[/bold green]")
                            valid_accounts_list.append(acc)
                            valid_count += 1
                        elif category == "PARSIAL":
                            console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold yellow]{status}[/bold yellow] ({detail})")
                            partial_count += 1
                        elif category == "ERROR":
                            console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold red]{status}[/bold red] ({detail})")
                            error_count += 1
                        else:  # INVALID
                            console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold yellow]{status}[/bold yellow] ({detail})")
                            invalid_count += 1
                    except FloodWaitError as exc:
                        msg = f"Telegram meminta jeda {exc.seconds} detik. Antrean dihentikan."
                        shopee_core.save_food_result(acc, False, "FLOOD_WAIT", msg, False, False)
                        processed_count += 1
                        error_count += 1
                        console.print(f"[bold red]⚠️ FloodWait {exc.seconds}s. Antrean dihentikan demi keamanan.[/bold red]")
                        break
                    except Exception as exc:
                        if acc in recheck_targets:
                            old_rec = next((r for r in shopee_core.get_checked_accounts_records("food") if r.get("account") == acc), None)
                            if old_rec:
                                preserved_records.append({**old_rec, "reason": "cek ulang error"})
                                console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold yellow]ERROR (hasil sukses lama dipertahankan)[/bold yellow]")
                                processed_count += 1
                                progress.advance(task)
                                if i < total:
                                    await asyncio.sleep(args.delay)
                                continue
                        shopee_core.save_food_result(acc, False, "ERROR", str(exc), False, False)
                        console.print(f"  [cyan][{i}/{total}][/cyan] ➔ [bold white]{acc:<15}[/bold white] : [bold red]ERROR[/bold red] ({exc})")
                        processed_count += 1
                        error_count += 1

                    progress.advance(task)
                    if i < total:
                        await asyncio.sleep(args.delay)
        else:
            for i, acc in enumerate(usernames, 1):
                bar = shopee_core.render_progress_bar(i, total)
                try:
                    is_valid, status, detail, has_25k, has_12k = await shopee_core.check_one_food(client, acc)
                    if acc in recheck_targets and not is_valid and status in ("TIMEOUT", "ERROR"):
                        old_rec = next((r for r in shopee_core.get_checked_accounts_records("food") if r.get("account") == acc), None)
                        if old_rec:
                            preserved_records.append({**old_rec, "reason": f"cek ulang {status.lower()}"})
                            print(f"  {bar} {acc:<15} : {YELLOW}{status} (hasil sukses lama dipertahankan){RESET}")
                            processed_count += 1
                            if i < total:
                                await asyncio.sleep(args.delay)
                            continue
                    shopee_core.save_food_result(acc, is_valid, status, detail, has_25k, has_12k)

                    category = shopee_core.classify_food_status(is_valid, status)
                    if category == "VALID":
                        print(f"  {bar} {acc:<15} : {GREEN}{BOLD}MEMENUHI SYARAT{RESET}")
                        valid_accounts_list.append(acc)
                        valid_count += 1
                    elif category == "PARSIAL":
                        print(f"  {bar} {acc:<15} : {YELLOW}{status}{RESET} ({detail})")
                        partial_count += 1
                    elif category == "ERROR":
                        print(f"  {bar} {acc:<15} : {RED}{status}{RESET} ({detail})")
                        error_count += 1
                    else:  # INVALID
                        print(f"  {bar} {acc:<15} : {YELLOW}{status}{RESET} ({detail})")
                        invalid_count += 1
                except FloodWaitError as exc:
                    msg = f"Telegram meminta jeda {exc.seconds} detik. Antrean dihentikan."
                    shopee_core.save_food_result(acc, False, "FLOOD_WAIT", msg, False, False)
                    processed_count += 1
                    error_count += 1
                    print(f"{RED}⚠️ FloodWait {exc.seconds}s. Antrean dihentikan.{RESET}")
                    break
                except Exception as exc:
                    if acc in recheck_targets:
                        old_rec = next((r for r in shopee_core.get_checked_accounts_records("food") if r.get("account") == acc), None)
                        if old_rec:
                            preserved_records.append({**old_rec, "reason": "cek ulang error"})
                            print(f"  {bar} {acc:<15} : {YELLOW}ERROR (hasil sukses lama dipertahankan){RESET}")
                            processed_count += 1
                            if i < total:
                                await asyncio.sleep(args.delay)
                            continue
                    shopee_core.save_food_result(acc, False, "ERROR", str(exc), False, False)
                    print(f"  {bar} {acc:<15} : {RED}ERROR ({exc}){RESET}")
                    processed_count += 1
                    error_count += 1

                if i < total:
                    await asyncio.sleep(args.delay)

    finally:
        await client.disconnect()

    # Rekapitulasi Akhir Berbingkai Rapi (Kompatibel Termux)
    shopee_core.print_food_summary_report(
        total_processed=processed_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        valid_accounts=valid_accounts_list,
        partial_count=partial_count,
        error_count=error_count,
        show_csv_path=False,
    )
    if reused_records or preserved_records:
        shopee_core.print_combined_execution_summary(
            mode="food",
            total_all=len(usernames) + len(reused_records) + len(preserved_records),
            total_processed=processed_count,
            new_success=valid_count,
            new_fail=invalid_count + partial_count,
            new_error=error_count,
            reused_records=reused_records,
            preserved_records=preserved_records,
            auth_method="otp",
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\nTerjadi kesalahan: {exc}")
