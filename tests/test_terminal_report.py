import csv
import os
from pathlib import Path
import re
import tempfile
import unittest

import shopee_core


class TestTerminalReport(unittest.TestCase):
    def setUp(self):
        # Bersihkan ANSI escape sequences untuk validasi konten teks
        self.ansi_re = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')

    def clean_text(self, text: str) -> str:
        return self.ansi_re.sub('', text)

    def test_classify_food_status_exhaustive(self):
        """Uji audit: Pengelompokan status ke 4 kategori mutlak tanpa tumpang tindih."""
        test_cases = [
            # 1. VALID (wajib is_valid=True DAN status='MEMENUHI SYARAT')
            ((True, "MEMENUHI SYARAT"), "VALID"),
            ((True, "memenuhi syarat"), "VALID"),
            ((True, "  MEMENUHI SYARAT  "), "VALID"),

            # 2. PARSIAL (is_valid=False DAN status='PARSIAL')
            ((False, "PARSIAL"), "PARSIAL"),
            ((False, "parsial"), "PARSIAL"),

            # 3. INVALID (is_valid=False DAN status='TIDAK MEMENUHI'/'TIDAK ADA VOUCHER')
            ((False, "TIDAK MEMENUHI"), "INVALID"),
            ((False, "tidak memenuhi"), "INVALID"),
            ((False, "TIDAK ADA VOUCHER"), "INVALID"),

            # 4. ERROR (kegagalan sistem/bot)
            ((False, "TIMEOUT"), "ERROR"),
            ((False, "FLOOD_WAIT"), "ERROR"),
            ((False, "AKUN DIBATASI / BANNED"), "ERROR"),
            ((False, "AKUN TIDAK DITEMUKAN"), "ERROR"),
            ((False, "COOKIE TIDAK VALID"), "ERROR"),
            ((False, "BUKAN MILIKMU"), "ERROR"),
            ((False, "ERROR"), "ERROR"),
            ((False, "CUSTOM_BOT_ERROR"), "ERROR"),

            # 5. Konflik Kritis (is_valid=False tapi status='MEMENUHI SYARAT' -> wajib ERROR)
            ((False, "MEMENUHI SYARAT"), "ERROR"),
            ((False, "memenuhi syarat"), "ERROR"),

            # 6. Konflik Sebaliknya (is_valid=True tapi status bukan 'MEMENUHI SYARAT' -> wajib ERROR)
            ((True, "TIDAK MEMENUHI"), "ERROR"),
            ((True, "PARSIAL"), "ERROR"),
            ((True, "TIMEOUT"), "ERROR"),
            ((True, "Diskon 25RB"), "ERROR"),

            # 7. Boolean tidak valid (None, string, int) -> wajib ERROR
            ((None, "MEMENUHI SYARAT"), "ERROR"),
            (("True", "MEMENUHI SYARAT"), "ERROR"),
            ((1, "MEMENUHI SYARAT"), "ERROR"),
            ((0, "TIDAK MEMENUHI"), "ERROR"),
            ((None, "TIDAK MEMENUHI"), "ERROR"),

            # 8. Status kosong / invalid -> wajib ERROR
            ((True, ""), "ERROR"),
            ((False, ""), "ERROR"),
            ((True, "   "), "ERROR"),
            ((False, "   "), "ERROR"),
            ((True, None), "ERROR"),
            ((False, None), "ERROR"),
            ((False, 12345), "ERROR"),
        ]

        for (is_valid, status), expected_cat in test_cases:
            with self.subTest(is_valid=is_valid, status=status):
                result = shopee_core.classify_food_status(is_valid, status)
                self.assertEqual(result, expected_cat)

    def test_conflicting_account_flow_invariance(self):
        """Uji alur akun konflik: (False, 'MEMENUHI SYARAT') masuk ERROR, tidak masuk valid_food.txt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            orig_valid = shopee_core.VALID_FOOD_FILE
            orig_csv = shopee_core.RESULTS_FOOD_FILE
            orig_txt = shopee_core.RESULTS_FOOD_TXT
            orig_25k = shopee_core.DISKON_25K_TXT

            try:
                shopee_core.VALID_FOOD_FILE = tmp_path / "valid_food.txt"
                shopee_core.RESULTS_FOOD_FILE = tmp_path / "hasil_food.csv"
                shopee_core.RESULTS_FOOD_TXT = tmp_path / "hasil_food.txt"
                shopee_core.DISKON_25K_TXT = tmp_path / "diskon_25rb.txt"

                # Akun dengan konflik: is_valid=False tapi status="MEMENUHI SYARAT"
                acc = "acc_conflict_test"
                is_valid = False
                status = "MEMENUHI SYARAT"
                detail = "Status teks bilang memenuhi tapi boolean False"

                shopee_core.save_food_result(acc, is_valid, status, detail, False, False)
                cat = shopee_core.classify_food_status(is_valid, status)

                # Harus diklasifikasikan sebagai ERROR
                self.assertEqual(cat, "ERROR")

                # Tidak boleh ada di valid_food.txt
                self.assertFalse(shopee_core.VALID_FOOD_FILE.exists())

                # Simulasi ke laporan ringkasan:
                # 1 valid, 1 invalid, 0 partial, 1 conflict (error)
                out = shopee_core.render_food_summary_box(
                    total_processed=3,
                    valid_count=1,
                    invalid_count=1,
                    partial_count=0,
                    error_count=1,
                    valid_accounts=["truly_valid_acc"],
                    box_width=48,
                )
                clean = self.clean_text(out)
                self.assertIn("Total Diproses     : 3", clean)
                self.assertIn("Memenuhi Syarat    : 1", clean)
                self.assertIn("Belum Memenuhi     : 1", clean)
                self.assertIn("Gagal / Error      : 1", clean)
                self.assertIn("└ truly_valid_acc", clean)
                self.assertNotIn("acc_conflict_test", clean)
            finally:
                shopee_core.VALID_FOOD_FILE = orig_valid
                shopee_core.RESULTS_FOOD_FILE = orig_csv
                shopee_core.RESULTS_FOOD_TXT = orig_txt
                shopee_core.DISKON_25K_TXT = orig_25k

    def test_statistic_sum_consistency_invariance(self):
        """Uji audit 1 & 3: Total Diproses = Memenuhi Syarat + Belum Memenuhi + Parsial + Gagal/Error."""
        combinations = [
            # (valid, invalid, partial, error)
            (0, 156, 0, 0),
            (3, 7, 0, 0),
            (5, 0, 0, 0),
            (2, 10, 3, 0),
            (2, 8, 0, 2),
            (0, 0, 0, 0),
            (4, 5, 2, 1),
            (10, 20, 5, 5),
            (1, 0, 0, 0),
        ]

        for v, inv, p, err in combinations:
            expected_total = v + inv + p + err
            with self.subTest(v=v, inv=inv, p=p, err=err):
                out = shopee_core.render_food_summary_box(
                    total_processed=expected_total,
                    valid_count=v,
                    invalid_count=inv,
                    partial_count=p,
                    error_count=err,
                    box_width=48,
                )
                clean = self.clean_text(out)
                # Pastikan teks Total Diproses sesuai rumus
                self.assertIn(f"Total Diproses     : {expected_total}", clean)
                self.assertIn(f"Memenuhi Syarat    : {v}", clean)
                self.assertIn(f"Belum Memenuhi     : {inv}", clean)
                if p > 0:
                    self.assertIn(f"Status Parsial     : {p}", clean)
                if err > 0:
                    self.assertIn(f"Gagal / Error      : {err}", clean)

    def test_get_visible_width_ansi_immunity(self):
        """Uji audit 2: Kode warna ANSI tidak memengaruhi perhitungan lebar."""
        base_strings = [
            "✨ LAPORAN HASIL CHECK VOUCHER ✨",
            "🎯 Total Diproses     : 156",
            "✅ Memenuhi Syarat    : 0",
            "⚠️ Belum Memenuhi     : 156",
            "★ DAFTAR AKUN MEMENUHI SYARAT ★",
            "       └ (Tidak ada)",
            "user_contoh_123",
            "╭──────────────────────────────────────────────╮",
        ]

        color_wrappers = [
            lambda s: f"\033[92m{s}\033[0m",
            lambda s: f"\033[1;93m{s}\033[0m",
            lambda s: f"\033[96m\033[1m{s}\033[0m",
            lambda s: f"\033[38;5;214m{s}\033[0m",
            lambda s: f"\033[0m{s}\033[0m",
            lambda s: f"\x1b[91m{s}\x1b[0m",
        ]

        for s in base_strings:
            expected_width = shopee_core.get_visible_width(s)
            for wrap in color_wrappers:
                colored = wrap(s)
                measured_width = shopee_core.get_visible_width(colored)
                self.assertEqual(
                    measured_width,
                    expected_width,
                    f"Lebar berbeda setelah diberi ANSI color: {colored!r} (lebar {measured_width} vs {expected_width})"
                )

    def test_narrow_terminal_all_lines_consistent_width(self):
        """Uji audit 2 & 7: Bingkai tetap rapi pada berbagai ukuran lebar terminal (38 - 60)."""
        test_widths = [38, 40, 42, 44, 48, 54, 60]
        for w in test_widths:
            with self.subTest(width=w):
                out = shopee_core.render_food_summary_box(
                    total_processed=156,
                    valid_count=1,
                    invalid_count=155,
                    valid_accounts=["user_testing_long_name"],
                    box_width=w,
                )
                box_lines = [line for line in out.splitlines() if line.startswith('\033[92m│') or line.startswith('│')]
                for line in box_lines:
                    self.assertEqual(
                        shopee_core.get_visible_width(line),
                        w,
                        f"Baris tidak konsisten pada lebar {w}: {line!r}"
                    )

    def test_long_and_unicode_usernames_do_not_break_box(self):
        """Uji audit 2 & 3: Username sangat panjang atau berisi unicode tidak merusak kotak."""
        extreme_accounts = [
            "super_duper_extremely_long_username_that_exceeds_terminal_width_1234567890",
            "shopee_🔥_promo_✨_food_🎉",
            "normal_user",
        ]
        out = shopee_core.render_food_summary_box(
            total_processed=3,
            valid_count=3,
            invalid_count=0,
            valid_accounts=extreme_accounts,
            box_width=40,  # Layar sangat sempit
        )
        # Seluruh baris kotak harus tepat 40 kolom
        box_lines = [line for line in out.splitlines() if line.startswith('\033[92m│') or line.startswith('│')]
        for line in box_lines:
            self.assertEqual(shopee_core.get_visible_width(line), 40)

    def test_scenario_1_156_processed_0_valid(self):
        """Skenario 1: Total 156 akun, 0 memenuhi syarat, 156 belum memenuhi."""
        out = shopee_core.render_food_summary_box(
            total_processed=156,
            valid_count=0,
            invalid_count=156,
            valid_accounts=[],
            box_width=48,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 156", clean)
        self.assertIn("Memenuhi Syarat    : 0", clean)
        self.assertIn("Belum Memenuhi     : 156", clean)
        self.assertIn("★ DAFTAR AKUN MEMENUHI SYARAT ★", clean)
        self.assertIn("└ (Tidak ada)", clean)
        self.assertIn("Akun valid disimpan di 'valid_food.txt'", clean)

        self.assertNotIn("Status Parsial", clean)
        self.assertNotIn("Gagal / Error", clean)

        lines = [line for line in out.splitlines() if line.startswith('\033[92m│') or line.startswith('│')]
        for line in lines:
            self.assertEqual(shopee_core.get_visible_width(line), 48)

    def test_scenario_2_partial_valid_accounts(self):
        """Skenario 2: Sebagian akun memenuhi syarat."""
        valid_accs = ["andi_shopee", "budi_food", "citra_99"]
        out = shopee_core.render_food_summary_box(
            total_processed=10,
            valid_count=3,
            invalid_count=7,
            valid_accounts=valid_accs,
            box_width=48,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 10", clean)
        self.assertIn("Memenuhi Syarat    : 3", clean)
        self.assertIn("Belum Memenuhi     : 7", clean)

        for acc in valid_accs:
            self.assertIn(f"└ {acc}", clean)

    def test_scenario_3_all_valid_accounts(self):
        """Skenario 3: Semua akun memenuhi syarat."""
        valid_accs = ["user_1", "user_2", "user_3", "user_4", "user_5"]
        out = shopee_core.render_food_summary_box(
            total_processed=5,
            valid_count=5,
            invalid_count=0,
            valid_accounts=valid_accs,
            box_width=48,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 5", clean)
        self.assertIn("Memenuhi Syarat    : 5", clean)
        self.assertIn("Belum Memenuhi     : 0", clean)
        for acc in valid_accs:
            self.assertIn(f"└ {acc}", clean)

    def test_scenario_4_partial_accounts_included(self):
        """Skenario 4: Hasil mencakup akun dengan status parsial."""
        valid_accs = ["valid_acc1", "valid_acc2"]
        out = shopee_core.render_food_summary_box(
            total_processed=15,
            valid_count=2,
            invalid_count=10,
            partial_count=3,
            valid_accounts=valid_accs,
            box_width=48,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 15", clean)
        self.assertIn("Memenuhi Syarat    : 2", clean)
        self.assertIn("Belum Memenuhi     : 10", clean)
        self.assertIn("Status Parsial     : 3", clean)

        # Total harus konsisten: 2 + 10 + 3 = 15
        self.assertEqual(2 + 10 + 3, 15)

        self.assertIn("└ valid_acc1", clean)
        self.assertIn("└ valid_acc2", clean)

    def test_scenario_5_error_accounts_included(self):
        """Skenario 5: Sebagian akun gagal diperiksa karena error."""
        valid_accs = ["sukses_1"]
        out = shopee_core.render_food_summary_box(
            total_processed=10,
            valid_count=1,
            invalid_count=7,
            error_count=2,
            valid_accounts=valid_accs,
            box_width=48,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 10", clean)
        self.assertIn("Memenuhi Syarat    : 1", clean)
        self.assertIn("Belum Memenuhi     : 7", clean)
        self.assertIn("Gagal / Error      : 2", clean)

        # Total harus konsisten: 1 + 7 + 2 = 10
        self.assertEqual(1 + 7 + 2, 10)

    def test_scenario_6_zero_accounts_processed(self):
        """Skenario 6: Tidak ada akun yang selesai diperiksa (0)."""
        out = shopee_core.render_food_summary_box(
            total_processed=0,
            valid_count=0,
            invalid_count=0,
            valid_accounts=[],
            box_width=48,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 0", clean)
        self.assertIn("Memenuhi Syarat    : 0", clean)
        self.assertIn("Belum Memenuhi     : 0", clean)
        self.assertIn("└ (Tidak ada)", clean)

    def test_scenario_7_narrow_terminal_width(self):
        """Skenario 7: Terminal memiliki lebar layar yang sempit (40 kolom)."""
        out = shopee_core.render_food_summary_box(
            total_processed=156,
            valid_count=1,
            invalid_count=155,
            valid_accounts=["nama_akun_cukup_panjang_12345"],
            box_width=40,
        )
        clean = self.clean_text(out)

        self.assertIn("Total Diproses     : 156", clean)
        self.assertIn("Memenuhi Syarat    : 1", clean)
        self.assertIn("Belum Memenuhi     : 155", clean)

        box_lines = [line for line in out.splitlines() if line.startswith('\033[92m│') or line.startswith('│')]
        for line in box_lines:
            self.assertEqual(shopee_core.get_visible_width(line), 40)

    def test_deduplication_of_usernames(self):
        """Uji username duplikat pada parameter valid_accounts."""
        out = shopee_core.render_food_summary_box(
            total_processed=5,
            valid_count=2,
            invalid_count=3,
            valid_accounts=["user_duplikat", "user_duplikat", "user_lain"],
            box_width=48,
        )
        clean = self.clean_text(out)
        self.assertEqual(clean.count("└ user_duplikat"), 1)
        self.assertEqual(clean.count("└ user_lain"), 1)

    def test_valid_food_file_saving_and_deduplication(self):
        """Uji penyimpanan hasil ke valid_food.txt dan proteksi duplikasi."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            orig_valid = shopee_core.VALID_FOOD_FILE
            orig_csv = shopee_core.RESULTS_FOOD_FILE
            orig_txt = shopee_core.RESULTS_FOOD_TXT
            orig_25k = shopee_core.DISKON_25K_TXT

            try:
                shopee_core.VALID_FOOD_FILE = tmp_path / "valid_food.txt"
                shopee_core.RESULTS_FOOD_FILE = tmp_path / "hasil_food.csv"
                shopee_core.RESULTS_FOOD_TXT = tmp_path / "hasil_food.txt"
                shopee_core.DISKON_25K_TXT = tmp_path / "diskon_25rb.txt"

                # 1. Simpan akun valid
                shopee_core.save_food_result("user_valid_1", True, "MEMENUHI SYARAT", "Diskon 25RB", True, True)
                # 2. Simpan lagi akun yang sama (duplikat)
                shopee_core.save_food_result("user_valid_1", True, "MEMENUHI SYARAT", "Diskon 25RB", True, True)
                # 3. Simpan akun parsial (tidak boleh masuk ke valid_food.txt)
                shopee_core.save_food_result("user_parsial", False, "PARSIAL", "Hanya 12RB", False, True)
                # 4. Simpan akun tidak memenuhi
                shopee_core.save_food_result("user_gagal", False, "TIDAK MEMENUHI", "Tidak ada voucher", False, False)

                # Periksa isi valid_food.txt
                self.assertTrue(shopee_core.VALID_FOOD_FILE.exists())
                valid_lines = shopee_core.VALID_FOOD_FILE.read_text(encoding="utf-8").splitlines()
                self.assertEqual(valid_lines, ["user_valid_1"])

                # Periksa CSV
                self.assertTrue(shopee_core.RESULTS_FOOD_FILE.exists())
                with shopee_core.RESULTS_FOOD_FILE.open("r", encoding="utf-8-sig") as f:
                    rows = list(csv.reader(f))
                    self.assertEqual(len(rows), 5)
                    self.assertEqual(rows[0], ["Tanggal & Waktu", "Username", "Status", "Diskon 25RB", "Ongkir 12RB", "Keterangan"])
            finally:
                shopee_core.VALID_FOOD_FILE = orig_valid
                shopee_core.RESULTS_FOOD_FILE = orig_csv
                shopee_core.RESULTS_FOOD_TXT = orig_txt
                shopee_core.DISKON_25K_TXT = orig_25k

    def test_end_to_end_saving_and_classification_flow(self):
        """Uji alur integrasi penuh: klasifikasi status hingga penulisan file valid_food.txt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            orig_valid = shopee_core.VALID_FOOD_FILE
            orig_csv = shopee_core.RESULTS_FOOD_FILE
            orig_txt = shopee_core.RESULTS_FOOD_TXT
            orig_25k = shopee_core.DISKON_25K_TXT

            try:
                shopee_core.VALID_FOOD_FILE = tmp_path / "valid_food.txt"
                shopee_core.RESULTS_FOOD_FILE = tmp_path / "hasil_food.csv"
                shopee_core.RESULTS_FOOD_TXT = tmp_path / "hasil_food.txt"
                shopee_core.DISKON_25K_TXT = tmp_path / "diskon_25rb.txt"

                test_accounts = [
                    # (username, is_valid, status, detail, has_25k, has_12k, expected_cat, should_be_in_valid_file)
                    ("user_genuine_valid", True, "MEMENUHI SYARAT", "Diskon 25RB Food", True, True, "VALID", True),
                    ("user_genuine_valid", True, "MEMENUHI SYARAT", "Duplikat akun valid", True, True, "VALID", True),
                    # Kasus is_valid=True tapi status konflik
                    ("user_conflict_timeout", True, "TIMEOUT", "Timeout bot", True, False, "ERROR", False),
                    ("user_conflict_parsial", True, "PARSIAL", "Parsial", True, False, "ERROR", False),
                    ("user_conflict_tidak_memenuhi", True, "TIDAK MEMENUHI", "Tidak memenuhi", True, False, "ERROR", False),
                    ("user_conflict_empty", True, "", "Status kosong", True, False, "ERROR", False),
                    # Kasus is_valid=False tapi status MEMENUHI SYARAT (konflik)
                    ("user_conflict_fake_valid", False, "MEMENUHI SYARAT", "Palsu", False, False, "ERROR", False),
                    # Kasus normal non-valid
                    ("user_parsial_real", False, "PARSIAL", "Hanya 12RB", False, True, "PARSIAL", False),
                    ("user_tidak_memenuhi_real", False, "TIDAK MEMENUHI", "Kosong", False, False, "INVALID", False),
                    ("user_timeout_real", False, "TIMEOUT", "Timeout bot", False, False, "ERROR", False),
                    ("user_flood_wait_real", False, "FLOOD_WAIT", "Telegram Flood", False, False, "ERROR", False),
                    ("user_banned_real", False, "AKUN DIBATASI / BANNED", "Akun limit", False, False, "ERROR", False),
                ]

                counts = {"VALID": 0, "PARSIAL": 0, "INVALID": 0, "ERROR": 0}
                valid_list = []
                total_processed = 0

                for user, is_v, st, det, h25, h12, exp_cat, in_valid_file in test_accounts:
                    # 1. Simpan ke file melalui alur resmi
                    shopee_core.save_food_result(user, is_v, st, det, h25, h12)
                    # 2. Klasifikasikan status
                    cat = shopee_core.classify_food_status(is_v, st)
                    self.assertEqual(cat, exp_cat, f"Gagal klasifikasi {user}: {cat} != {exp_cat}")
                    counts[cat] += 1
                    total_processed += 1
                    if cat == "VALID":
                        valid_list.append(user)

                # 3. Verifikasi valid_food.txt: HANYA ada 'user_genuine_valid' sebanyak 1 baris
                self.assertTrue(shopee_core.VALID_FOOD_FILE.exists())
                valid_lines = shopee_core.VALID_FOOD_FILE.read_text(encoding="utf-8").splitlines()
                self.assertEqual(valid_lines, ["user_genuine_valid"])

                # 4. Verifikasi konsistensi statistik
                self.assertEqual(counts["VALID"], 2)  # Termasuk 1 duplikat
                self.assertEqual(counts["PARSIAL"], 1)
                self.assertEqual(counts["INVALID"], 1)
                self.assertEqual(counts["ERROR"], 8)
                self.assertEqual(total_processed, 12)
                self.assertEqual(total_processed, sum(counts.values()))

                # 5. Verifikasi pembuatan laporan ringkasan
                out = shopee_core.render_food_summary_box(
                    total_processed=total_processed,
                    valid_count=counts["VALID"],
                    invalid_count=counts["INVALID"],
                    partial_count=counts["PARSIAL"],
                    error_count=counts["ERROR"],
                    valid_accounts=valid_list,
                    box_width=48,
                )
                clean = self.clean_text(out)
                self.assertIn(f"Total Diproses     : {total_processed}", clean)
                self.assertIn(f"Memenuhi Syarat    : {counts['VALID']}", clean)
                self.assertIn(f"Belum Memenuhi     : {counts['INVALID']}", clean)
                self.assertIn(f"Status Parsial     : {counts['PARSIAL']}", clean)
                self.assertIn(f"Gagal / Error      : {counts['ERROR']}", clean)
                # Username lolos tercantum, akun konflik tidak tercantum
                self.assertIn("└ user_genuine_valid", clean)
                self.assertNotIn("user_conflict", clean)
                self.assertNotIn("user_parsial", clean)
            finally:
                shopee_core.VALID_FOOD_FILE = orig_valid
                shopee_core.RESULTS_FOOD_FILE = orig_csv
                shopee_core.RESULTS_FOOD_TXT = orig_txt
                shopee_core.DISKON_25K_TXT = orig_25k

    def test_inter_session_data_consistency(self):
        """Uji simulasi 2 sesi untuk 4 skenario transisi:
        1. valid -> timeout   : status error/tidak pasti, jangan hapus data valid terakhir dari disk, tandai ERROR di sesi berjalan.
        2. valid -> invalid   : hasil negatif terkonfirmasi, hapus dari valid_food.txt & diskon_25rb.txt.
        3. valid -> parsial   : hasil parsial terkonfirmasi, hapus dari valid_food.txt, pertahankan di diskon_25rb.txt jika ada 25RB.
        4. invalid -> valid   : hasil valid terkonfirmasi, tambahkan ke valid_food.txt & diskon_25rb.txt.
        5. Akun tidak terkait : akun valid sesi 1 yang tidak dicek di sesi 2 tetap aman.
        6. Laporan sesi 2     : hanya mencatat statistik sesi 2, tidak mencampurkan data valid sesi 1.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            orig_valid = shopee_core.VALID_FOOD_FILE
            orig_csv = shopee_core.RESULTS_FOOD_FILE
            orig_txt = shopee_core.RESULTS_FOOD_TXT
            orig_25k = shopee_core.DISKON_25K_TXT

            try:
                shopee_core.VALID_FOOD_FILE = tmp_path / "valid_food.txt"
                shopee_core.RESULTS_FOOD_FILE = tmp_path / "hasil_food.csv"
                shopee_core.RESULTS_FOOD_TXT = tmp_path / "hasil_food.txt"
                shopee_core.DISKON_25K_TXT = tmp_path / "diskon_25rb.txt"

                # === SESI 1 ===
                # 4 akun valid
                shopee_core.save_food_result("user_v_to_timeout", True, "MEMENUHI SYARAT", "Diskon 25RB + Ongkir 12RB", True, True)
                shopee_core.save_food_result("user_v_to_invalid", True, "MEMENUHI SYARAT", "Diskon 25RB + Ongkir 12RB", True, True)
                shopee_core.save_food_result("user_v_to_partial_25k", True, "MEMENUHI SYARAT", "Diskon 25RB + Ongkir 12RB", True, True)
                shopee_core.save_food_result("user_v_to_partial_12k", True, "MEMENUHI SYARAT", "Diskon 25RB + Ongkir 12RB", True, True)
                shopee_core.save_food_result("user_unrelated_valid", True, "MEMENUHI SYARAT", "Diskon 25RB + Ongkir 12RB", True, True)
                # 1 akun invalid di sesi 1
                shopee_core.save_food_result("user_inv_to_valid", False, "TIDAK MEMENUHI", "Tidak ada voucher", False, False)

                # Verifikasi awal Sesi 1
                v1 = set(shopee_core.VALID_FOOD_FILE.read_text(encoding="utf-8").splitlines())
                d1 = set(shopee_core.DISKON_25K_TXT.read_text(encoding="utf-8").splitlines())
                self.assertEqual(len(v1), 5)
                self.assertNotIn("user_inv_to_valid", v1)
                self.assertEqual(len(d1), 5)
                self.assertNotIn("user_inv_to_valid", d1)

                # === SESI 2 (Pengecekan Ulang) ===
                # 1. Skenario valid -> timeout (ERROR): status tidak pasti, jangan hapus bukti valid terakhir
                shopee_core.save_food_result("user_v_to_timeout", False, "TIMEOUT", "Bot timeout", False, False)
                # 2. Skenario valid -> invalid (INVALID): hasil negatif terkonfirmasi, hapus dari file
                shopee_core.save_food_result("user_v_to_invalid", False, "TIDAK MEMENUHI", "Voucher kedaluwarsa", False, False)
                # 3. Skenario valid -> parsial (25k ada, 12k tidak ada): hapus dari valid_food, pertahankan di diskon_25rb
                shopee_core.save_food_result("user_v_to_partial_25k", False, "PARSIAL", "Hanya 25k", True, False)
                # 4. Skenario valid -> parsial (25k tidak ada, 12k ada): hapus dari valid_food dan diskon_25rb
                shopee_core.save_food_result("user_v_to_partial_12k", False, "PARSIAL", "Hanya 12k", False, True)
                # 5. Skenario invalid -> valid (VALID): berhasil lolos, tambahkan ke valid_food & diskon_25rb
                shopee_core.save_food_result("user_inv_to_valid", True, "MEMENUHI SYARAT", "Lengkap 25k + 12k", True, True)
                # Catatan: 'user_unrelated_valid' sengaja TIDAK diperiksa di sesi 2

                # Verifikasi file valid_food.txt setelah Sesi 2:
                # - user_v_to_timeout: DIPERTAHANKAN (last known valid state, timeout bukan bukti voucher hilang)
                # - user_unrelated_valid: DIPERTAHANKAN (akun tidak terkait tetap aman)
                # - user_inv_to_valid: DITAMBAHKAN (hasil valid terkonfirmasi)
                # - user_v_to_invalid: DIHAPUS (hasil negatif terkonfirmasi)
                # - user_v_to_partial_25k & 12k: DIHAPUS (bukan valid lengkap)
                v2 = set(line.strip() for line in shopee_core.VALID_FOOD_FILE.read_text(encoding="utf-8").splitlines() if line.strip())
                expected_v2 = {"user_v_to_timeout", "user_unrelated_valid", "user_inv_to_valid"}
                self.assertEqual(v2, expected_v2)

                # Verifikasi file diskon_25rb.txt setelah Sesi 2:
                # - user_v_to_timeout: DIPERTAHANKAN (last known valid)
                # - user_unrelated_valid: DIPERTAHANKAN
                # - user_inv_to_valid: DITAMBAHKAN (memiliki 25RB)
                # - user_v_to_partial_25k: DIPERTAHANKAN (terbukti punya 25RB)
                # - user_v_to_invalid: DIHAPUS (terbukti tidak punya)
                # - user_v_to_partial_12k: DIHAPUS (hanya punya 12k, tidak punya 25k)
                d2 = set(line.strip() for line in shopee_core.DISKON_25K_TXT.read_text(encoding="utf-8").splitlines() if line.strip())
                expected_d2 = {"user_v_to_timeout", "user_unrelated_valid", "user_inv_to_valid", "user_v_to_partial_25k"}
                self.assertEqual(d2, expected_d2)

                # Verifikasi laporan terminal Sesi 2:
                # Total Diproses sesi 2 = 5 akun
                # Valid = 1 ('user_inv_to_valid')
                # Invalid = 1 ('user_v_to_invalid')
                # Parsial = 2 ('user_v_to_partial_25k', 'user_v_to_partial_12k')
                # Error = 1 ('user_v_to_timeout')
                sesi_2_valid = ["user_inv_to_valid"]
                out_s2 = shopee_core.render_food_summary_box(
                    total_processed=5,
                    valid_count=1,
                    invalid_count=1,
                    partial_count=2,
                    error_count=1,
                    valid_accounts=sesi_2_valid,
                )
                clean_s2 = self.clean_text(out_s2)
                self.assertIn("Total Diproses     : 5", clean_s2)
                self.assertIn("Memenuhi Syarat    : 1", clean_s2)
                self.assertIn("Belum Memenuhi     : 1", clean_s2)
                self.assertIn("Status Parsial     : 2", clean_s2)
                self.assertIn("Gagal / Error      : 1", clean_s2)
                # Hanya 'user_inv_to_valid' yang tampil di daftar akun memenuhi syarat sesi 2
                self.assertIn("└ user_inv_to_valid", clean_s2)
                self.assertNotIn("user_v_to_timeout", clean_s2)
                self.assertNotIn("user_unrelated_valid", clean_s2)
                self.assertNotIn("user_v_to_invalid", clean_s2)

                # Verifikasi riwayat CSV: 1 header + 6 sesi 1 + 5 sesi 2 = 12 baris
                with shopee_core.RESULTS_FOOD_FILE.open("r", encoding="utf-8-sig") as f:
                    csv_rows = list(csv.reader(f))
                    self.assertEqual(len(csv_rows), 12)
            finally:
                shopee_core.VALID_FOOD_FILE = orig_valid
                shopee_core.RESULTS_FOOD_FILE = orig_csv
                shopee_core.RESULTS_FOOD_TXT = orig_txt
                shopee_core.DISKON_25K_TXT = orig_25k

    def test_diskon_25rb_invalid_category_rejection(self):
        """Uji penolakan akun has_25k=True tetapi statusnya INVALID atau ERROR ke diskon_25rb.txt."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            orig_valid = shopee_core.VALID_FOOD_FILE
            orig_csv = shopee_core.RESULTS_FOOD_FILE
            orig_txt = shopee_core.RESULTS_FOOD_TXT
            orig_25k = shopee_core.DISKON_25K_TXT

            try:
                shopee_core.VALID_FOOD_FILE = tmp_path / "valid_food.txt"
                shopee_core.RESULTS_FOOD_FILE = tmp_path / "hasil_food.csv"
                shopee_core.RESULTS_FOOD_TXT = tmp_path / "hasil_food.txt"
                shopee_core.DISKON_25K_TXT = tmp_path / "diskon_25rb.txt"

                # 1. Akun has_25k=True tapi status TIDAK MEMENUHI (INVALID)
                shopee_core.save_food_result("user_inv_25k", False, "TIDAK MEMENUHI", "Anomali", True, False)
                # 2. Akun has_25k=True tapi status TIMEOUT (ERROR)
                shopee_core.save_food_result("user_err_25k", False, "TIMEOUT", "Timeout bot", True, False)
                # 3. Akun has_25k=True status PARSIAL (Sah untuk diskon_25rb.txt)
                shopee_core.save_food_result("user_partial_ok", False, "PARSIAL", "Hanya 25k", True, False)

                d_lines = [line.strip() for line in shopee_core.DISKON_25K_TXT.read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(d_lines, ["user_partial_ok"])
                self.assertNotIn("user_inv_25k", d_lines)
                self.assertNotIn("user_err_25k", d_lines)
            finally:
                shopee_core.VALID_FOOD_FILE = orig_valid
                shopee_core.RESULTS_FOOD_FILE = orig_csv
                shopee_core.RESULTS_FOOD_TXT = orig_txt
                shopee_core.DISKON_25K_TXT = orig_25k

    def test_get_checked_usernames_resume_accuracy(self):
        """Uji akurasi fitur resume get_checked_usernames pada mode food:
        - Akun dengan status TIMEOUT / ERROR / FLOOD_WAIT tidak masuk ke checked (bisa diulang).
        - Akun dengan status sukses / tidak memenuhi masuk ke checked (dilewati).
        - Status terbaru per user di CSV menentukan apakah akun bisa diulang atau tidak.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            orig_valid = shopee_core.VALID_FOOD_FILE
            orig_csv = shopee_core.RESULTS_FOOD_FILE
            orig_txt = shopee_core.RESULTS_FOOD_TXT
            orig_25k = shopee_core.DISKON_25K_TXT

            try:
                shopee_core.VALID_FOOD_FILE = tmp_path / "valid_food.txt"
                shopee_core.RESULTS_FOOD_FILE = tmp_path / "hasil_voucher_food.csv"
                shopee_core.RESULTS_FOOD_TXT = tmp_path / "hasil_voucher_food.txt"
                shopee_core.DISKON_25K_TXT = tmp_path / "diskon_25rb.txt"

                # Tulis riwayat CSV:
                # 1. user1: TIMEOUT pada percobaan pertama
                shopee_core.save_food_result("user1", False, "TIMEOUT", "Bot timeout", False, False)
                # 2. user2: TIDAK MEMENUHI
                shopee_core.save_food_result("user2", False, "TIDAK MEMENUHI", "Tidak ada", False, False)
                # 3. user3: MEMENUHI SYARAT
                shopee_core.save_food_result("user3", True, "MEMENUHI SYARAT", "Lengkap", True, True)

                checked = shopee_core.get_checked_usernames("food")
                self.assertIn("user2", checked)
                self.assertIn("user3", checked)
                self.assertNotIn("user1", checked)  # user1 harus bisa di-resume / diulang

                # user1 diulang di sesi berikutnya dan berhasil
                shopee_core.save_food_result("user1", True, "MEMENUHI SYARAT", "Lengkap", True, True)
                checked_updated = shopee_core.get_checked_usernames("food")
                self.assertIn("user1", checked_updated)  # Sekarang sudah masuk checked
            finally:
                shopee_core.VALID_FOOD_FILE = orig_valid
                shopee_core.RESULTS_FOOD_FILE = orig_csv
                shopee_core.RESULTS_FOOD_TXT = orig_txt
                shopee_core.DISKON_25K_TXT = orig_25k

    def test_color_constants_defined(self):
        """Pastikan semua konstanta warna dan gaya ANSI terdefinisi di shopee_core."""
        for color_name in ("CYAN", "GREEN", "YELLOW", "RED", "WHITE", "MAGENTA", "BOLD", "DIM", "RESET"):
            self.assertTrue(hasattr(shopee_core, color_name), f"{color_name} harus ada di shopee_core")
            val = getattr(shopee_core, color_name)
            self.assertIsInstance(val, str)

    def test_input_manual_account_username(self):
        """Pastikan input_manual_account bekerja untuk username dan konfirmasi Y tanpa NameError."""
        from unittest.mock import patch
        with patch("builtins.input", side_effect=["test_user123", "y"]):
            res = shopee_core.input_manual_account("username")
            self.assertEqual(res, "test_user123")

    def test_input_manual_account_cookie(self):
        """Pastikan input_manual_account bekerja untuk cookie dan konfirmasi default Enter."""
        from unittest.mock import patch
        fake_cookie = "SPC_EC=token_123; SPC_U=999;"
        with patch("builtins.input", side_effect=[fake_cookie, ""]):
            res = shopee_core.input_manual_account("cookie")
            self.assertEqual(res, fake_cookie)

    def test_input_manual_account_cancel(self):
        """Pastikan input_manual_account mengembalikan None jika pengguna mengetik 'b'."""
        from unittest.mock import patch
        with patch("builtins.input", side_effect=["b"]):
            res = shopee_core.input_manual_account("username")
            self.assertIsNone(res)

    def test_bulk_format_guidance_all_modes(self):
        """Pastikan print_bulk_format_guidance berjalan lancar tanpa error formatting/warna."""
        for mode in ("username", "cookie", "auto"):
            shopee_core.print_bulk_format_guidance(mode)


if __name__ == "__main__":
    unittest.main()

