#!/usr/bin/env python3
"""Unit tests untuk modul Klaim Voucher ShopeeFood (voucher_claim.py).

Menguji seluruh fungsionalitas dan skenario penanganan error:
1. Konfigurasi Telegram & Tautan Voucher
2. Validasi file input (tidak ditemukan, kosong, duplikat)
3. Tombol Claim Voucher tidak ditemukan / timeout
4. Tombol metode identifikasi tidak ditemukan / timeout
5. Pengabaian pesan lama (stale message) & pesan loading
6. Klasifikasi respons (BERHASIL, GAGAL, TIDAK DIKETAHUI)
7. Penanganan FloodWaitError & Timeout
8. Penyimpanan inkremental hasil klaim ke bot_responses.txt
9. Format tampilan box ringkasan terminal
10. Integrasi menu baru tanpa merusak menu lama
"""

import argparse
import asyncio
from io import StringIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telethon.errors import FloodWaitError

import cek_misi_termux
import shopee_core
import voucher_claim


class DummyButton:
    def __init__(self, text: str):
        self.text = text
        self.clicked = False

    async def click(self):
        self.clicked = True


class DummyMessage:
    def __init__(self, msg_id: int, text: str = "", buttons=None, out: bool = False):
        self.id = msg_id
        self.text = text
        self.buttons = buttons or []
        self.out = out


class TestVoucherClaimModule(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Konfigurasi Tautan Voucher & Telegram
    def test_voucher_config_env_priority(self):
        custom_env = "https://shopee.co.id/voucher/details?evcode=CUSTOM_ENV"
        with patch.dict(os.environ, {"SHOPEE_VOUCHER_LINK": custom_env}):
            link = voucher_claim.load_voucher_claim_config()
            self.assertEqual(link, custom_env)

    def test_voucher_config_file_save_and_load(self):
        cfg_file = self.dir_path / "voucher_claim_config.json"
        with patch("voucher_claim.CONFIG_CLAIM_FILE", cfg_file):
            with patch.dict(os.environ, {}, clear=True):
                # Sebelum ada file, return default
                self.assertIn("evcode=NEWFOODIES", voucher_claim.load_voucher_claim_config())

                # Simpan konfigurasi baru
                new_link = "https://shopee.co.id/voucher/details?evcode=PROMO_BARU"
                saved = voucher_claim.save_voucher_claim_config(new_link)
                self.assertTrue(saved)
                self.assertTrue(cfg_file.exists())

                # Baca kembali
                loaded = voucher_claim.load_voucher_claim_config()
                self.assertEqual(loaded, new_link)

                # Simpan link kosong harus ditolak
                self.assertFalse(voucher_claim.save_voucher_claim_config("   "))

    def test_telegram_config_validation(self):
        """Memastikan sistem dapat mendeteksi apakah kredensial Telegram sudah lengkap atau belum."""
        with patch("shopee_core.load_credentials", return_value=(0, "")):
            self.assertFalse(voucher_claim.check_telegram_credentials_configured())

        with patch("shopee_core.load_credentials", return_value=(123456, "abcdef123456")):
            self.assertTrue(voucher_claim.check_telegram_credentials_configured())

    # 2. File Input & Deduplikasi
    def test_read_claim_accounts_file_not_found(self):
        non_existent = self.dir_path / "ghost_file.txt"
        with self.assertRaises(FileNotFoundError):
            voucher_claim.read_claim_accounts(non_existent)

    def test_read_claim_accounts_empty_file(self):
        empty_file = self.dir_path / "empty_accounts.txt"
        empty_file.write_text("   \n\n# Komentar saja\n", encoding="utf-8")
        accounts, dupes = voucher_claim.read_claim_accounts(empty_file)
        self.assertEqual(accounts, [])
        self.assertEqual(dupes, 0)

    def test_read_claim_accounts_deduplication(self):
        acc_file = self.dir_path / "accounts.txt"
        content = """
        user1@example.com
        USER1@EXAMPLE.COM
        user2@example.com
        # Komentar yang harus diabaikan
        user3@example.com
        user2@example.com
        user1@example.com
        """
        acc_file.write_text(content.strip(), encoding="utf-8")
        accounts, dupes = voucher_claim.read_claim_accounts(acc_file)
        self.assertEqual(accounts, ["user1@example.com", "user2@example.com", "user3@example.com"])
        self.assertEqual(dupes, 3)

    # 3. Klasifikasi Respons Bot
    def test_classify_claim_response_berhasil(self):
        samples = [
            "Selamat! Voucher ShopeeFood 25RB berhasil diklaim.",
            "Claim voucher berhasil ditambahkan ke akun Anda.",
            "Voucher telah masuk ke dompet voucher Anda.",
            "Claimed successfully! Silakan gunakan.",
            "Voucher berhasil klaim",
        ]
        for s in samples:
            status, detail = voucher_claim.classify_claim_response(s)
            self.assertEqual(status, "BERHASIL", f"Gagal mengklasifikasikan: {s}")

    def test_classify_claim_response_gagal(self):
        samples = [
            ("❌ Maaf, kamu belum memenuhi kriteria untuk klaim atau mendapatkan voucher ini.", "kriteria"),
            ("❌ Maaf, kamu belum memenuhi kriteria untuk klaim atau men...", "kriteria_truncated"),
            ("Maaf, akun Anda belum memenuhi kriteria promo NewFoodies.", "kriteria"),
            ("Maaf, kuota voucher ini sudah habis hari ini.", "Kuota"),
            ("Akun Anda sudah pernah mengklaim voucher ini sebelumnya.", "pernah"),
            ("Akun tidak memenuhi syarat untuk promo NewFoodies.", "syarat"),
            ("Voucher ini sudah kadaluwarsa / expired.", "kedaluwarsa"),
            ("Akun terkena limit pembatasan.", "limit"),
            ("User tidak ditemukan pada sistem.", "tidak ditemukan"),
            ("Gagal memproses klaim voucher.", "Gagal"),
        ]
        for text, desc in samples:
            status, detail = voucher_claim.classify_claim_response(text)
            self.assertEqual(status, "GAGAL", f"Seharusnya GAGAL: {text}")
            if "kriteria" in desc:
                self.assertIn("TIDAK MEMENUHI KRITERIA", detail)

    def test_classify_claim_response_tidak_diketahui(self):
        samples = [
            "",
            "   ",
            "Halo, ada yang bisa dibantu dari customer service?",
            "Silakan pilih menu utama bot berikut:",
            "Mohon tunggu, sedang memproses permintaan Anda...",
        ]
        for s in samples:
            status, detail = voucher_claim.classify_claim_response(s)
            self.assertEqual(status, "TIDAK DIKETAHUI", f"Seharusnya TIDAK DIKETAHUI: {s}")

    def test_is_intermediate_response(self):
        # Respons perantara yang harus dikenali
        intermediate_samples = [
            "⏳ Klaim voucher...",
            "⏳ Klaim voucher sedang diproses...",
            "⌛ Memproses klaim...",
            "Mohon tunggu, sedang memproses permintaan Anda...",
            "Tunggu sebentar, sedang memproses...",
            "Klaim voucher sedang diproses...",
        ]
        for s in intermediate_samples:
            self.assertTrue(
                voucher_claim.is_intermediate_response(s),
                f"Seharusnya terdeteksi sebagai intermediate: {s}",
            )
            status, detail = voucher_claim.classify_claim_response(s)
            self.assertEqual(status, "TIDAK DIKETAHUI")
            self.assertIn("perantara", detail.lower())

        # Respons final tidak boleh dideteksi sebagai intermediate
        final_samples = [
            "✅ Voucher berhasil diklaim ke akun",
            "❌ Maaf, kamu belum memenuhi kriteria untuk klaim atau menggunakan voucher ini.",
            "Gagal memproses klaim voucher.",
            "Maaf, kuota voucher ini sudah habis hari ini.",
        ]
        for s in final_samples:
            self.assertFalse(
                voucher_claim.is_intermediate_response(s),
                f"Tidak boleh terdeteksi sebagai intermediate: {s}",
            )

    def test_sanitize_log_text_masks_credentials(self):
        raw = "Error hash: 1234567890abcdef1234567890abcdef with OTP 482910 and phone +6281234567890"
        cleaned = voucher_claim.sanitize_log_text(raw)
        self.assertNotIn("1234567890abcdef1234567890abcdef", cleaned)
        self.assertNotIn("482910", cleaned)
        self.assertNotIn("+6281234567890", cleaned)
        self.assertIn("[REDACTED_HASH]", cleaned)
        self.assertIn("[REDACTED_CODE]", cleaned)
        self.assertIn("[REDACTED_PHONE]", cleaned)

    # 4. Deteksi Pesan Baru & Pengabaian Pesan Lama (Stale Messages)
    async def test_wait_for_bot_message_ignores_stale_and_out_messages(self):
        client = AsyncMock()
        # Buat pesan:
        # id=10 (lama, sebelum after_id=20)
        # id=21 (out=True, pesan kita sendiri)
        # id=22 (pesan bot baru setelah after_id=20)
        btn_old = DummyButton("Claim Voucher")
        btn_new = DummyButton("Claim Voucher")
        msg_old = DummyMessage(10, "Old message", buttons=[[btn_old]], out=False)
        msg_out = DummyMessage(21, "Our message", buttons=[[btn_old]], out=True)
        msg_new = DummyMessage(22, "Silakan klik", buttons=[[btn_new]], out=False)

        client.get_messages.return_value = [msg_new, msg_out, msg_old]

        msg, btn, r, c = await voucher_claim.wait_for_bot_message_with_buttons(
            client=client,
            target_bot="@shp_tools_bot",
            after_id=20,
            match_fn=lambda t: "claim" in t.casefold(),
            timeout=1.0,
            poll_interval=0.05,
        )
        self.assertIsNotNone(msg)
        self.assertEqual(msg.id, 22)
        self.assertEqual(btn, btn_new)

    async def test_wait_for_bot_final_response_filters_loading_messages(self):
        client = AsyncMock()
        # Panggilan pertama mengembalikan pesan loading
        loading_msg = DummyMessage(30, "Mohon tunggu, sedang memproses klaim...")
        final_msg = DummyMessage(31, "Selamat! Voucher berhasil diklaim.")

        call_count = 0
        async def mock_get_messages(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [loading_msg]
            return [final_msg, loading_msg]

        client.get_messages.side_effect = mock_get_messages

        resp = await voucher_claim.wait_for_bot_final_response(
            client=client,
            target_bot="@shp_tools_bot",
            after_id=25,
            timeout=2.0,
            poll_interval=0.05,
        )
        self.assertIn("berhasil diklaim", resp)

    async def test_wait_for_bot_final_response_edited_message(self):
        client = AsyncMock()
        call_count = 0

        async def mock_get_messages(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Bot awalnya mengirim pesan loading dengan id 40
                return [DummyMessage(40, "⏳ Klaim voucher...")]
            # Bot mengedit pesan id 40 menjadi pesan final
            return [DummyMessage(40, "❌ Maaf, kamu belum memenuhi kriteria untuk klaim atau menggunakan voucher ini.")]

        client.get_messages.side_effect = mock_get_messages

        resp = await voucher_claim.wait_for_bot_final_response(
            client=client,
            target_bot="@shp_tools_bot",
            after_id=35,
            timeout=2.0,
            poll_interval=0.05,
        )
        self.assertIn("belum memenuhi kriteria", resp)

    async def test_wait_for_bot_final_response_timeout_fallback(self):
        client = AsyncMock()
        # Bot hanya mengirim pesan loading dan tidak pernah mengirim pesan final
        client.get_messages.return_value = [DummyMessage(50, "⏳ Klaim voucher...")]

        resp = await voucher_claim.wait_for_bot_final_response(
            client=client,
            target_bot="@shp_tools_bot",
            after_id=45,
            timeout=0.1,
            poll_interval=0.02,
        )
        self.assertEqual(resp, "⏳ Klaim voucher...")

    # 5. Penanganan Error Tombol Tidak Ditemukan / Timeout
    async def test_claim_voucher_missing_claim_button(self):
        client = AsyncMock()
        client.send_message.return_value = DummyMessage(10)
        # Bot membalas pesan tanpa tombol Claim Voucher
        other_btn = DummyButton("Bantuan Bot")
        client.get_messages.return_value = [DummyMessage(11, "Pilih opsi:", buttons=[[other_btn]])]

        status, detail, raw = await voucher_claim.claim_voucher_for_account(
            client=client,
            account_identity="shopee_user_1",
            voucher_link="https://shopee.co.id/voucher/test",
            timeout=0.1,
        )
        self.assertEqual(status, "TIDAK DIKETAHUI")
        self.assertIn("Tombol 'Claim Voucher' tidak ditemukan", detail)

    async def test_claim_voucher_missing_method_button(self):
        client = AsyncMock()
        client.send_message.side_effect = [
            DummyMessage(10),  # /account
            DummyMessage(20),  # voucher link
        ]
        claim_btn = DummyButton("Claim Voucher")
        claim_msg = DummyMessage(15, "Pilih:", buttons=[[claim_btn]])

        # Tahap 1 ada tombol Claim Voucher, tetapi balasan link voucher tidak punya tombol Email/ID
        client.get_messages.side_effect = [
            [claim_msg],
            [DummyMessage(25, "Format link salah atau tidak ada tombol", buttons=[])]
        ]

        status, detail, raw = await voucher_claim.claim_voucher_for_account(
            client=client,
            account_identity="user@example.com",
            voucher_link="https://shopee.co.id/voucher/test",
            timeout=0.2,
        )
        self.assertEqual(status, "TIDAK DIKETAHUI")
        self.assertIn("Tombol metode identifikasi tidak ditemukan", detail)

    # 6. Alur Lengkap Berhasil Klaim Voucher untuk 1 Akun
    async def test_claim_voucher_success_flow(self):
        client = AsyncMock()
        client.send_message.side_effect = [
            DummyMessage(10),  # kirim /account
            DummyMessage(20),  # kirim link
            DummyMessage(30),  # kirim email
        ]
        btn_claim = DummyButton("🎟️ Claim Voucher")
        msg_claim = DummyMessage(15, buttons=[[btn_claim]])

        btn_email = DummyButton("📧 Email")
        msg_email = DummyMessage(25, buttons=[[btn_email]])

        msg_result = DummyMessage(35, "Voucher berhasil diklaim ke akun Anda!")

        client.get_messages.side_effect = [
            [msg_claim],
            [msg_email],
            [msg_result],
        ]

        status, detail, raw = await voucher_claim.claim_voucher_for_account(
            client=client,
            account_identity="buyer123@gmail.com",
            voucher_link="https://shopee.co.id/voucher/test",
            timeout=1.0,
        )
        self.assertEqual(status, "BERHASIL")
        self.assertTrue(btn_claim.clicked)
        self.assertTrue(btn_email.clicked)
        self.assertIn("berhasil diklaim", raw)

    # 7. Penanganan FloodWaitError & Penyimpanan Hasil Inkremental
    async def test_run_voucher_claim_mode_floodwait_and_saving(self):
        client = AsyncMock()
        out_file = self.dir_path / "test_bot_responses.txt"
        accounts = ["user_1", "user_2", "user_3"]

        async def mock_claim(client, account_identity, *args, **kwargs):
            if account_identity == "user_1":
                return "BERHASIL", "Voucher berhasil diklaim", "OK"
            elif account_identity == "user_2":
                raise FloodWaitError(request=None)
            return "GAGAL", "Gagal", "FAIL"

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                with patch("sys.stdout", new=StringIO()):
                    stats = await voucher_claim.run_voucher_claim_mode(
                        client=client,
                        accounts=accounts,
                        output_file=out_file,
                        step_delay=0.01,
                    )

        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["completed"], 2)  # user_1 + user_2 (floodwait)
        self.assertEqual(stats["success"], 1)
        self.assertEqual(stats["unknown"], 1)  # FloodWait dihitung tidak diketahui/tertunda

        self.assertTrue(out_file.exists())
        saved_text = out_file.read_text(encoding="utf-8")
        self.assertIn("user_1", saved_text)
        self.assertIn("BERHASIL", saved_text)
        self.assertIn("FloodWait", saved_text)

    # 8. Format Tampilan Kotak Terminal Konsisten
    def test_render_claim_summary_box(self):
        box = voucher_claim.render_claim_summary_box(
            total_accounts=10,
            completed_count=7,
            success_count=5,
            fail_count=1,
            unknown_count=1,
            box_width=48,
            output_file_name="bot_responses.txt",
        )
        lines = box.strip().splitlines()
        self.assertTrue(lines[0].startswith("\033[92m╭"))
        self.assertTrue(lines[-1].startswith("📂"))
        self.assertIn("Total akun", box)
        self.assertIn("Selesai", box)
        self.assertIn("Berhasil", box)
        self.assertIn("Gagal", box)
        self.assertIn("Tidak diketahui", box)

        # Periksa integritas lebar kolom (garis bingkai tidak miring)
        for line in lines[:8]:
            vis_w = shopee_core.get_visible_width(line)
            self.assertEqual(vis_w, 48, f"Lebar baris tidak rata: '{line}' ({vis_w} != 48)")

    # 9. Integrasi Menu Utama Tanpa Merusak Menu Lama
    def test_banner_contains_all_menus(self):
        with patch("sys.stdout", new=StringIO()) as fake_out:
            cek_misi_termux.print_banner()
            output = fake_out.getvalue()

        # Bersihkan ANSI codes agar pengujian mencocokkan teks visual murni
        clean_banner = shopee_core.ANSI_REGEX.sub("", output)

        # Menu 1 - 6 dan 0 tetap utuh dengan nomornya
        self.assertIn("1. 🎯 Cek Misi Bayar QRIS", clean_banner)
        self.assertIn("2. 🍔 Cek Voucher Shopee Food", clean_banner)
        self.assertIn("3. ⚡ Cek Keduanya Sekaligus", clean_banner)
        self.assertIn("4. 📦 MODE MASSAL / BULK CEPAT", clean_banner)
        self.assertIn("5. 👥 Kelola Multi-Worker", clean_banner)
        self.assertIn("6. ⚙️  Reset Pengaturan", clean_banner)
        self.assertIn("7. 🎟️ Klaim Voucher ShopeeFood", clean_banner)
        self.assertIn("0. 🚪 Keluar", clean_banner)

    def test_voucher_config_dual_save_and_load(self):
        cfg_file = self.dir_path / "voucher_claim_config.json"
        with patch("voucher_claim.CONFIG_CLAIM_FILE", cfg_file):
            with patch.dict(os.environ, {}, clear=True):
                # Sebelum ada file, return default 2 link
                links = voucher_claim.load_voucher_claim_configs()
                self.assertEqual(len(links), 2)
                self.assertIn("evcode=NEWFOODIES", links[0])
                self.assertIn("evcode=ONGKIRGRATIS", links[1])

                # Simpan 2 link baru
                link1 = "https://shopee.co.id/voucher/details?evcode=CUSTOM_DISCOUNT"
                link2 = "https://shopee.co.id/voucher/details?evcode=CUSTOM_ONGKIR"
                saved = voucher_claim.save_voucher_claim_configs([link1, link2])
                self.assertTrue(saved)
                self.assertTrue(cfg_file.exists())

                # Baca kembali
                loaded = voucher_claim.load_voucher_claim_configs()
                self.assertEqual(loaded, [link1, link2])

    def test_voucher_config_legacy_migration(self):
        cfg_file = self.dir_path / "voucher_claim_config.json"
        # Simpan format lama {"voucher_link": "..."}
        old_format = '{"voucher_link": "https://shopee.co.id/voucher/details?evcode=OLD_SINGLE"}'
        cfg_file.write_text(old_format, encoding="utf-8")

        with patch("voucher_claim.CONFIG_CLAIM_FILE", cfg_file):
            with patch.dict(os.environ, {}, clear=True):
                loaded = voucher_claim.load_voucher_claim_configs()
                self.assertEqual(len(loaded), 2)
                self.assertIn("OLD_SINGLE", loaded[0])
                self.assertIn("evcode=ONGKIRGRATIS", loaded[1])

    async def test_run_voucher_claim_mode_sequential_two_vouchers(self):
        client = AsyncMock()
        out_file = self.dir_path / "test_bot_responses_multi.txt"
        accounts = ["user_seq_1"]
        called_links = []

        async def mock_claim(client, account_identity, voucher_link, *args, **kwargs):
            called_links.append((account_identity, voucher_link))
            if "NEWFOODIES" in voucher_link:
                return "BERHASIL", "Voucher diskon berhasil diklaim", "OK_DISC"
            else:
                return "GAGAL", "❌ Maaf, kamu belum memenuhi kriteria", "FAIL_ONGKIR"

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with patch("sys.stdout", new=StringIO()):
                    stats = await voucher_claim.run_voucher_claim_mode(
                        client=client,
                        accounts=accounts,
                        voucher_links=[
                            voucher_claim.DEFAULT_VOUCHER_LINK,
                            voucher_claim.DEFAULT_VOUCHER_LINK_2,
                        ],
                        output_file=out_file,
                        step_delay=0.01,
                        voucher_delay=0.01,
                    )

        # Harus dipanggil 2 kali secara berurutan untuk 1 akun
        self.assertEqual(len(called_links), 2)
        self.assertEqual(called_links[0][0], "user_seq_1")
        self.assertIn("NEWFOODIES", called_links[0][1])
        self.assertEqual(called_links[1][0], "user_seq_1")
        self.assertIn("ONGKIRGRATIS", called_links[1][1])

        # Periksa output file
        saved_text = out_file.read_text(encoding="utf-8")
        self.assertIn("[Voucher 1: Diskon NewFoodies]", saved_text)
        self.assertIn("[Voucher 2: Ongkir Gratis]", saved_text)
        self.assertIn("BERHASIL", saved_text)
        self.assertIn("GAGAL", saved_text)

    def test_cli_argument_parsing_claim_mode(self):
        with patch("sys.argv", ["cek_misi_termux.py", "--mode", "claim", "--voucher-link", "https://shopee.co.id/voucher/custom"]):
            parser = argparse.ArgumentParser()
            parser.add_argument("file", nargs="?", default=None)
            parser.add_argument("--mode", choices=["misi", "food", "both", "claim"])
            parser.add_argument("--voucher-link")
            parser.add_argument("--voucher-link-2")
            args = parser.parse_args(["--mode", "claim", "--voucher-link", "https://shopee.co.id/voucher/custom", "--voucher-link-2", "https://shopee.co.id/voucher/custom2"])
            self.assertEqual(args.mode, "claim")
            self.assertEqual(args.voucher_link, "https://shopee.co.id/voucher/custom")
            self.assertEqual(args.voucher_link_2, "https://shopee.co.id/voucher/custom2")


if __name__ == "__main__":
    unittest.main()

