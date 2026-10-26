"""
Unit tests untuk Fitur Reuse Hasil Cek Mode Klaim (Opsi 7) Per-Voucher di Shopee Core & Voucher Claim.
Data sintetis/mock saja, tanpa bot Telegram sungguhan.
"""

import asyncio
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import shopee_core
import voucher_claim
import cek_misi_termux


class TestClaimReuse(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Simpan file path asli
        self.orig_claim_csv = voucher_claim.RESULTS_CLAIM_FILE
        self.orig_claim_txt = voucher_claim.DEFAULT_OUTPUT_FILE
        self.orig_core_claim_csv = shopee_core.RESULTS_CLAIM_FILE
        self.orig_core_claim_txt = shopee_core.RESULTS_CLAIM_TXT

        # Arahkan ke file sementara
        self.claim_csv = self.tmp_path / "hasil_klaim.csv"
        self.claim_txt = self.tmp_path / "bot_responses.txt"

        voucher_claim.RESULTS_CLAIM_FILE = self.claim_csv
        voucher_claim.DEFAULT_OUTPUT_FILE = self.claim_txt
        shopee_core.RESULTS_CLAIM_FILE = self.claim_csv
        shopee_core.RESULTS_CLAIM_TXT = self.claim_txt

    def tearDown(self):
        voucher_claim.RESULTS_CLAIM_FILE = self.orig_claim_csv
        voucher_claim.DEFAULT_OUTPUT_FILE = self.orig_claim_txt
        shopee_core.RESULTS_CLAIM_FILE = self.orig_core_claim_csv
        shopee_core.RESULTS_CLAIM_TXT = self.orig_core_claim_txt
        self.tmp_dir.cleanup()

    def _write_csv_record(self, account, v_idx, v_label, status, detail, date_str="2026-10-25 10:00:00"):
        file_exists = self.claim_csv.exists()
        with open(self.claim_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Tanggal & Waktu", "Akun", "Voucher Index", "Label Voucher", "Status", "Keterangan"])
            writer.writerow([date_str, account, v_idx, v_label, status, detail])

    def test_1_v1_and_v2_success_option_1_skipped_total(self):
        """1. Riwayat V1 sukses + V2 sukses, opsi [1] -> akun dilewati total, klaim TIDAK dipanggil, masuk daftar dipakai ulang."""
        self._write_csv_record("user1", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Voucher berhasil diklaim")
        self._write_csv_record("user1", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Voucher berhasil diklaim")

        with patch("builtins.input", return_value="1"):
            action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                usernames=["user1"],
                csv_file=self.claim_csv,
                log_file=self.claim_txt,
            )

        # user1 sepenuhnya sukses, tidak masuk antrean proses
        self.assertEqual(to_proc, [])
        self.assertEqual(len(reused), 1)
        self.assertEqual(reused[0]["account"], "user1")
        self.assertEqual(plan["user1"], [])

        # Jalankan runner dengan plan ini dan pastikan claim_voucher_for_account TIDAK dipanggil sama sekali
        with patch("voucher_claim.claim_voucher_for_account", new_callable=AsyncMock) as mock_claim:
            res = asyncio.run(voucher_claim.run_voucher_claim_mode(
                accounts=to_proc,
                reused_records=reused,
                account_vouchers_plan=plan,
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
            ))
            mock_claim.assert_not_called()
            self.assertEqual(res["total"], 1)
            self.assertEqual(len(res["reused_records"]), 1)

    def test_2_v1_success_v2_fail_option_1_claims_only_v2(self):
        """2. Riwayat V1 sukses + V2 gagal, opsi [1] -> fungsi klaim dipanggil HANYA untuk V2, V1 tidak diklaim ulang."""
        self._write_csv_record("user2", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Voucher berhasil diklaim")
        self._write_csv_record("user2", 2, "Voucher 2: Ongkir Gratis", "GAGAL", "Kuota habis")

        with patch("builtins.input", return_value="1"):
            action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                usernames=["user2"],
                csv_file=self.claim_csv,
                log_file=self.claim_txt,
            )

        self.assertEqual(to_proc, ["user2"])
        self.assertEqual(plan["user2"], [2])
        self.assertEqual(len(reused), 1)
        self.assertIn(1, reused[0].get("reused_vouchers", []))

        # Buktikan bahwa mock hanya dipanggil 1 kali dan untuk Voucher 2 saja
        called_links = []
        async def mock_claim(client, account_identity, voucher_link, target_bot, timeout):
            called_links.append(voucher_link)
            return "BERHASIL", "Voucher 2 berhasil", "Berhasil"

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim) as p_claim:
            asyncio.run(voucher_claim.run_voucher_claim_mode(
                client=MagicMock(),
                accounts=to_proc,
                reused_records=reused,
                account_vouchers_plan=plan,
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
                step_delay=0.0,
                voucher_delay=0.0,
            ))
            self.assertEqual(p_claim.call_count, 1)
            # Voucher 2 adalah ONGKIRGRATIS
            self.assertIn("ONGKIRGRATIS", called_links[0])
            self.assertNotIn("NEWFOODIES", called_links[0])

    def test_3_option_2_reclaims_all_vouchers_regardless_of_history(self):
        """3. Opsi [2] -> kedua voucher diklaim untuk semua akun, tanpa memandang riwayat."""
        self._write_csv_record("user3", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Voucher berhasil diklaim")
        self._write_csv_record("user3", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Voucher berhasil diklaim")

        with patch("builtins.input", return_value="2"):
            action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                usernames=["user3"],
                csv_file=self.claim_csv,
                log_file=self.claim_txt,
            )

        self.assertEqual(to_proc, ["user3"])
        self.assertEqual(plan["user3"], [1, 2])
        self.assertEqual(reused, [])

        with patch("voucher_claim.claim_voucher_for_account", new_callable=AsyncMock) as mock_claim:
            mock_claim.return_value = ("BERHASIL", "Sukses", "Berhasil")
            asyncio.run(voucher_claim.run_voucher_claim_mode(
                client=MagicMock(),
                accounts=to_proc,
                reused_records=reused,
                account_vouchers_plan=plan,
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
                step_delay=0.0,
                voucher_delay=0.0,
            ))
            self.assertEqual(mock_claim.call_count, 2)

    def test_4_option_3_selective_recheck(self):
        """4. Opsi [3] pilih 1 akun dari daftar -> akun itu diklaim kedua vouchernya, akun lain ikut aturan [1]."""
        self._write_csv_record("userA", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Voucher berhasil diklaim")
        self._write_csv_record("userA", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Voucher berhasil diklaim")

        self._write_csv_record("userB", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Voucher berhasil diklaim")
        self._write_csv_record("userB", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Voucher berhasil diklaim")

        # userA dipilih untuk recheck (nomor 1), userB tidak dipilih
        inputs = iter(["3", "1"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs)):
            action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                usernames=["userA", "userB"],
                csv_file=self.claim_csv,
                log_file=self.claim_txt,
            )

        self.assertIn("userA", to_proc)
        self.assertNotIn("userB", to_proc)
        self.assertEqual(plan["userA"], [1, 2])
        self.assertEqual(plan["userB"], [])
        self.assertIn("userA", recheck_accs)
        self.assertEqual(len(reused), 1)
        self.assertEqual(reused[0]["account"], "userB")

        # Buktikan eksekusi hanya mengklaim userA
        processed_accounts = []
        async def mock_claim(client, account_identity, voucher_link, target_bot, timeout):
            processed_accounts.append(account_identity)
            return "BERHASIL", "Sukses", "Berhasil"

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim):
            asyncio.run(voucher_claim.run_voucher_claim_mode(
                client=MagicMock(),
                accounts=to_proc,
                reused_records=reused,
                account_vouchers_plan=plan,
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
                step_delay=0.0,
                voucher_delay=0.0,
            ))
            self.assertEqual(processed_accounts, ["userA", "userA"])

    def test_5_all_success_dead_end_avoidance_menu(self):
        """5. Semua akun kedua vouchernya sukses, opsi [1] -> tampil ringkasan dipakai ulang + menu lanjutan."""
        self._write_csv_record("user5", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Voucher berhasil diklaim")
        self._write_csv_record("user5", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Voucher berhasil diklaim")

        # Sub-opsi [1]: Selesai, pakai hasil lama ini saja
        inputs = iter(["1", "1"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs)):
            action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                usernames=["user5"],
                csv_file=self.claim_csv,
                log_file=self.claim_txt,
            )
            self.assertEqual(action, "finish")
            self.assertEqual(len(reused), 1)

        # Sub-opsi [3]: Klaim ulang semua
        inputs = iter(["1", "3"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs)):
            action, to_proc, reused, recheck_accs, plan = voucher_claim.handle_claim_reuse_wizard(
                usernames=["user5"],
                csv_file=self.claim_csv,
                log_file=self.claim_txt,
            )
            self.assertEqual(action, "proceed")
            self.assertEqual(to_proc, ["user5"])
            self.assertEqual(plan["user5"], [1, 2])

    def test_6_recheck_timeout_error_preserves_old_success(self):
        """6. Klaim ulang voucher berakhir TIMEOUT/ERROR -> hasil sukses lama voucher itu dipertahankan dan ditandai."""
        self._write_csv_record("user6", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Sukses Lama", "2026-10-25 09:00:00")
        self._write_csv_record("user6", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Sukses Lama", "2026-10-25 09:00:00")

        # Mock klaim ulang voucher 1 menghasilkan TIMEOUT
        async def mock_claim(client, account_identity, voucher_link, target_bot, timeout):
            if "NEWFOODIES" in voucher_link:
                return "TIMEOUT", "Timeout menunggu balasan bot", "Timeout"
            return "BERHASIL", "Sukses baru", "Berhasil"

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim):
            res = asyncio.run(voucher_claim.run_voucher_claim_mode(
                client=MagicMock(),
                accounts=["user6"],
                account_vouchers_plan={"user6": [1, 2]},
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
                step_delay=0.0,
                voucher_delay=0.0,
            ))

        # Hasil lama voucher 1 dipertahankan dan ditandai
        self.assertEqual(len(res["preserved_records"]), 1)
        self.assertEqual(res["preserved_records"][0]["account"], "user6")
        self.assertEqual(res["preserved_records"][0]["voucher_index"], 1)

        # Di CSV baru, tidak boleh ada penimpaan V1 menjadi GAGAL/ERROR
        updated_records = voucher_claim.get_checked_claim_records(csv_file=self.claim_csv, log_file=self.claim_txt)
        user6_rec = updated_records.get("user6")
        self.assertTrue(user6_rec["v1"]["is_success"])
        self.assertTrue(user6_rec["v2"]["is_success"])

    def test_7_recheck_definitive_final_replaces_only_that_voucher(self):
        """7. Klaim ulang voucher menghasilkan hasil final baru -> hanya voucher itu yang tertimpa, voucher lain tidak berubah."""
        self._write_csv_record("user7", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Sukses Lama", "2026-10-25 09:00:00")
        self._write_csv_record("user7", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Sukses Lama", "2026-10-25 09:00:00")

        # Klaim ulang V1 definitif GAGAL (kriteria tidak memenuhi), V2 tidak dijalankan dalam plan
        async def mock_claim(client, account_identity, voucher_link, target_bot, timeout):
            return "GAGAL", "TIDAK MEMENUHI KRITERIA: Promo NewFoodies", "Gagal kriteria"

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim):
            asyncio.run(voucher_claim.run_voucher_claim_mode(
                client=MagicMock(),
                accounts=["user7"],
                account_vouchers_plan={"user7": [1]},
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
                step_delay=0.0,
                voucher_delay=0.0,
            ))

        # Periksa status di riwayat: V1 berubah jadi GAGAL, V2 TETAP BERHASIL
        updated_records = voucher_claim.get_checked_claim_records(csv_file=self.claim_csv, log_file=self.claim_txt)
        user7_rec = updated_records.get("user7")
        self.assertFalse(user7_rec["v1"]["is_success"])
        self.assertEqual(user7_rec["v1"]["status"], "GAGAL")
        self.assertTrue(user7_rec["v2"]["is_success"])
        self.assertEqual(user7_rec["v2"]["status"], "BERHASIL")

    def test_8_bot_responses_log_parser_strict(self):
        """8. Parser bot_responses.txt: baris BERHASIL V1 saja -> V1 sukses, V2 bukan sukses. Baris tanpa label/status jelas -> diabaikan."""
        log_content = (
            "[2026-10-25 10:00:00] [user8a] [Voucher 1: Diskon NewFoodies] [BERHASIL] Voucher berhasil diklaim\n"
            "[2026-10-25 10:01:00] [user8b] [Voucher 1: Diskon NewFoodies] [GAGAL] Kuota voucher habis\n"
            "[2026-10-25 10:02:00] [user8c] [BERHASIL] Tidak ada label voucher yang jelas\n"
            "[2026-10-25 10:03:00] [user8d] [Voucher 2: Ongkir Gratis] [TIMEOUT] Waktu habis\n"
        )
        self.claim_txt.write_text(log_content, encoding="utf-8")

        parsed = voucher_claim.parse_bot_responses_log(self.claim_txt)
        self.assertIn("user8a", parsed)
        self.assertTrue(parsed["user8a"]["v1"]["is_success"])
        self.assertFalse(parsed["user8a"]["v2"]["is_success"])  # V2 tidak boleh ditebak sukses!

        # user8b gagal -> bukan sukses
        self.assertIn("user8b", parsed)
        self.assertFalse(parsed["user8b"]["v1"]["is_success"])

        # user8c tanpa label voucher -> diabaikan (tidak dianggap sukses)
        if "user8c" in parsed:
            self.assertFalse(parsed["user8c"]["v1"]["is_success"])
            self.assertFalse(parsed["user8c"]["v2"]["is_success"])
        else:
            self.assertNotIn("user8c", parsed)

        # user8d timeout -> bukan sukses
        self.assertIn("user8d", parsed)
        self.assertFalse(parsed["user8d"]["v2"]["is_success"])

    def test_9_single_account_manual_prompt_and_reuse(self):
        """9. Jalur manual single-account kedua vouchernya sukses -> muncul konfirmasi reuse vs klaim ulang; memilih reuse tidak memanggil klaim."""
        self._write_csv_record("user9", 1, "Voucher 1: Diskon NewFoodies", "BERHASIL", "Sukses")
        self._write_csv_record("user9", 2, "Voucher 2: Ongkir Gratis", "BERHASIL", "Sukses")

        # Alur: Menu utama klaim -> ganti link (N) -> pilih manual (1) -> input user9 -> konfirmasi reuse (1)
        inputs = iter(["n", "1", "user9", "y", "1"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs)), \
             patch("voucher_claim.claim_voucher_for_account", new_callable=AsyncMock) as mock_claim:
            asyncio.run(voucher_claim.interactive_voucher_claim_menu())
            mock_claim.assert_not_called()

    def test_10_forced_recheck_already_claimed_treated_as_success(self):
        """10. Voucher yang dipaksa klaim ulang dibalas bot 'sudah diklaim' -> diklasifikasikan dan disimpan sebagai sukses."""
        async def mock_claim(client, account_identity, voucher_link, target_bot, timeout):
            return "GAGAL", "Voucher sudah pernah diklaim sebelumnya", "❌ Akun Anda sudah pernah mengklaim voucher ini sebelumnya."

        with patch("voucher_claim.claim_voucher_for_account", side_effect=mock_claim):
            res = asyncio.run(voucher_claim.run_voucher_claim_mode(
                client=MagicMock(),
                accounts=["user10"],
                account_vouchers_plan={"user10": [1]},
                csv_file=self.claim_csv,
                output_file=self.claim_txt,
                step_delay=0.0,
                voucher_delay=0.0,
            ))

        # Status harus diperbarui sebagai BERHASIL
        records = voucher_claim.get_checked_claim_records(csv_file=self.claim_csv, log_file=self.claim_txt)
        user10_rec = records.get("user10")
        self.assertIsNotNone(user10_rec)
        self.assertTrue(user10_rec["v1"]["is_success"])
        self.assertEqual(user10_rec["v1"]["status"], "BERHASIL")


if __name__ == "__main__":
    unittest.main()
