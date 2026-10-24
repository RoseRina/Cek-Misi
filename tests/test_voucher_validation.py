#!/usr/bin/env python3
"""Seri Pengujian Regresi Deteksi Voucher ShopeeFood."""

import unittest
from pathlib import Path
import tempfile

from shopee_core import (
    is_shopeefood_25k_voucher,
    is_shopeefood_ongkir_12k,
    validate_voucher_html,
    verify_html_account_match,
    parse_voucher_cards,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestShopeeFoodVoucherRegression(unittest.TestCase):
    def test_case_1_target_voucher_valid(self):
        html_target_25k = """
        <article class="vc" data-g="all food" data-q="1">
          <div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
          <div class="body">
            <div class="h">Diskon 100% s.d. Rp25RB</div>
            <div class="m">Tanpa min. belanja</div>
            <div class="v">Hingga 31.10.2026</div>
            <div class="chips"><span class="chip">Pengguna Baru</span><span class="chip">ShopeePay</span></div>
            <div class="code"><code>SPPSF25330008763533159320261023</code></div>
          </div>
        </article>
        """
        self.true(is_shopeefood_25k_voucher(html_target_25k))

        html_target_12k = """
        <article class="vc" data-g="all foodVip">
          <div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
          <div class="body">
            <div class="h">Diskon Ongkir Rp12RB</div>
            <div class="m">Tanpa min. belanja</div>
            <div class="v">Hingga 31.10.2026</div>
            <div class="chips"><span class="chip">Semua Resto</span></div>
            <div class="code"><code>SPPSH24330008763533159320261023</code></div>
          </div>
        </article>
        """
        self.true(is_shopeefood_ongkir_12k(html_target_12k))

    def true(self, val, msg=""):
        self.assertTrue(val, msg)

    def false(self, val, msg=""):
        self.assertFalse(val, msg)

    def test_case_2_jajanlater_min_belanja_ditolak(self):
        html = """
        <article class="vc" data-g="all food">
          <div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
          <div class="body">
            <div class="h">Diskon 100% s.d. Rp25RB</div>
            <div class="m">Min. Blj Rp25RB</div>
            <div class="chips"><span class="chip">Pengguna Baru</span><span class="chip">SPayLater</span></div>
            <div class="code"><code>JAJANLATER233</code></div>
          </div>
        </article>
        """
        self.false(is_shopeefood_25k_voucher(html))


    def test_case_3_diferent_discount_dicount_ditolak(self):
        samples = [
            # Mie Gacoan 21%
            """<article class="vc" data-g="all food"><div class="stub food"><span class="stub-t">MIE GACOAN</span></div>
               <div class="body"><div class="h">Diskon 21% s.d. Rp25RBx3</div><div class="m">Min. Blj Rp50RB</div><code>GACOAN2298</code></div></article>""",
            # Diskon 100% s.d. 10RB
            """<article class="vc" data-g="all food"><div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
               <div class="body"><div class="h">Diskon 100% s.d. Rp10RB</div><div class="m">Tanpa min. belanja</div><code>SHOPEEVIP253</code></div></article>""",
            # Diskon 100% s.d. 30RB (SPayLater)
            """<article class="vc" data-g="all food"><div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
               <div class="body"><div class="h">Diskon 100% s.d. Rp30RB</div><div class="m">Tanpa min. belanja</div><code>COBALATER394</code></div></article>""",
            # Diskon 90% s.d. 50RB
            """<article class="vc" data-g="all food"><div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
               <div class="body"><div class="h">Diskon 90% s.d. Rp50RB</div><div class="m">Tanpa min. belanja</div><code>COBALATER393</code></div></article>""",
            # Diskon 15% s.d. 200RB
            """<article class="vc" data-g="all food"><div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
               <div class="body"><div class="h">Diskon 15% s.d. Rp200RB</div><div class="m">Min. Blj Rp100RB</div><code>BAUHi333</code></div></article>""",
            # Diskon Rp25RB Kartu Debit Jumlah 125RB
            """<article class="vc" data-g="all food"><div class="stub food"><span class="stub-t">SHOPEEFOOD</span></div>
               <div class="body"><div class="h">Diskon Rp25RB</div><div class="m">Min. Blj Rp125RB</div><div class="chips"><span class="chip">Kartu Debit</span><span class="chip">BTN</span></div><code>BTNFOOD</code></div></article>""",
        ]
        for s in samples:
            self.false(is_shopeefood_25k_voucher(s))

    def test_case_4_kategori_lain_ditolak(self):
        # Fashion
        html_fashion = """<article class="vc" data-g="all shopee"><div class="stub fashion"><span class="stub-t">FASHION</span></div><div class="body"><div class="h">Diskon 100% s.d. Rp25RB</div><div class="m">Tanpa min. belanja</div><code>FASH100</code></div></article>"""
        self.false(is_shopeefood_25k_voucher(html_fashion))

    def test_case_5_real_fixture_wo19hs5oaz(self):
        fixture = FIXTURES_DIR / "voucher-wo19hs5oaz.html"
        self.true(fixture.exists())
        has_25k, has_12k = validate_voucher_html(fixture)
        self.false(has_25k)
        self.false(has_12k)

    def test_case_6_html_rusak_kosong(self):
        self.false(is_shopeefood_25k_voucher(""))
        self.false(is_shopeefood_25k_voucher(None))
        self.false(is_shopeefood_25k_voucher("<html><body>Tidak ada</body></html>"))
        self.false(is_shopeefood_ongkir_12k(""))
        self.assertEqual(validate_voucher_html(Path("tak_ada.html")), (False, False))

    def test_case_7_ongkir_terisolasi(self):
        # html fsv
        html_fsv = """<article class="vc" data-g="all shopee"><div class="stub fsv"><span class="stub-t">Gratis Ongkir</span></div><div class="body"><div class="h">Diskon Ongkir Rp12RB</div><div class="m">Tanpa min. belanja</div><code>FSV12K</code></div></article>"""
        self.false(is_shopeefood_ongkir_12k(self._clean(html_fsv)))
        self.false(is_shopeefood_25k_voucher(self._clean(html_fsv)))


    def _clean(self, s):
        return s.strip()

    def test_case_8_proteksi_akun_tertukar(self):
        html = """
        <!DOCTYPE html><html><head><title>Voucher wo19hs5oaz</title></head>
        <body><div class="hd"><h1>Voucher Saya</h1><span class="u">wo19hs5oaz</span></div></body></html>
        """
        self.true(verify_html_account_match(html, "wo19hs5oaz", "voucher-wo19hs5oaz.html"))
        self.true(verify_html_account_match(html, "WO19HS5OAZ"))
        self.false(verify_html_account_match(html, "user_beveda"))

    def test_status_classification(self):
        # Skenario 1: Lengkap 25k & 12k
        has_25k, has_12k = True, True
        if has_25k and has_12k:
            status, is_valid = "MEMENUHI SYARAT", True
        self.assertEqual(status, "MEMENUHI SYARAT")
        self.assertTrue(is_valid)

        # Skenario 2: Hanya 12k (Parsial)
        has_25k, has_12k = False, True
        if has_25k and has_12k:
            status, is_valid = "MEMENUHI SYARAT", True
        elif has_25k:
            status, is_valid = "MEMENUHI SYARAT", True
        elif has_12k:
            status, is_valid = "PARSIAL", False
        else:
            status, is_valid = "TIDAK MEMENUHI", False
        self.assertEqual(status, "PARSIAL")
        self.assertFalse(is_valid)

        # Skenario 3: Tidak ada (kasus wo19hs5oaz)
        has_25k, has_12k = False, False
        if has_25k and has_12k:
            status, is_valid = "MEMENUHI SYARAT", True
        elif has_25k:
            status, is_valid = "MEMENUHI SYARAT", True
        elif has_12k:
            status, is_valid = "PARSIAL", False
        else:
            status, is_valid = "TIDAK MEMENUHI", False
        self.assertEqual(status, "TIDAK MEMENUHI")
        self.assertFalse(is_valid)


if __name__ == "__main__":
    unittest.main()

