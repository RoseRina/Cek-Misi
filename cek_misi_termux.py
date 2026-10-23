#!/usr/bin/env python3
"""Standalone Cek Misi (Bayar QRIS) client for Android Termux.

Install in Termux with:
    pkg install python
    python -m pip install telethon

Run interactively:
    python cek_misi_termux.py

Or provide a UTF-8 text file with one Shopee username per line:
    python cek_misi_termux.py daftar_username.txt

The script signs in to Telegram using your own API ID and API Hash. The
Telethon session is stored in ./cek_misi_termux.session. Results are appended
to ./hasil_cek_misi.csv.
"""

import asyncio
import csv
from datetime import datetime
import getpass
import re
import sys
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError


TARGET_BOT = "@shp_tools_bot"
SESSION_NAME = "cek_misi_termux"
RESULTS_FILE = Path("hasil_cek_misi.csv")
STEP_DELAY = 3.0
POLL_INTERVAL = 0.5
MISSION_BUTTON_TIMEOUT = 15
RESULT_TIMEOUT = 30


def read_usernames():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1]).expanduser()
        if not path.is_file():
            raise ValueError(f"File daftar tidak ditemukan: {path}")
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    else:
        print("Masukkan username Shopee, satu per baris. Tekan Enter pada baris kosong untuk mulai:")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if not line.strip():
                break
            lines.append(line)

    usernames = []
    seen = set()
    for line in lines:
        username = line.strip()
        if username and not username.startswith("#") and username not in seen:
            usernames.append(username)
            seen.add(username)
    if not usernames:
        raise ValueError("Daftar username kosong.")
    return usernames


def save_result(username, coins, status, detail):
    file_exists = RESULTS_FILE.exists() and RESULTS_FILE.stat().st_size > 0
    with RESULTS_FILE.open("a", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        if not file_exists:
            writer.writerow(["Tanggal & Waktu", "Username", "Koin Bayar QRIS", "Status", "Keterangan"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            username,
            coins if coins is not None else "-",
            status,
            detail or "-",
        ])


def error_status(text):
    normalized = " ".join((text or "").casefold().split())
    if "akun ini sedang dibatasi" in normalized and "banned" in normalized:
        return "GAGAL"
    if "akun tidak ditemukan" in normalized:
        return "AKUN TIDAK DITEMUKAN"
    if "cookie tidak valid" in normalized:
        return "GAGAL"
    if "akun ini bukan milikmu" in normalized:
        return "GAGAL"
    return None


def parse_qris_result(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    qris_lines = [line for line in lines if "bayar qris" in line.casefold()]
    if not qris_lines:
        return None
    line = qris_lines[0]
    matches = re.findall(r"(?<!\d)([\d.,\s]+)\s*koin\b", line, re.IGNORECASE)
    amount = None
    for raw_amount in matches:
        digits = re.sub(r"\D", "", raw_amount)
        if digits:
            amount = int(digits)
            break
    if amount is None:
        return None
    status = "BELUM SELESAI" if "belum" in line.casefold() else "SELESAI"
    return amount, status, line


async def wait_for_button(client, after_id, matches, timeout):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=10)
        candidates = sorted(
            (message for message in messages if message.id > after_id and message.buttons),
            key=lambda message: message.id,
        )
        for message in candidates:
            for row_index, row in enumerate(message.buttons):
                for column_index, button in enumerate(row):
                    label = (button.text or "").casefold()
                    if matches(label):
                        return message, row_index, column_index, button.text
        await asyncio.sleep(POLL_INTERVAL)
    return None


async def check_one_mission(client, username):
    previous = await client.get_messages(TARGET_BOT, limit=1)
    start_id = previous[0].id if previous else 0
    command = await client.send_message(TARGET_BOT, "/mission")
    start_id = max(start_id, command.id)
    await asyncio.sleep(STEP_DELAY)

    checkin = await wait_for_button(
        client,
        start_id,
        lambda label: "checkin" in label or "check-in" in label or "check in" in label,
        MISSION_BUTTON_TIMEOUT,
    )
    if not checkin:
        return None, "GAGAL", "Pilihan Misi Checkin tidak ditemukan"
    message, row_index, column_index, label = checkin
    print(f"  Memilih misi: {label}")
    await message.click(row_index, column_index)
    start_id = message.id
    await asyncio.sleep(STEP_DELAY)

    login_option = await wait_for_button(
        client,
        start_id - 1,
        lambda label: any(term in label for term in ("username", "email", "user id", "id akun"))
        and "cookie" not in label,
        MISSION_BUTTON_TIMEOUT,
    )
    if not login_option:
        return None, "GAGAL", "Opsi Username / Email / ID tidak ditemukan"
    message, row_index, column_index, label = login_option
    print(f"  Memilih login: {label}")
    await message.click(row_index, column_index)
    await asyncio.sleep(STEP_DELAY)

    sent_user = await client.send_message(TARGET_BOT, username)
    last_seen = {}
    deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(TARGET_BOT, limit=15)
        for message in sorted((item for item in messages if item.id > sent_user.id), key=lambda item: item.id):
            text = (message.text or "").strip()
            if not text or last_seen.get(message.id) == text:
                continue
            last_seen[message.id] = text
            status = error_status(text)
            if status:
                return None, status, text
            result = parse_qris_result(text)
            if result:
                return result
        await asyncio.sleep(POLL_INTERVAL)
    return None, "GAGAL", "Timeout menunggu hasil Misi Checkin / Bayar QRIS"


async def main():
    usernames = read_usernames()
    try:
        api_id = int(input("API_ID Telegram: ").strip())
    except ValueError as exc:
        raise ValueError("API_ID harus berupa angka.") from exc
    if api_id <= 0:
        raise ValueError("API_ID harus angka positif.")
    api_hash = getpass.getpass("API_HASH Telegram: ").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", api_hash):
        raise ValueError("API_HASH harus berisi 32 karakter heksadesimal.")

    client = TelegramClient(SESSION_NAME, api_id, api_hash)
    try:
        await client.start(
            phone=lambda: input("Nomor telepon Telegram (format +62...): ").strip(),
            code_callback=lambda: input("Kode login Telegram: ").strip(),
            password=lambda: getpass.getpass("Password verifikasi dua langkah: "),
        )
        print(f"\nLogin Telegram berhasil. Memeriksa {len(usernames)} username. Hasil: {RESULTS_FILE.resolve()}\n")
        for index, username in enumerate(usernames, start=1):
            print(f"[{index}/{len(usernames)}] {username}")
            try:
                coins, status, detail = await check_one_mission(client, username)
                save_result(username, coins, status, detail)
                if coins is None:
                    print(f"  {status}: {detail}\n")
                else:
                    print(f"  Bayar QRIS: {coins:,} koin | {status}\n")
            except FloodWaitError as exc:
                save_result(username, None, "GAGAL", f"Telegram meminta jeda {exc.seconds} detik; antrean dihentikan.")
                print(f"  Flood wait {exc.seconds} detik. Antrean dihentikan agar tidak mengulang langkah yang belum pasti.")
                break
            except Exception as exc:
                save_result(username, None, "GAGAL", f"Error: {exc}")
                print(f"  GAGAL: {exc}\n")
            if index < len(usernames):
                await asyncio.sleep(STEP_DELAY)
        print("Selesai.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nDihentikan.")
    except Exception as exc:
        print(f"\nTidak dapat menjalankan Cek Misi: {exc}")
