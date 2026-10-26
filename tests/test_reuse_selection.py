"""
Unit tests untuk Fitur Reuse Hasil Cek Sebelumnya dengan Opsi Pemilihan di Shopee Core & Bulk Wizard.
Data sintetis/mock saja, tanpa Telegram bot sungguhan.
"""

import asyncio
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import shopee_core
import cek_misi_termux


class TestReuseSelection(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Simpan file path asli
        self.orig_misi_csv = shopee_core.RESULTS_MISI_FILE
        self.orig_misi_txt = shopee_core.RESULTS_MISI_TXT
        self.orig_selesai_txt = shopee_core.MISI_SELESAI_TXT

        self.orig_food_csv = shopee_core.RESULTS_FOOD_FILE
        self.orig_food_txt = shopee_core.RESULTS_FOOD_TXT
        self.orig_valid_food = shopee_core.VALID_FOOD_FILE

        self.orig_both_csv = shopee_core.RESULTS_ALL_FILE
        self.orig_both_txt = shopee_core.RESULTS_ALL_TXT

        self.orig_nomor_csv = shopee_core.RESULTS_GANTI_NOMOR_FILE

        # Arahkan ke file sementara
        shopee_core.RESULTS_MISI_FILE = self.tmp_path / "hasil_misi.csv"
        shopee_core.RESULTS_MISI_TXT = self.tmp_path / "hasil_misi.txt"
        shopee_core.MISI_SELESAI_TXT = self.tmp_path / "misi_selesai.txt"

        shopee_core.RESULTS_FOOD_FILE = self.tmp_path / "hasil_food.csv"
        shopee_core.RESULTS_FOOD_TXT = self.tmp_path / "hasil_food.txt"
        shopee_core.VALID_FOOD_FILE = self.tmp_path / "valid_food.txt"

        shopee_core.RESULTS_ALL_FILE = self.tmp_path / "hasil_gabungan.csv"
        shopee_core.RESULTS_ALL_TXT = self.tmp_path / "hasil_gabungan.txt"

        shopee_core.RESULTS_GANTI_NOMOR_FILE = self.tmp_path / "hasil_ganti_nomor.csv"

    def tearDown(self):
        shopee_core.RESULTS_MISI_FILE = self.orig_misi_csv
        shopee_core.RESULTS_MISI_TXT = self.orig_misi_txt
        shopee_core.MISI_SELESAI_TXT = self.orig_selesai_txt

        shopee_core.RESULTS_FOOD_FILE = self.orig_food_csv
        shopee_core.RESULTS_FOOD_TXT = self.orig_food_txt
        shopee_core.VALID_FOOD_FILE = self.orig_valid_food

        shopee_core.RESULTS_ALL_FILE = self.orig_both_csv
        shopee_core.RESULTS_ALL_TXT = self.orig_both_txt

        shopee_core.RESULTS_GANTI_NOMOR_FILE = self.orig_nomor_csv

        self.tmp_dir.cleanup()

    def _seed_misi_csv(self, accounts_and_status: list[tuple[str, str, int]]):
        """Membuat baris CSV awal untuk mode misi."""
        with shopee_core.RESULTS_MISI_FILE.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Tanggal & Waktu", "Username", "Koin Bayar QRIS", "Status", "Keterangan"])
            for acc, status, coins in accounts_and_status:
                writer.writerow(["2026-10-25 10:00:00", acc, coins, status, f"Detail {status}"])

    def test_1_option_1_all_successful_dead_end_avoidance(self):
        """1. CSV berisi 6 akun sukses, pengguna pilih [1] -> 0 akun diproses,
        ringkasan menampilkan 6 dipakai ulang, dan menu 'semua sudah dipakai ulang' muncul."""
        accounts = [f"test_user_{i}" for i in range(1, 7)]
        self._seed_misi_csv([(acc, "SELESAI", 1000) for acc in accounts])

        # Input [1] lalu pada menu semua dipakai ulang pilih [1] (Selesai, pakai hasil lama ini saja)
        with patch("builtins.input", side_effect=["1", "1"]):
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                accounts, "misi", "otp"
            )

        self.assertEqual(action, "finish")
        self.assertEqual(to_proc, [])
        self.assertEqual(len(reused), 6)
        self.assertEqual(len(recheck), 0)

        # Pastikan ringkasan mencakup 6 akun dan dalam keadaan tersamar / format display yang valid
        summary_str = shopee_core.render_combined_execution_summary(
            mode="misi",
            total_all=6,
            total_processed=0,
            new_success=0,
            new_fail=0,
            new_error=0,
            reused_records=reused,
            preserved_records=[],
            auth_method="otp",
        )
        self.assertIn("DIPAKAI ULANG DARI HASIL LAMA (6 akun):", summary_str)
        self.assertIn("Total Akun Sukses / Layak :", summary_str)
        for acc in accounts:
            display_label = shopee_core.format_account_display(acc, "otp")
            self.assertIn(display_label, summary_str)

    def test_2_option_2_recheck_all(self):
        """2. CSV berisi 6 akun sukses, pengguna pilih [2] -> 6 akun masuk antrean, tidak ada yang dipakai ulang."""
        accounts = [f"test_user_{i}" for i in range(1, 7)]
        self._seed_misi_csv([(acc, "SELESAI", 1000) for acc in accounts])

        with patch("builtins.input", side_effect=["2"]):
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                accounts, "misi", "otp"
            )

        self.assertEqual(action, "proceed")
        self.assertEqual(len(to_proc), 6)
        self.assertEqual(to_proc, accounts)
        self.assertEqual(len(reused), 0)
        self.assertEqual(recheck, set(accounts))

    def test_3_option_3_select_per_account(self):
        """3. CSV berisi 6 akun sukses, pengguna pilih [3] lalu pilih nomor 1,3 ->
        2 akun masuk antrean, 4 dipakai ulang, dan daftar dipakai ulang menampilkan akun yang benar (tersamar)."""
        raw_cookie = "SPC_EC=secret_ec_token_123456789; SPC_U=998877; shopee_token=abc"
        accounts = ["user_alpha_1", raw_cookie, "user_alpha_3", "user_alpha_4", "user_alpha_5", "user_alpha_6"]
        self._seed_misi_csv([(acc, "SELESAI", 1000) for acc in accounts])

        with patch("builtins.input", side_effect=["3", "1,3"]):
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                accounts, "misi", "cookie"
            )

        self.assertEqual(action, "proceed")
        self.assertEqual(len(to_proc), 2)
        self.assertEqual(to_proc, ["user_alpha_1", "user_alpha_3"])
        self.assertEqual(len(reused), 4)
        reused_accounts = [r["account"] for r in reused]
        self.assertEqual(reused_accounts, [raw_cookie, "user_alpha_4", "user_alpha_5", "user_alpha_6"])
        self.assertEqual(recheck, {"user_alpha_1", "user_alpha_3"})

        # Periksa masking pada akun cookie: raw cookie tidak boleh tampil telanjang
        cookie_rec = next(r for r in reused if r["account"] == raw_cookie)
        self.assertNotIn("secret_ec_token_123456789", cookie_rec["display"])
        self.assertIn("Cookie", cookie_rec["display"])

    def test_4_option_3_invalid_input_retry(self):
        """4. Pilihan [3] dengan input nomor di luar rentang / format salah -> ditolak dan diminta ulang, tidak crash."""
        accounts = [f"user_beta_{i}" for i in range(1, 7)]
        self._seed_misi_csv([(acc, "SELESAI", 1000) for acc in accounts])

        # Input: "3", lalu coba "99", lalu "abc", lalu "0", lalu "1,999", lalu berhasil "1,2"
        inputs = ["3", "99", "abc", "0", "1,999", "1,2"]
        with patch("builtins.input", side_effect=inputs):
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                accounts, "misi", "otp"
            )

        self.assertEqual(action, "proceed")
        self.assertEqual(len(to_proc), 2)
        self.assertEqual(to_proc, ["user_beta_1", "user_beta_2"])
        self.assertEqual(len(reused), 4)
        self.assertEqual(recheck, {"user_beta_1", "user_beta_2"})

    def test_5_recheck_timeout_preserves_old_success(self):
        """5. Cek ulang yang menghasilkan TIMEOUT -> hasil sukses lama dipertahankan dan ditandai di ringkasan."""
        acc = "user_recheck_timeout"
        self._seed_misi_csv([(acc, "SELESAI", 1500)])

        # Pastikan akun tercatat sukses sebelumnya
        checked_before = shopee_core.get_checked_usernames("misi")
        self.assertIn(acc, checked_before)

        # Mock telegram client & check_one_mission agar menghasilkan TIMEOUT
        mock_client = MagicMock()
        mock_check = AsyncMock(return_value=(None, "TIMEOUT", "Bot tidak merespons dalam 15s"))

        with patch("shopee_core.check_one_mission", mock_check), \
             patch("asyncio.sleep", AsyncMock()):
            # Jalankan run_misi_mode dengan recheck_targets={acc}
            asyncio.run(
                cek_misi_termux.run_misi_mode(
                    client=mock_client,
                    usernames=[acc],
                    auth_method="otp",
                    step_delay=0,
                    reused_records=[],
                    recheck_targets={acc}
                )
            )

        # Pastikan CSV TIDAK ditimpa dengan status TIMEOUT (sehingga status sukses lama tetap menjadi yang terakhir atau tidak tercemar)
        records = shopee_core.get_checked_accounts_records("misi")
        self.assertIn(acc, records)
        self.assertEqual(records[acc]["status"], "SELESAI")

        checked_after = shopee_core.get_checked_usernames("misi")
        self.assertIn(acc, checked_after)

    def test_6_recheck_definitive_final_overwrites_old_success(self):
        """6. Cek ulang yang menghasilkan hasil final baru -> hasil baru menggantikan hasil lama."""
        acc = "user_recheck_final"
        self._seed_misi_csv([(acc, "SELESAI", 2000)])

        mock_client = MagicMock()
        # Bot membalas definitif baru: TIDAK ADA MISI QRIS
        mock_check = AsyncMock(return_value=(None, "TIDAK ADA MISI QRIS", "Tidak ada tugas QRIS aktif"))

        with patch("shopee_core.check_one_mission", mock_check), \
             patch("asyncio.sleep", AsyncMock()):
            asyncio.run(
                cek_misi_termux.run_misi_mode(
                    client=mock_client,
                    usernames=[acc],
                    auth_method="otp",
                    step_delay=0,
                    reused_records=[],
                    recheck_targets={acc}
                )
            )

        # Baris baru harus tersimpan di CSV dan menimpa status lama
        records = shopee_core.get_checked_accounts_records("misi")
        self.assertIn(acc, records)
        self.assertEqual(records[acc]["status"], "TIDAK ADA MISI QRIS")
        self.assertNotEqual(records[acc]["status"], "SELESAI")

    def test_7_mixed_accounts_automatic_queue(self):
        """7. Daftar akun campuran (sebagian sudah sukses, sebagian belum) ->
        akun yang belum sukses otomatis masuk antrean tanpa perlu dipilih."""
        # 4 akun sudah sukses
        seeded = [f"seeded_{i}" for i in range(1, 5)]
        self._seed_misi_csv([(s, "SELESAI", 500) for s in seeded])

        # Total 6 akun: 4 sudah sukses + 2 baru
        all_accounts = seeded + ["new_acc_1", "new_acc_2"]

        # Kasus A: Pengguna pilih [1] (Pakai hasil lama)
        with patch("builtins.input", side_effect=["1"]):
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                all_accounts, "misi", "otp"
            )

        self.assertEqual(action, "proceed")
        # 2 akun baru otomatis masuk to_proc
        self.assertEqual(to_proc, ["new_acc_1", "new_acc_2"])
        # 4 akun sukses masuk reused
        self.assertEqual(len(reused), 4)
        self.assertEqual(recheck, set())

        # Kasus B: Pengguna pilih [3] dan pilih akun sukses ke-2 ('seeded_2') untuk dicek ulang
        with patch("builtins.input", side_effect=["3", "2"]):
            action, to_proc, reused, recheck = shopee_core.handle_reuse_or_recheck_wizard(
                all_accounts, "misi", "otp"
            )

        self.assertEqual(action, "proceed")
        # to_proc berisi 2 akun baru + 1 akun lama yang dipilih ('seeded_2')
        self.assertEqual(set(to_proc), {"new_acc_1", "new_acc_2", "seeded_2"})
        self.assertEqual(len(reused), 3)
        self.assertEqual(recheck, {"seeded_2"})


if __name__ == "__main__":
    unittest.main()
