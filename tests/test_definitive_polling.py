#!/usr/bin/env python3
"""Unit tests komprehensif untuk pengujian polling balasan bot definitif di seluruh mode CLI Cek-Misi:
1. Ganti Nomor: Balasan '❌ Akun belum punya nomor HP...' -> GAGAL langsung, bukan TIMEOUT.
2. Ganti Nomor: Balasan ❌ definitif lain -> GAGAL, bukan TIMEOUT; tanpa balasan -> TIMEOUT; loading -> Password/PIN -> SUKSES; OTP -> GAGAL + Batal; Password/PIN -> SUKSES + Batal.
3. Misi: Balasan definitif non-QRIS (akun tidak ditemukan/belum terdaftar) -> GAGAL langsung; baris QRIS -> status dan koin akurat.
4. Food: Balasan teks negatif definitif tanpa file HTML -> GAGAL langsung, bukan TIMEOUT file; file HTML valid -> diproses normal; loading teks -> tetap menunggu file HTML.
5. Klaim: Balasan negatif definitif (kriteria, akun tidak ditemukan, cookie tidak valid, belum punya no HP, tanda ❌) -> GAGAL (bukan TIDAK DIKETAHUI); balasan tak dikenal -> tetap TIDAK DIKETAHUI; perantara diabaikan; timeout -> tetap terlabel.
6. Uji Lintas Akun: Pesan 'Dibatalkan.' dari akun sebelumnya tidak terbawa ke akun berikutnya.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

import shopee_core
import voucher_claim


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
    def __init__(self, msg_id: int, text: str = "", buttons=None, document=None, out: bool = False):
        self.id = msg_id
        self.text = text
        self.raw_text = text
        self.buttons = buttons or []
        self.document = document
        self.out = out

    async def click(self, row_idx: int, col_idx: int):
        if self.buttons and row_idx < len(self.buttons):
            row = self.buttons[row_idx]
            if col_idx < len(row):
                btn = row[col_idx]
                if hasattr(btn, "click") and callable(btn.click):
                    await btn.click()

    async def download_media(self, path):
        pass


class MockDocAttr:
    def __init__(self, file_name: str):
        self.file_name = file_name


class MockDoc:
    def __init__(self, file_name: str):
        self.attributes = [MockDocAttr(file_name)]


class TestDefinitivePollingAcrossModes(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Patch paths to temp dir
        self.patch_csv_gn = patch.object(shopee_core, "RESULTS_GANTI_NOMOR_FILE", self.dir_path / "gn.csv")
        self.patch_txt_gn = patch.object(shopee_core, "RESULTS_GANTI_NOMOR_TXT", self.dir_path / "gn.txt")
        self.patch_reedem = patch.object(shopee_core, "REEDEM_GANTI_NOMOR_TXT", self.dir_path / "reedem.txt")
        self.patch_download = patch.object(shopee_core, "DOWNLOAD_DIR", self.dir_path / "downloads")

        # Set super fast timing for tests
        self.patch_step_delay = patch.object(shopee_core, "STEP_DELAY", 0.0)
        self.patch_btn_timeout = patch.object(shopee_core, "BUTTON_TIMEOUT", 0.5)
        self.patch_res_timeout = patch.object(shopee_core, "RESULT_TIMEOUT", 1.0)
        self.patch_poll_interval = patch.object(shopee_core, "POLL_INTERVAL", 0.01)

        self.patch_csv_gn.start()
        self.patch_txt_gn.start()
        self.patch_reedem.start()
        self.patch_download.start()
        self.patch_step_delay.start()
        self.patch_btn_timeout.start()
        self.patch_res_timeout.start()
        self.patch_poll_interval.start()

    def tearDown(self):
        self.patch_poll_interval.stop()
        self.patch_res_timeout.stop()
        self.patch_btn_timeout.stop()
        self.patch_step_delay.stop()
        self.patch_download.stop()
        self.patch_reedem.stop()
        self.patch_txt_gn.stop()
        self.patch_csv_gn.stop()
        self.temp_dir.cleanup()

    # =========================================================================
    # 1 & 2. GANTI NOMOR CHECKER (OPSI 8)
    # =========================================================================

    async def test_01_ganti_nomor_belum_punya_no_hp_returns_fail_immediately(self):
        """Bot membalas '❌ Akun belum punya nomor HP. Ganti nomornya lewat /verify.'
        harus segera mengembalikan GAGAL tanpa menunggu RESULT_TIMEOUT.
        """
        btn_gn = MockButton("Ganti Nomor")
        btn_user = MockButton("Email / Username / ID")
        current_id = 100
        messages = []

        async def fake_send(target, text):
            nonlocal current_id
            current_id += 1
            sent = MockMessage(current_id, text, out=True)
            messages.append(sent)

            if text == "/account":
                current_id += 1
                messages.append(MockMessage(current_id, "Menu Akun", buttons=[[btn_gn]], out=False))
            elif text == "user_no_phone":
                current_id += 1
                # Respons bot definitif negatif: belum punya nomor HP
                messages.append(MockMessage(
                    current_id,
                    "❌ Akun belum punya nomor HP. Ganti nomornya lewat /verify.",
                    out=False
                ))
            return sent

        async def fake_get(target, limit=15):
            return sorted(messages, key=lambda m: m.id, reverse=True)[:limit]

        # Saat tombol ganti nomor diklik, bot tampilkan pilihan login
        def on_gn_click():
            nonlocal current_id
            current_id += 1
            messages.append(MockMessage(current_id, "Pilih metode:", buttons=[[btn_user]], out=False))
        btn_gn.on_click = on_gn_click

        # Saat tombol user diklik, bot kirim prompt
        def on_user_click():
            nonlocal current_id
            current_id += 1
            messages.append(MockMessage(current_id, "Silakan masukkan username / email / ID Shopee:", out=False))
        btn_user.on_click = on_user_click

        client = MagicMock()
        client.send_message = fake_send
        client.get_messages = fake_get

        start_t = time.time()
        is_eligible, status, detail = await shopee_core.check_one_change_number(
            client, "user_no_phone", auth_method="username"
        )
        elapsed = time.time() - start_t

        self.assertFalse(is_eligible)
        self.assertEqual(status, "GAGAL")
        self.assertIn("Belum punya nomor HP", detail)
        # Selesai jauh sebelum RESULT_TIMEOUT (1.0s)
        self.assertLess(elapsed, 0.5, "Harus selesai seketika tanpa menunggu timeout")

    async def test_02_ganti_nomor_definitive_cross_fails_and_empty_times_out(self):
        """Pesan diawali ❌ lain -> GAGAL langsung; tanpa balasan sama sekali -> TIMEOUT."""
        btn_gn = MockButton("Ganti Nomor")
        btn_user = MockButton("Email / Username / ID")

        # Kasus 2a: Balasan ❌ lain
        current_id = 200
        messages_a = []
        async def fake_send_a(target, text):
            nonlocal current_id
            current_id += 1
            sent = MockMessage(current_id, text, out=True)
            messages_a.append(sent)
            if text == "/account":
                current_id += 1
                messages_a.append(MockMessage(current_id, "Menu Akun", buttons=[[btn_gn]], out=False))
            elif text == "user_banned":
                current_id += 1
                messages_a.append(MockMessage(current_id, "❌ Akun ini sedang dibatasi karena pelanggaran.", out=False))
            return sent

        async def fake_get_a(target, limit=15):
            return sorted(messages_a, key=lambda m: m.id, reverse=True)[:limit]

        btn_gn.on_click = lambda: messages_a.append(MockMessage(current_id + 1, "Pilih metode:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: messages_a.append(MockMessage(current_id + 2, "Masukkan username:"))

        client_a = MagicMock()
        client_a.send_message = fake_send_a
        client_a.get_messages = fake_get_a

        is_eligible_a, status_a, detail_a = await shopee_core.check_one_change_number(
            client_a, "user_banned", auth_method="username"
        )
        self.assertFalse(is_eligible_a)
        self.assertIn(status_a, ("GAGAL", "AKUN DIBATASI / BANNED"))

        # Kasus 2b: Tidak ada balasan sama sekali -> TIMEOUT
        messages_b = []
        async def fake_send_b(target, text):
            nonlocal current_id
            current_id += 1
            sent = MockMessage(current_id, text, out=True)
            messages_b.append(sent)
            if text == "/account":
                current_id += 1
                messages_b.append(MockMessage(current_id, "Menu Akun", buttons=[[btn_gn]], out=False))
            # Tidak membalas apapun setelah kirim user
            return sent

        async def fake_get_b(target, limit=15):
            return sorted(messages_b, key=lambda m: m.id, reverse=True)[:limit]

        btn_gn.on_click = lambda: messages_b.append(MockMessage(current_id + 1, "Pilih metode:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: messages_b.append(MockMessage(current_id + 2, "Masukkan username:"))

        client_b = MagicMock()
        client_b.send_message = fake_send_b
        client_b.get_messages = fake_get_b

        is_eligible_b, status_b, detail_b = await shopee_core.check_one_change_number(
            client_b, "user_silent", auth_method="username"
        )
        self.assertFalse(is_eligible_b)
        self.assertEqual(status_b, "TIMEOUT")

    # =========================================================================
    # 3. MISI BAYAR QRIS (OPSI 1)
    # =========================================================================

    async def test_03_misi_non_qris_definitive_fails_and_qris_success(self):
        """Balasan non-QRIS negatif (misal akun tidak terdaftar) -> GAGAL, bukan TIMEOUT.
        Balasan baris QRIS -> koin & status akurat.
        """
        btn_checkin = MockButton("Misi Checkin")
        btn_user = MockButton("Email / Username / ID")

        # 3a. Negatif non-QRIS: '❌ Akun ini belum terdaftar di sistem bot'
        curr_id = 300
        msgs_a = []
        async def fake_send_misi_a(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs_a.append(sent)
            if text == "/mission":
                curr_id += 1
                msgs_a.append(MockMessage(curr_id, "Pilih misi:", buttons=[[btn_checkin]], out=False))
            elif text == "user_unregistered":
                curr_id += 1
                msgs_a.append(MockMessage(curr_id, "❌ Akun ini belum terdaftar di sistem bot.", out=False))
            return sent

        async def fake_get_misi_a(target, limit=15):
            return sorted(msgs_a, key=lambda m: m.id, reverse=True)[:limit]

        btn_checkin.on_click = lambda: msgs_a.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs_a.append(MockMessage(curr_id + 2, "Silakan kirim username:"))

        client_a = MagicMock()
        client_a.send_message = fake_send_misi_a
        client_a.get_messages = fake_get_misi_a

        coins_a, status_a, detail_a = await shopee_core.check_one_mission(
            client_a, "user_unregistered", auth_method="username"
        )
        self.assertIsNone(coins_a)
        self.assertEqual(status_a, "GAGAL")
        self.assertIn("belum terdaftar", detail_a)

        # 3b. Positif QRIS: Baris misi QRIS valid
        msgs_b = []
        async def fake_send_misi_b(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs_b.append(sent)
            if text == "/mission":
                curr_id += 1
                msgs_b.append(MockMessage(curr_id, "Pilih misi:", buttons=[[btn_checkin]], out=False))
            elif text == "user_valid_qris":
                curr_id += 1
                msgs_b.append(MockMessage(
                    curr_id,
                    "🎯 MISI CHECKIN SHOPEEPAY:\n➖ Bayar QRIS: 5.000 koin (Selesai)\n➖ Spin Koin: Belum",
                    out=False
                ))
            return sent

        async def fake_get_misi_b(target, limit=15):
            return sorted(msgs_b, key=lambda m: m.id, reverse=True)[:limit]

        btn_checkin.on_click = lambda: msgs_b.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs_b.append(MockMessage(curr_id + 2, "Silakan kirim username:"))

        client_b = MagicMock()
        client_b.send_message = fake_send_misi_b
        client_b.get_messages = fake_get_misi_b

        coins_b, status_b, detail_b = await shopee_core.check_one_mission(
            client_b, "user_valid_qris", auth_method="username"
        )
        self.assertEqual(coins_b, 5000)
        self.assertEqual(status_b, "SELESAI")

    # =========================================================================
    # 4. CEK VOUCHER FOOD (OPSI 2)
    # =========================================================================

    async def test_04_food_negative_text_returns_fail_and_loading_keeps_waiting(self):
        """Balasan teks negatif definitif tanpa file HTML -> GAGAL langsung, bukan TIMEOUT file.
        Pesan loading tanpa file HTML -> loop tetap menunggu.
        """
        btn_voucher = MockButton("Check Voucher")
        btn_user = MockButton("Email / Username / ID")

        # 4a. Teks negatif penolakan: '❌ Akun belum punya nomor HP'
        curr_id = 400
        msgs_a = []
        async def fake_send_food_a(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs_a.append(sent)
            if text == "/account":
                curr_id += 1
                msgs_a.append(MockMessage(curr_id, "Menu Akun:", buttons=[[btn_voucher]], out=False))
            elif text == "user_food_no_hp":
                curr_id += 1
                msgs_a.append(MockMessage(
                    curr_id,
                    "❌ Akun belum punya nomor HP. Ganti nomornya lewat /verify.",
                    out=False
                ))
            return sent

        async def fake_get_food_a(target, limit=15):
            return sorted(msgs_a, key=lambda m: m.id, reverse=True)[:limit]

        btn_voucher.on_click = lambda: msgs_a.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs_a.append(MockMessage(curr_id + 2, "Silakan kirim username:"))

        client_a = MagicMock()
        client_a.send_message = fake_send_food_a
        client_a.get_messages = fake_get_food_a

        start_t = time.time()
        is_val, status_a, detail_a, h25, h12 = await shopee_core.check_one_food(
            client_a, "user_food_no_hp", auth_method="username"
        )
        elapsed = time.time() - start_t

        self.assertFalse(is_val)
        self.assertEqual(status_a, "GAGAL")
        self.assertIn("nomor hp", detail_a.casefold())
        self.assertLess(elapsed, 0.5, "Harus langsung kembali tanpa menunggu timeout file HTML")

        # 4b. Pesan loading diikuti pengiriman file HTML valid
        dummy_html_content = (
            '<html><body>'
            '<span class="u">user_html_ok</span>'
            '<article class="vc" data-g="food">'
            '<div class="stub">ShopeeFood</div>'
            '<div class="body">'
            '<div class="h">Diskon 100% s.d. Rp25RB</div>'
            '<div class="m">Tanpa min. belanja</div>'
            '<div class="v">sisa 2 jam</div>'
            '</div>'
            '</article>'
            '</body></html>'
        )
        test_file = self.dir_path / "food_user_html_ok_123.html"
        test_file.write_text(dummy_html_content, encoding="utf-8")

        msgs_b = []
        async def fake_send_food_b(target, text):
            nonlocal curr_id
            curr_id += 1
            sent = MockMessage(curr_id, text, out=True)
            msgs_b.append(sent)
            if text == "/account":
                curr_id += 1
                msgs_b.append(MockMessage(curr_id, "Menu Akun:", buttons=[[btn_voucher]], out=False))
            elif text == "user_html_ok":
                curr_id += 1
                # 1. Pesan loading perantara
                msgs_b.append(MockMessage(curr_id, "⏳ Sedang memproses data voucher...", out=False))
                # 2. File HTML voucher
                curr_id += 1
                doc_msg = MockMessage(
                    curr_id,
                    "Berikut file voucher Anda:",
                    document=MockDoc("voucher_user_html_ok.html"),
                    out=False
                )
                async def fake_dl(dest):
                    Path(dest).write_text(dummy_html_content, encoding="utf-8")
                doc_msg.download_media = fake_dl
                msgs_b.append(doc_msg)
            return sent

        async def fake_get_food_b(target, limit=15):
            return sorted(msgs_b, key=lambda m: m.id, reverse=True)[:limit]

        btn_voucher.on_click = lambda: msgs_b.append(MockMessage(curr_id + 1, "Pilih login:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: msgs_b.append(MockMessage(curr_id + 2, "Silakan kirim username:"))

        client_b = MagicMock()
        client_b.send_message = fake_send_food_b
        client_b.get_messages = fake_get_food_b

        is_val_b, status_b, detail_b, h25_b, h12_b = await shopee_core.check_one_food(
            client_b, "user_html_ok", auth_method="username"
        )
        self.assertTrue(is_val_b)
        self.assertEqual(status_b, "MEMENUHI SYARAT")
        self.assertTrue(h25_b)

    # =========================================================================
    # 5. KLAIM VOUCHER (OPSI 7)
    # =========================================================================

    def test_05_claim_response_classification(self):
        """Klaim: Balasan negatif definitif -> GAGAL (bukan TIDAK DIKETAHUI).
        Balasan tidak dikenal -> tetap TIDAK DIKETAHUI.
        Perantara -> TIDAK DIKETAHUI (status perantara).
        """
        # 5a. Kriteria tidak memenuhi -> GAGAL
        st, dt = voucher_claim.classify_claim_response("Maaf, akun Anda belum memenuhi kriteria klaim voucher ini.")
        self.assertEqual(st, "GAGAL")

        # 5b. Akun tidak ditemukan -> GAGAL
        st, dt = voucher_claim.classify_claim_response("Akun tidak ditemukan pada database Shopee.")
        self.assertEqual(st, "GAGAL")

        # 5c. Cookie tidak valid / expired -> GAGAL
        st, dt = voucher_claim.classify_claim_response("Format cookie salah atau cookie expired.")
        self.assertEqual(st, "GAGAL")

        # 5d. Belum punya nomor HP -> GAGAL
        st, dt = voucher_claim.classify_claim_response("❌ Akun belum punya nomor HP. Ganti nomornya lewat /verify.")
        self.assertEqual(st, "GAGAL")
        self.assertIn("nomor HP", dt)

        # 5e. Balasan ❌ lain -> GAGAL
        st, dt = voucher_claim.classify_claim_response("❌ Tautan voucher ini tidak aktif atau salah.")
        self.assertEqual(st, "GAGAL")

        # 5f. Balasan benar-benar tidak dikenal -> TIDAK DIKETAHUI
        st, dt = voucher_claim.classify_claim_response("Halo kak! Selamat siang dari Shopee Bot.")
        self.assertEqual(st, "TIDAK DIKETAHUI")

        # 5g. Pesan perantara / loading -> TIDAK DIKETAHUI (berstatus perantara)
        st, dt = voucher_claim.classify_claim_response("⏳ Sedang memproses klaim voucher...")
        self.assertEqual(st, "TIDAK DIKETAHUI")
        self.assertIn("perantara", dt)

        # 5h. Kosong -> TIDAK DIKETAHUI
        st, dt = voucher_claim.classify_claim_response("")
        self.assertEqual(st, "TIDAK DIKETAHUI")

    # =========================================================================
    # 6. UJI LINTAS AKUN: PESAN 'DIBATALKAN.' TIDAK TERBAWA
    # =========================================================================

    async def test_06_cancelled_message_cross_account_isolation(self):
        """Pesan 'Dibatalkan.' setelah klik Batal di akun A tidak boleh terbawa
        atau dianggap sebagai hasil akun B berikutnya.
        """
        btn_gn = MockButton("Ganti Nomor")
        btn_user = MockButton("Email / Username / ID")
        btn_cancel = MockButton("Batal")
        btn_pwd = MockButton("Password Akun")
        btn_pin = MockButton("PIN ShopeePay")

        current_id = 600
        messages = []

        async def fake_send_multi(target, text):
            nonlocal current_id
            current_id += 1
            sent = MockMessage(current_id, text, out=True)
            messages.append(sent)

            if text == "/account":
                current_id += 1
                messages.append(MockMessage(current_id, "Menu Akun:", buttons=[[btn_gn]], out=False))
            elif text == "user_a_otp":
                current_id += 1
                # Akun A minta OTP -> ada tombol Batal
                messages.append(MockMessage(
                    current_id,
                    "Kode verifikasi OTP akan dikirimkan ke WhatsApp Anda.",
                    buttons=[[btn_cancel]],
                    out=False
                ))
            elif text == "user_b_layak":
                current_id += 1
                # Akun B minta Password/PIN -> layak
                messages.append(MockMessage(
                    current_id,
                    "Pilih metode verifikasi identitas akun:",
                    buttons=[[btn_pwd, btn_pin], [btn_cancel]],
                    out=False
                ))
            return sent

        async def fake_get_multi(target, limit=15):
            return sorted(messages, key=lambda m: m.id, reverse=True)[:limit]

        # Saat Batal diklik pada Akun A, bot mengirim konfirmasi 'Dibatalkan.'
        async def on_cancel_click():
            nonlocal current_id
            current_id += 1
            messages.append(MockMessage(current_id, "Dibatalkan.", out=False))
        btn_cancel.on_click = on_cancel_click

        btn_gn.on_click = lambda: messages.append(MockMessage(current_id + 1, "Pilih metode:", buttons=[[btn_user]]))
        btn_user.on_click = lambda: messages.append(MockMessage(current_id + 2, "Masukkan username:"))

        client = MagicMock()
        client.send_message = fake_send_multi
        client.get_messages = fake_get_multi

        # Jalankan Akun A (OTP -> dibatalkan)
        is_el_a, st_a, dt_a = await shopee_core.check_one_change_number(
            client, "user_a_otp", auth_method="username"
        )
        self.assertFalse(is_el_a)
        self.assertEqual(st_a, "GAGAL")
        self.assertTrue(btn_cancel.clicked)

        # Pastikan pesan 'Dibatalkan.' masuk ke antrean bot
        any_cancel_msg = any("Dibatalkan." in (m.text or "") for m in messages)
        self.assertTrue(any_cancel_msg)

        # Reset tombol cancel
        btn_cancel.clicked = False

        # Jalankan Akun B (Harus berhasil membaca Password/PIN dan TIDAK terganggu pesan 'Dibatalkan.')
        is_el_b, st_b, dt_b = await shopee_core.check_one_change_number(
            client, "user_b_layak", auth_method="username"
        )
        self.assertTrue(is_el_b)
        self.assertEqual(st_b, "SUKSES")
        self.assertIn("Password/PIN", dt_b)


if __name__ == "__main__":
    unittest.main()
