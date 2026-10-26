#!/usr/bin/env python3
"""Unit test untuk verifikasi investigasi dan perbaikan bug live TIMEOUT mode Misi di Cek-Misi (CLI).

Kasus uji:
1. parse_qris_result() dengan teks persis daftar Misi Checkin dari live run
   (Bayar QRIS 10.000 koin — belum selesai) -> BELUM SELESAI, koin 10000, bukan None.
2. check_one_mission() dengan urutan mock bot:
   /mission -> button checkin -> button login -> prompt email -> kirim username ->
   Message 1: "✅ Login: dummy_user (User ID: 12345)" ->
   Message 2: "Misi Checkin" lengkap ->
   harus selesai sebagai BELUM SELESAI, bukan TIMEOUT, dan tidak berhenti di pesan "Login:".
3. Pesan loading/perantara (misal ⏳ Sedang memproses...) diikuti Misi Checkin ->
   tetap selesai sebagai BELUM SELESAI (perantara tidak merusak alur).
4. Tidak ada balasan sama sekali dari bot sampai timeout ->
   tetap mengembalikan TIMEOUT (tidak berubah menjadi hasil palsu).
5. Baris QRIS dengan status SELESAI dan SUDAH DICLAIM tetap berfungsi seperti semula.
6. Log diagnostik aman (debug=True):
   mencatat log kandidat polling tanpa mengekspos kredensial/token/cookie mentah.
"""

import asyncio
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock

import shopee_core


class MockButton:
    def __init__(self, text: str, on_click=None):
        self.text = text
        self.clicked = False
        self.on_click = on_click

    async def click(self):
        self.clicked = True
        if self.on_click:
            res = self.on_click()
            if asyncio.iscoroutine(res):
                await res


class MockMessage:
    def __init__(self, msg_id: int, text: str = "", buttons=None, out: bool = False):
        self.id = msg_id
        self.text = text
        self.raw_text = text
        self.buttons = buttons or []
        self.out = out

    async def click(self, row_idx: int, col_idx: int):
        if self.buttons and row_idx < len(self.buttons):
            row = self.buttons[row_idx]
            if col_idx < len(row):
                btn = row[col_idx]
                if hasattr(btn, "click") and callable(btn.click):
                    await btn.click()


class TestMisiLiveFix(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Percepat timeout selama pengujian
        self.patch_btn_timeout = patch.object(shopee_core, "BUTTON_TIMEOUT", 0.5)
        self.patch_res_timeout = patch.object(shopee_core, "RESULT_TIMEOUT", 0.8)
        self.patch_step_delay = patch.object(shopee_core, "STEP_DELAY", 0.0)
        self.patch_poll_interval = patch.object(shopee_core, "POLL_INTERVAL", 0.05)

        self.patch_btn_timeout.start()
        self.patch_res_timeout.start()
        self.patch_step_delay.start()
        self.patch_poll_interval.start()

    def tearDown(self):
        self.patch_btn_timeout.stop()
        self.patch_res_timeout.stop()
        self.patch_step_delay.stop()
        self.patch_poll_interval.stop()

    def test_01_parse_qris_result_exact_live_format(self):
        """1. parse_qris_result() dengan teks persis format daftar Misi Checkin dari bot:
        Bayar QRIS (Min. 15RB) (10.000 koin) — belum selesai
        Harus mengembalikan: (10000, 'BELUM SELESAI', 'Bayar QRIS (Min. 15RB) (10.000 koin) — belum selesai')
        """
        exact_bot_reply = (
            "🎯 Misi Checkin\n"
            "Install ShopeePay — belum muncul / sudah diclaim\n"
            "Isi Saldo 10RB (Gratis Admin) — belum muncul / sudah diclaim\n"
            "Bayar QRIS (Min. 15RB) (10.000 koin) — belum selesai\n"
            "Isi Saldo 100RB (Misi ShopeePay) — belum muncul"
        )
        result = shopee_core.parse_qris_result(exact_bot_reply, has_finished_button=True)
        self.assertIsNotNone(result)
        amount, status, detail = result
        self.assertEqual(amount, 10000)
        self.assertEqual(status, "BELUM SELESAI")
        self.assertIn("Bayar QRIS", detail)
        self.assertIn("10.000 koin", detail)
        self.assertIn("belum selesai", detail)

    async def test_02_check_one_mission_with_login_acknowledgment_and_full_mission(self):
        """2. check_one_mission() dengan urutan pesan mock:
        perintah -> prompt email -> kirim username -> "Login:" -> "Misi Checkin" lengkap.
        Harus selesai sebagai BELUM SELESAI (10000 koin), bukan TIMEOUT, dan tidak boleh berhenti di pesan "Login:".
        """
        btn_checkin = MockButton("Misi Checkin")
        btn_user = MockButton("Email / Username / ID")
        btn_recheck = MockButton("Recheck Misi")

        curr_id = 500
        msgs = []

        async def fake_send_message(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs.append(sent)

            if text == "/mission":
                curr_id += 1
                msgs.append(MockMessage(curr_id, "Pilih misi:", buttons=[[btn_checkin]], out=False))
            elif text == "mock_user_live_01":
                # Bot mengirim 2 pesan berurutan:
                # 1. Konfirmasi Login
                curr_id += 1
                msgs.append(MockMessage(curr_id, "✅ Login: mock_user_live_01 (User ID: 99887766)", out=False))
                # 2. Daftar Misi Checkin lengkap
                curr_id += 1
                misi_text = (
                    "🎯 Misi Checkin\n"
                    "Install ShopeePay — belum muncul / sudah diclaim\n"
                    "Isi Saldo 10RB (Gratis Admin) — belum muncul / sudah diclaim\n"
                    "Bayar QRIS (Min. 15RB) (10.000 koin) — belum selesai\n"
                    "Isi Saldo 100RB (Misi ShopeePay) — belum muncul"
                )
                msgs.append(MockMessage(curr_id, misi_text, buttons=[[btn_recheck]], out=False))

            return sent

        async def fake_get_messages(target, limit=15):
            return sorted(msgs, key=lambda m: m.id, reverse=True)[:limit]

        btn_checkin.on_click = lambda: msgs.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs.append(MockMessage(curr_id + 2, "Masukkan email / username / user id:"))

        client = MagicMock()
        client.send_message = fake_send_message
        client.get_messages = fake_get_messages

        coins, status, detail = await shopee_core.check_one_mission(
            client, "mock_user_live_01", auth_method="username"
        )
        self.assertEqual(coins, 10000)
        self.assertEqual(status, "BELUM SELESAI")
        self.assertIn("10.000 koin", detail)
        self.assertNotIn("TIMEOUT", status)

    async def test_03_loading_intermediate_followed_by_mission(self):
        """3. Pesan loading/perantara diikuti Misi Checkin ->
        tetap selesai sebagai BELUM SELESAI (perantara tidak merusak).
        """
        btn_checkin = MockButton("Misi Checkin")
        btn_user = MockButton("Email / Username / ID")
        btn_recheck = MockButton("Recheck Misi")

        curr_id = 600
        msgs = []

        async def fake_send_message(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs.append(sent)

            if text == "/mission":
                curr_id += 1
                msgs.append(MockMessage(curr_id, "Pilih misi:", buttons=[[btn_checkin]], out=False))
            elif text == "mock_user_intermediate":
                # Pesan proses/loading perantara
                curr_id += 1
                msgs.append(MockMessage(curr_id, "⏳ Sedang memproses misi checkin, mohon tunggu sebentar...", out=False))

                # Lalu pesan daftar misi lengkap
                curr_id += 1
                misi_text = (
                    "🎯 Misi Checkin\n"
                    "Bayar QRIS (Min. 15RB) (10.000 koin) — belum selesai"
                )
                msgs.append(MockMessage(curr_id, misi_text, buttons=[[btn_recheck]], out=False))

            return sent

        async def fake_get_messages(target, limit=15):
            return sorted(msgs, key=lambda m: m.id, reverse=True)[:limit]

        btn_checkin.on_click = lambda: msgs.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs.append(MockMessage(curr_id + 2, "Masukkan email / username / user id:"))

        client = MagicMock()
        client.send_message = fake_send_message
        client.get_messages = fake_get_messages

        coins, status, detail = await shopee_core.check_one_mission(
            client, "mock_user_intermediate", auth_method="username"
        )
        self.assertEqual(coins, 10000)
        self.assertEqual(status, "BELUM SELESAI")

    async def test_04_no_reply_until_timeout(self):
        """4. Tidak ada balasan sama sekali sampai timeout ->
        tetap TIMEOUT (kasus ini tidak boleh berubah jadi hasil palsu).
        """
        btn_checkin = MockButton("Misi Checkin")
        btn_user = MockButton("Email / Username / ID")

        curr_id = 700
        msgs = []

        async def fake_send_message(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs.append(sent)

            if text == "/mission":
                curr_id += 1
                msgs.append(MockMessage(curr_id, "Pilih misi:", buttons=[[btn_checkin]], out=False))
            # Setelah kirim username, bot tidak membalas sama sekali
            return sent

        async def fake_get_messages(target, limit=15):
            return sorted(msgs, key=lambda m: m.id, reverse=True)[:limit]

        btn_checkin.on_click = lambda: msgs.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs.append(MockMessage(curr_id + 2, "Masukkan email / username / user id:"))

        client = MagicMock()
        client.send_message = fake_send_message
        client.get_messages = fake_get_messages

        coins, status, detail = await shopee_core.check_one_mission(
            client, "mock_user_unresponsive", auth_method="username"
        )
        self.assertIsNone(coins)
        self.assertEqual(status, "TIMEOUT")
        self.assertIn("Timeout", detail)

    def test_05_qris_selesai_and_sudah_diclaim_preserved(self):
        """5. Baris QRIS SELESAI dan SUDAH DICLAIM tetap bekerja seperti semula."""
        text_selesai = (
            "🎯 Misi Checkin\n"
            "Bayar QRIS (Min. 15RB) (10.000 koin) — selesai\n"
        )
        amount_s, status_s, detail_s = shopee_core.parse_qris_result(text_selesai, has_finished_button=True)
        self.assertEqual(amount_s, 10000)
        self.assertEqual(status_s, "SELESAI")

        text_diclaim = (
            "🎯 Misi Checkin\n"
            "Bayar QRIS (Min. 15RB) (10.000 koin) — sudah diclaim\n"
        )
        amount_c, status_c, detail_c = shopee_core.parse_qris_result(text_diclaim, has_finished_button=True)
        self.assertEqual(amount_c, 10000)
        self.assertEqual(status_c, "SUDAH DICLAIM")

        text_diklaim_k = (
            "🎯 Misi Checkin\n"
            "Bayar QRIS (Min. 15RB) (10.000 koin) — sudah diklaim\n"
        )
        amount_k, status_k, detail_k = shopee_core.parse_qris_result(text_diklaim_k, has_finished_button=True)
        self.assertEqual(amount_k, 10000)
        self.assertEqual(status_k, "SUDAH DICLAIM")

    async def test_06_safe_diagnostic_logging_masks_credentials(self):
        """6. Saat debug=True di check_one_mission, log diagnostik aman tercetak tanpa mengekspos kredensial/token."""
        btn_checkin = MockButton("Misi Checkin")
        btn_cookie = MockButton("Raw Cookie")

        curr_id = 800
        msgs = []
        raw_cookie = "SPC_EC=super_secret_session_token_xyz987; SPC_U=12345678;"

        async def fake_send_message(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs.append(sent)
            if text == "/mission":
                curr_id += 1
                msgs.append(MockMessage(curr_id, "Pilih misi:", buttons=[[btn_checkin]], out=False))
            elif raw_cookie in text:
                curr_id += 1
                msgs.append(MockMessage(curr_id, f"✅ Login: {raw_cookie}", out=False))
                curr_id += 1
                msgs.append(MockMessage(curr_id, "🎯 Misi Checkin\nBayar QRIS (Min. 15RB) (5.000 koin) — belum selesai", out=False))
            return sent

        async def fake_get_messages(target, limit=15):
            return sorted(msgs, key=lambda m: m.id, reverse=True)[:limit]

        btn_checkin.on_click = lambda: msgs.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_cookie]]))
        btn_cookie.on_click = lambda: msgs.append(MockMessage(curr_id + 2, "Masukkan raw cookie:"))

        client = MagicMock()
        client.send_message = fake_send_message
        client.get_messages = fake_get_messages

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            coins, status, detail = await shopee_core.check_one_mission(
                client, raw_cookie, auth_method="cookie", debug=True
            )

        log_output = buf.getvalue()
        self.assertEqual(coins, 5000)
        self.assertEqual(status, "BELUM SELESAI")
        self.assertIn("[DEBUG-MISI]", log_output)
        # Pastikan token rahasia TIDAK pernah muncul dalam log diagnostik
        self.assertNotIn("super_secret_session_token_xyz987", log_output)


if __name__ == "__main__":
    unittest.main()
