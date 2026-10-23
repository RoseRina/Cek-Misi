#!/usr/bin/env python3
"""Web Checker Adapter for Shopee Tools (@shp_tools_bot).

Menyediakan fungsi pengecekan asinkron terisolasi untuk Web API & WebSocket,
mendukung multi-sesi pengguna secara simultan.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import re
from typing import Optional, Dict, Any, Tuple

from telethon import TelegramClient
from telethon.errors import FloodWaitError

from shopee_core import (
    TARGET_BOT,
    BUTTON_TIMEOUT,
    RESULT_TIMEOUT,
    POLL_INTERVAL,
    detect_bot_error,
    parse_qris_result,
    validate_voucher_html,
    parse_raw_usernames,
    wait_for_button,
)


async def check_qris_mission(
    client: TelegramClient,
    username: str,
    step_delay: float = 2.5,
) -> Dict[str, Any]:
    """Pengecekan Misi Bayar QRIS untuk 1 akun."""
    try:
        previous = await client.get_messages(TARGET_BOT, limit=1)
        start_id = previous[0].id if previous else 0
        command = await client.send_message(TARGET_BOT, "/mission")
        start_id = max(start_id, command.id)
        await asyncio.sleep(step_delay)

        # 1. Klik menu Checkin
        checkin = await wait_for_button(
            client,
            start_id,
            lambda label: any(x in label for x in ("checkin", "check-in", "check in")),
            BUTTON_TIMEOUT,
        )
        if not checkin:
            return {
                "success": False,
                "status": "GAGAL",
                "detail": "Tombol Misi Check-in tidak ditemukan",
                "coins": None,
            }
        message, row_idx, col_idx, _ = checkin
        await message.click(row_idx, col_idx)
        start_id = message.id
        await asyncio.sleep(step_delay)

        # 2. Klik pilihan Username / Email / ID
        login_opt = await wait_for_button(
            client,
            start_id - 1,
            lambda label: any(term in label for term in ("username", "email", "user id", "id akun"))
            and "cookie" not in label,
            BUTTON_TIMEOUT,
        )
        if not login_opt:
            return {
                "success": False,
                "status": "GAGAL",
                "detail": "Tombol Username/Email/ID tidak ditemukan",
                "coins": None,
            }
        message, row_idx, col_idx, _ = login_opt
        await message.click(row_idx, col_idx)
        await asyncio.sleep(step_delay)

        # 3. Kirim username
        sent_msg = await client.send_message(TARGET_BOT, username)
        last_seen = {}
        deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
        while asyncio.get_running_loop().time() < deadline:
            messages = await client.get_messages(TARGET_BOT, limit=15)
            for msg in sorted((m for m in messages if m.id > sent_msg.id), key=lambda m: m.id):
                text = (msg.text or "").strip()
                if not text or last_seen.get(msg.id) == text:
                    continue
                last_seen[msg.id] = text

                err = detect_bot_error(text)
                if err:
                    return {
                        "success": False,
                        "status": err,
                        "detail": text,
                        "coins": None,
                    }

                result = parse_qris_result(text)
                if result:
                    coins, status, detail = result
                    return {
                        "success": True,
                        "status": status,
                        "detail": detail,
                        "coins": coins,
                    }
            await asyncio.sleep(POLL_INTERVAL)

        return {
            "success": False,
            "status": "TIMEOUT",
            "detail": "Timeout menunggu balasan bot Shopee",
            "coins": None,
        }
    except FloodWaitError as e:
        return {
            "success": False,
            "status": "FLOOD_WAIT",
            "detail": f"Terkena FloodWait Telegram selama {e.seconds} detik",
            "coins": None,
            "wait_seconds": e.seconds,
        }
    except Exception as e:
        return {
            "success": False,
            "status": "ERROR",
            "detail": f"Kesalahan sistem: {str(e)}",
            "coins": None,
        }


async def check_food_voucher(
    client: TelegramClient,
    username: str,
    download_dir: Path,
    step_delay: float = 2.5,
) -> Dict[str, Any]:
    """Pengecekan Voucher Shopee Food (25RB & 12RB) untuk 1 akun."""
    try:
        download_dir.mkdir(parents=True, exist_ok=True)
        previous = await client.get_messages(TARGET_BOT, limit=1)
        start_id = previous[0].id if previous else 0

        # 1. Kirim /account
        command = await client.send_message(TARGET_BOT, "/account")
        start_id = max(start_id, command.id)
        await asyncio.sleep(step_delay)

        # 2. Klik tombol "Check Voucher"
        btn_voucher = await wait_for_button(
            client,
            start_id,
            lambda label: "check voucher" in label or "voucher" in label,
            BUTTON_TIMEOUT,
        )
        if not btn_voucher:
            return {
                "success": False,
                "is_valid": False,
                "status": "GAGAL",
                "detail": "Tombol Check Voucher tidak ditemukan",
                "has_25k": False,
                "has_12k": False,
            }
        message, row_idx, col_idx, _ = btn_voucher
        await message.click(row_idx, col_idx)
        start_id = message.id
        await asyncio.sleep(step_delay)

        # 3. Klik tombol Email/Username/ID
        btn_login = await wait_for_button(
            client,
            start_id - 1,
            lambda label: any(term in label for term in ("username", "email", "id")) and "cookie" not in label,
            BUTTON_TIMEOUT,
        )
        if not btn_login:
            return {
                "success": False,
                "is_valid": False,
                "status": "GAGAL",
                "detail": "Tombol Username/Email/ID tidak ditemukan",
                "has_25k": False,
                "has_12k": False,
            }
        message, row_idx, col_idx, _ = btn_login
        await message.click(row_idx, col_idx)
        await asyncio.sleep(step_delay)

        # 4. Kirim username
        sent_msg = await client.send_message(TARGET_BOT, username)

        # 5. Tunggu dokumen HTML
        deadline = asyncio.get_running_loop().time() + RESULT_TIMEOUT
        # Sanitasi nama file untuk mencegah directory traversal
        safe_username = re.sub(r"[^a-zA-Z0-9_\-]", "_", username)[:64] or "user"
        html_path = download_dir / f"{safe_username}.html"
        file_received = False

        while asyncio.get_running_loop().time() < deadline:
            messages = await client.get_messages(TARGET_BOT, limit=8)
            for msg in sorted((m for m in messages if m.id > sent_msg.id), key=lambda m: m.id):
                text = (msg.text or "").strip()
                err = detect_bot_error(text)
                if err:
                    return {
                        "success": False,
                        "is_valid": False,
                        "status": err,
                        "detail": text,
                        "has_25k": False,
                        "has_12k": False,
                    }

                if msg.document:
                    for attr in msg.document.attributes:
                        fname = getattr(attr, "file_name", "") or ""
                        if fname.casefold().endswith(".html"):
                            await msg.download_media(str(html_path))
                            file_received = True
                            break
                if file_received:
                    break
            if file_received:
                break
            await asyncio.sleep(POLL_INTERVAL)

        if not file_received or not html_path.exists():
            return {
                "success": False,
                "is_valid": False,
                "status": "TIMEOUT",
                "detail": "Tidak menerima file HTML voucher dari bot",
                "has_25k": False,
                "has_12k": False,
            }

        # 6. Validasi file HTML lalu langsung hapus file dari server (privasi aman)
        has_25k, has_12k = validate_voucher_html(html_path)
        try:
            html_path.unlink(missing_ok=True)
        except Exception:
            pass

        if has_25k and has_12k:
            status = "MEMENUHI SYARAT"
            detail = "Lengkap: Diskon 25RB & Ongkir 12RB"
            is_valid = True
        elif has_25k:
            status = "PARSIAL"
            detail = "Hanya Diskon 25RB (Ongkir 12RB tidak ada)"
            is_valid = False
        elif has_12k:
            status = "PARSIAL"
            detail = "Hanya Ongkir 12RB (Diskon 25RB tidak ada)"
            is_valid = False
        else:
            status = "TIDAK MEMENUHI"
            detail = "Tidak ditemukan voucher 25RB maupun 12RB"
            is_valid = False

        return {
            "success": True,
            "is_valid": is_valid,
            "status": status,
            "detail": detail,
            "has_25k": has_25k,
            "has_12k": has_12k,
        }
    except FloodWaitError as e:
        return {
            "success": False,
            "is_valid": False,
            "status": "FLOOD_WAIT",
            "detail": f"Terkena FloodWait Telegram selama {e.seconds} detik",
            "has_25k": False,
            "has_12k": False,
            "wait_seconds": e.seconds,
        }
    except Exception as e:
        return {
            "success": False,
            "is_valid": False,
            "status": "ERROR",
            "detail": f"Kesalahan sistem: {str(e)}",
            "has_25k": False,
            "has_12k": False,
        }


async def check_user_combined(
    client: TelegramClient,
    username: str,
    mode: str,
    download_dir: Path,
    step_delay: float = 2.5,
) -> Dict[str, Any]:
    """Menjalankan pengecekan sesuai mode yang dipilih (misi, food, atau both)."""
    result: Dict[str, Any] = {
        "username": username,
        "mode": mode,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "qris": None,
        "food": None,
        "summary_status": "MEMPROSES",
        "is_valid": False,
    }

    if mode in ("misi", "both"):
        qris_res = await check_qris_mission(client, username, step_delay=step_delay)
        result["qris"] = qris_res
        if mode == "misi":
            result["summary_status"] = qris_res["status"]
            result["is_valid"] = qris_res.get("status") == "SELESAI"

    if mode in ("food", "both"):
        # Berikan jeda sejenak jika sebelumnya menjalankan misi
        if mode == "both":
            await asyncio.sleep(step_delay)
        food_res = await check_food_voucher(client, username, download_dir, step_delay=step_delay)
        result["food"] = food_res
        if mode == "food":
            result["summary_status"] = food_res["status"]
            result["is_valid"] = food_res.get("is_valid", False)

    if mode == "both":
        qris_status = result["qris"]["status"] if result["qris"] else "N/A"
        food_status = result["food"]["status"] if result["food"] else "N/A"
        food_valid = result["food"].get("is_valid", False) if result["food"] else False
        qris_ok = qris_status == "SELESAI"

        result["is_valid"] = food_valid or qris_ok
        result["summary_status"] = f"QRIS: {qris_status} | Food: {food_status}"

    return result
