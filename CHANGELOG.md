# Changelog

Seluruh riwayat pembaruan fitur dan perbaikan pada project ini dirangkum secara ringkas di bawah ini.

## Terbaru
- **25 Okt 2026**: Perbaikan false positive deteksi voucher ShopeeFood dengan validasi ketat per elemen kartu (`<article class="vc">`), menolak SPayLater/bank/kedaluwarsa/belum mulai. Penyelarasan alur pengisian akun: panduan interaktif manual (1 akun dengan masking/validasi) vs bulk (wizard 3 langkah terstruktur) pada menu utama dan menu klaim voucher (opsi 7), serta dokumentasi pembaruan di README.md.
- **25 Okt 2026 (`171802d`)**: Opsi 7 sekarang mengklaim 2 voucher berurutan per akun: Voucher 1 Diskon (`NEWFOODIES`) lalu Voucher 2 Ongkir Gratis (`ONGKIRGRATIS`). Menu bisa mengganti Tautan 1 / Tautan 2 / keduanya, hasil tercatat rapi per voucher di `bot_responses.txt`, dan mode CLI mendukung `--voucher-link-2`.

## Sebelumnya
- **25 Okt 2026 (`02af073`)**: Perbaikan deteksi respons perantara bot (`⏳ Klaim voucher...`) agar tidak dianggap hasil akhir; polling dilanjutkan hingga status final bot muncul (termasuk jika pesan diedit bot) dan batas waktu balasan akhir ditingkatkan menjadi 30 detik.
