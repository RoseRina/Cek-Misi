#!/usr/bin/env python3
"""Unit tests untuk fitur Cek Ganti Nomor (Checker Only) di shopee_core.py & cek_misi_termux.py.

Menguji 7 skenario wajib:
1. Balasan OTP -> GAGAL, dan tombol Batal diklik.
2. Balasan 'pilih metode / butuh verifikasi identitas' dengan tombol Password/PIN ShopeePay -> SUKSES, tombol Batal diklik, dan akun masuk reedem_gantinomor.txt tanpa duplikat.
3. Balasan 'pilih metode' tanpa tombol Password/PIN -> GAGAL, tombol Batal diklik, dan akun dihapus dari reedem_gantinomor.txt jika sebelumnya ada.
4. Timeout tanpa balasan yang bisa diklasifikasikan -> GAGAL / TIMEOUT, bukan SUKSES.
5. Akun username -> klik tombol Email/Username/ID (bukan Raw Cookie); Akun raw cookie -> klik Raw Cookie (bukan Email/Username/ID).
6. Akun cookie di semua output hasil (terminal/CSV/TXT) tampil tersamar, tidak pernah utuh.
7. Seluruh test terisolasi dengan data sintetis/palsu dan direktori temporary.
"""

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cek_misi_termux
import shopee_core


class DummyButton:
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


class DummyMessage:
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
                await btn.click()


class InteractiveDummyBot:
    def __init__(self, result_type="otp", with_pwd_pin=True, is_ubah_label=False):
        self.result_type = result_type
        self.with_pwd_pin = with_pwd_pin
        self.is_ubah_label = is_ubah_label
        self.current_id = 10
        self.messages = []

        self.btn_cancel = DummyButton("Batal")
        self.btn_ganti = DummyButton("Ubah Nomor" if is_ubah_label else "Ganti Nomor", on_click=self._on_ganti_clicked)
        self.btn_user = DummyButton("Email / Username / ID", on_click=lambda: self._on_method_clicked(is_cookie=False))
        self.btn_cookie = DummyButton("Raw Cookie", on_click=lambda: self._on_method_clicked(is_cookie=True))
        self.btn_pwd = DummyButton("Password Akun")
        self.btn_pin = DummyButton("PIN ShopeePay")
        self.btn_face = DummyButton("Verifikasi Wajah")

    def _on_ganti_clicked(self):
        self.current_id += 1
        msg = DummyMessage(
            self.current_id,
            "Pilih metode identifikasi akun:",
            buttons=[[self.btn_user, self.btn_cookie]],
            out=False,
        )
        self.messages.append(msg)

    def _on_method_clicked(self, is_cookie=False):
        self.current_id += 1
        prompt = "Kirim raw cookie Shopee:" if is_cookie else "Silakan masukkan username / email / ID Shopee:"
        msg = DummyMessage(self.current_id, prompt, out=False)
        self.messages.append(msg)

    async def get_messages(self, entity, limit=15):
        return sorted(self.messages, key=lambda m: m.id, reverse=True)[:limit]

    async def send_message(self, entity, text):
        self.current_id += 1
        sent = DummyMessage(self.current_id, text=text, out=True)
        self.messages.append(sent)

        # 1. Respons perintah /account
        if text.strip() == "/account":
            self.current_id += 1
            msg = DummyMessage(
                self.current_id,
                "Menu Akun Shopee Tools:",
                buttons=[[self.btn_ganti]],
                out=False,
            )
            self.messages.append(msg)

        # 2. Respons setelah username/cookie dikirim
        elif text.strip() != "/account":
            self.current_id += 1
            if self.result_type == "otp":
                msg = DummyMessage(
                    self.current_id,
                    "Kode verifikasi OTP akan dikirimkan ke nomor WhatsApp akun Anda.",
                    buttons=[[self.btn_cancel]],
                    out=False,
                )
                self.messages.append(msg)
            elif self.result_type == "password_pin":
                buttons = [[self.btn_pwd, self.btn_pin], [self.btn_cancel]] if self.with_pwd_pin else [[self.btn_face], [self.btn_cancel]]
                msg = DummyMessage(
                    self.current_id,
                    "Pilih metode verifikasi identitas akun Anda:",
                    buttons=buttons,
                    out=False,
                )
                self.messages.append(msg)
            elif self.result_type == "timeout":
                # Tidak ada balasan bot
                pass

        return sent


class TestChangeNumberChecker(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Arahkan path file output ke direktori temporary
        self.csv_file = self.dir_path / "hasil_ganti_nomor.csv"
        self.txt_file = self.dir_path / "hasil_ganti_nomor.txt"
        self.reedem_file = self.dir_path / "reedem_gantinomor.txt"

        self.patch_csv = patch.object(shopee_core, "RESULTS_GANTI_NOMOR_FILE", self.csv_file)
        self.patch_txt = patch.object(shopee_core, "RESULTS_GANTI_NOMOR_TXT", self.txt_file)
        self.patch_reedem = patch.object(shopee_core, "REEDEM_GANTI_NOMOR_TXT", self.reedem_file)
        self.patch_step_delay = patch.object(shopee_core, "STEP_DELAY", 0.0)
        self.patch_btn_timeout = patch.object(shopee_core, "BUTTON_TIMEOUT", 1.0)
        self.patch_res_timeout = patch.object(shopee_core, "RESULT_TIMEOUT", 0.5)
        self.patch_poll_interval = patch.object(shopee_core, "POLL_INTERVAL", 0.02)

        self.patch_csv.start()
        self.patch_txt.start()
        self.patch_reedem.start()
        self.patch_step_delay.start()
        self.patch_btn_timeout.start()
        self.patch_res_timeout.start()
        self.patch_poll_interval.start()

    def tearDown(self):
        self.patch_poll_interval.stop()
        self.patch_res_timeout.stop()
        self.patch_btn_timeout.stop()
        self.patch_step_delay.stop()
        self.patch_reedem.stop()
        self.patch_txt.stop()
        self.patch_csv.stop()
        self.temp_dir.cleanup()

    # 1. Balasan OTP -> GAGAL, dan tombol Batal diklik
    async def test_01_otp_response_returns_fail_and_clicks_cancel(self):
        bot = InteractiveDummyBot(result_type="otp")

        is_eligible, status, detail = await shopee_core.check_one_change_number(
            bot, "user_test_dummy", auth_method="username"
        )

        self.assertFalse(is_eligible)
        self.assertEqual(status, "GAGAL")
        self.assertIn("Meminta OTP", detail)
        self.assertTrue(bot.btn_ganti.clicked, "Tombol Ganti Nomor harus diklik")
        self.assertTrue(bot.btn_user.clicked, "Tombol Email/Username/ID harus diklik")
        self.assertTrue(bot.btn_cancel.clicked, "Tombol Batal harus diklik saat bot meminta OTP")

    # 2. Balasan 'pilih metode' dengan Password/PIN -> SUKSES, Batal diklik, masuk reedem_gantinomor.txt tanpa duplikat
    async def test_02_password_or_pin_returns_success_and_saves_dedup(self):
        bot = InteractiveDummyBot(result_type="password_pin", with_pwd_pin=True)

        is_eligible, status, detail = await shopee_core.check_one_change_number(
            bot, "user_layak_123", auth_method="username"
        )

        self.assertTrue(is_eligible)
        self.assertEqual(status, "SUKSES")
        self.assertIn("Password/PIN", detail)
        self.assertTrue(bot.btn_cancel.clicked, "Tombol Batal harus diklik setelah verifikasi terdeteksi")

        # Simpan hasil pertama kali
        shopee_core.save_ganti_nomor_result("user_layak_123", status, detail, auth_method="username")
        self.assertTrue(self.reedem_file.exists())
        content_first = self.reedem_file.read_text(encoding="utf-8").splitlines()
        self.assertIn("user_layak_123", content_first)
        self.assertEqual(content_first.count("user_layak_123"), 1)

        # Simpan kedua kali -> pastikan tidak duplikat
        shopee_core.save_ganti_nomor_result("user_layak_123", status, detail, auth_method="username")
        content_second = self.reedem_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(content_second.count("user_layak_123"), 1)

    # 3. Balasan 'pilih metode' tanpa Password/PIN -> GAGAL, Batal diklik, akun dihapus jika sebelumnya ada
    async def test_03_no_password_or_pin_returns_fail_and_removes_from_reedem(self):
        bot = InteractiveDummyBot(result_type="password_pin", with_pwd_pin=False, is_ubah_label=True)

        # Awalnya akun ada di file reedem_gantinomor.txt
        self.reedem_file.write_text("user_tidak_layak\nuser_lain\n", encoding="utf-8")

        is_eligible, status, detail = await shopee_core.check_one_change_number(
            bot, "user_tidak_layak", auth_method="username"
        )

        self.assertFalse(is_eligible)
        self.assertEqual(status, "GAGAL")
        self.assertIn("bukan Password/PIN", detail)
        self.assertTrue(bot.btn_cancel.clicked, "Tombol Batal harus diklik")

        # Sinkronisasi hasil gagal -> akun harus terhapus dari reedem_gantinomor.txt
        shopee_core.save_ganti_nomor_result("user_tidak_layak", status, detail, auth_method="username")
        updated_lines = self.reedem_file.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("user_tidak_layak", updated_lines)
        self.assertIn("user_lain", updated_lines)

    # 4. Timeout tanpa balasan yang dapat diklasifikasikan -> TIMEOUT / GAGAL
    async def test_04_timeout_returns_timeout_and_never_success(self):
        bot = InteractiveDummyBot(result_type="timeout")

        is_eligible, status, detail = await shopee_core.check_one_change_number(
            bot, "user_timeout_dummy", auth_method="username"
        )

        self.assertFalse(is_eligible)
        self.assertEqual(status, "TIMEOUT")
        self.assertIn("Timeout", detail)

    # 5. Pemilihan tombol login: Username -> Email/Username/ID; Raw Cookie -> Raw Cookie
    async def test_05_auth_method_button_selection(self):
        # Skenario A: Username
        bot_a = InteractiveDummyBot(result_type="otp")
        await shopee_core.check_one_change_number(bot_a, "nama_user_biasa", auth_method="username")
        self.assertTrue(bot_a.btn_user.clicked, "Tombol Email/Username/ID harus diklik untuk akun username")
        self.assertFalse(bot_a.btn_cookie.clicked, "Tombol Raw Cookie TIDAK boleh diklik untuk akun username")

        # Skenario B: Raw Cookie
        bot_b = InteractiveDummyBot(result_type="otp")
        fake_cookie = "SPC_EC=contoh_token_palsu_alpha12345; SPC_U=10009999;"
        await shopee_core.check_one_change_number(bot_b, fake_cookie, auth_method="auto")
        self.assertTrue(bot_b.btn_cookie.clicked, "Tombol Raw Cookie harus diklik untuk akun cookie")
        self.assertFalse(bot_b.btn_user.clicked, "Tombol Email/Username/ID TIDAK boleh diklik untuk akun cookie")

    # 6. Akun cookie di semua output hasil (terminal/CSV/TXT) tampil tersamar, tidak pernah utuh
    def test_06_cookie_masking_in_csv_txt_and_terminal(self):
        fake_cookie = "SPC_EC=contoh_token_rahasia_x99y88z77; SPC_U=12345678;"

        shopee_core.save_ganti_nomor_result(fake_cookie, "SUKSES", "Butuh Password/PIN", auth_method="cookie")

        # Periksa file CSV
        csv_text = self.csv_file.read_text(encoding="utf-8-sig")
        self.assertNotIn(fake_cookie, csv_text, "Cookie mentah utuh tidak boleh ada di CSV")
        self.assertNotIn("contoh_token_rahasia_x99y88z77", csv_text)
        self.assertIn("Cookie", csv_text)
        self.assertIn("UID: 12345678", csv_text)

        # Periksa file TXT riwayat
        txt_history = self.txt_file.read_text(encoding="utf-8")
        self.assertNotIn(fake_cookie, txt_history, "Cookie mentah utuh tidak boleh ada di TXT")
        self.assertNotIn("contoh_token_rahasia_x99y88z77", txt_history)
        self.assertIn("Cookie", txt_history)

        # Periksa file reedem_gantinomor.txt
        reedem_text = self.reedem_file.read_text(encoding="utf-8")
        self.assertNotIn(fake_cookie, reedem_text, "Cookie mentah utuh tidak boleh ada di reedem_gantinomor.txt")
        self.assertNotIn("contoh_token_rahasia_x99y88z77", reedem_text)
        self.assertIn("Cookie", reedem_text)

        # Periksa render ringkasan terminal
        summary_box = shopee_core.render_change_number_summary_box(
            total_processed=1,
            success_count=1,
            fail_count=0,
            error_count=0,
            success_accounts=[shopee_core.format_account_display(fake_cookie, "cookie")],
        )
        self.assertNotIn(fake_cookie, summary_box, "Cookie mentah utuh tidak boleh ada di ringkasan terminal")
        self.assertNotIn("contoh_token_rahasia_x99y88z77", summary_box)
        self.assertIn("Cookie", summary_box)


if __name__ == "__main__":
    unittest.main()
