# 🎯 Cek-Misi (Bayar QRIS Shopee Bot Automation)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3" />
  <img src="https://img.shields.io/badge/Android-Termux-black?style=for-the-badge&logo=android&logoColor=white" alt="Termux" />
  <img src="https://img.shields.io/badge/Telethon-Telegram_Client-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telethon" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" alt="Status" />
</p>

Script otomatisasi berbasis **Python & Telethon** yang dirancang khusus untuk dijalankan di **HP Android (Termux)** maupun PC. Script ini berfungsi untuk memeriksa status misi **Bayar QRIS / Misi Check-in** pada bot Telegram `@shp_tools_bot` secara cepat, baik untuk satu akun maupun banyak akun Shopee sekaligus, dan menyimpan laporannya rapi ke file **CSV (Excel)**.

---

## 📑 Daftar Isi
1. [📱 Syarat & Persiapan Awal](#-syarat--persiapan-awal)
2. [🔑 Panduan Mendapatkan API ID & API HASH Telegram](#-panduan-mendapatkan-api-id--api-hash-telegram)
3. [📲 Panduan Lengkap Install di HP Android (Termux)](#-panduan-lengkap-install-di-hp-android-termux)
4. [🚀 Cara Menjalankan Script](#-cara-menjalankan-script)
5. [📊 Cara Membuka Hasil Cek (CSV) di HP](#-cara-membuka-hasil-cek-csv-di-hp)
6. [❓ Tanya Jawab & Solusi Error (Troubleshooting)](#-tanya-jawab--solusi-error-troubleshooting)
7. [🔒 Keamanan & Privasi](#-keamanan--privasi)

---

## 📱 Syarat & Persiapan Awal

Sebelum mulai, pastikan Anda sudah menyiapkan:
- [x] **HP Android** dengan koneksi internet aktif.
- [x] **Aplikasi Telegram** yang aktif dan login di nomor Anda.
- [x] **Aplikasi Termux** (WAJIB ikuti cara download di bawah agar tidak error).
- [x] **API ID & API HASH Telegram** (Gratis dari situs resmi Telegram).

---

## 🔑 Panduan Mendapatkan API ID & API HASH Telegram

> 💡 **Untuk Orang Awam:**  
> Apa itu API ID dan API HASH? Anggap saja ini seperti **Kunci Resmi** dari Telegram agar Termux di HP Anda diizinkan berkomunikasi dengan bot secara aman melalui akun Telegram Anda. Langkah ini **hanya dilakukan 1 kali saja seumur hidup**.

Ikuti langkah demi langkah berikut secara teliti:

### Langkah 1: Buka Situs Resmi Telegram Core
Buka browser (Google Chrome disarankan) di HP atau PC Anda, lalu kunjungi:
👉 **[https://my.telegram.org](https://my.telegram.org)**

### Langkah 2: Masukkan Nomor HP Telegram
1. Masukkan nomor HP yang terdaftar di Telegram dengan awalan kode negara.  
   *Contoh untuk Indonesia:* `+6281234567890` (gunakan tanda `+`).
2. Klik tombol **Next**.
3. Buka **aplikasi Telegram** Anda. Anda akan menerima pesan resmi dari Telegram berisi **Kode Konfirmasi (Web login code)**.
4. Salin kode tersebut, tempelkan ke kolom **Confirmation code** di browser, lalu klik **Sign In**.

### Langkah 3: Masuk ke Menu API
Setelah berhasil login, Anda akan melihat beberapa menu.
- Klik menu **API development tools**.

### Langkah 4: Isi Formulir Pembuatan Aplikasi
Anda akan diminta mengisi formulir sederhana. Jangan bingung, isi saja seperti contoh berikut:
- **App title**: Masukkan nama bebas, contoh: `CekMisiShopee`
- **Short name**: Masukkan huruf kecil tanpa spasi, contoh: `cekmisi`
- **URL**: Kosongkan saja (biarkan kosong).
- **Platform**: Pilih **Android** (atau Others).
- **Description**: Kosongkan saja.
- Klik tombol **Create application**.

### Langkah 5: Salin API ID & API HASH Anda
Setelah tombol diklik, halaman akan menampilkan data aplikasi Anda:
- **`App api_id`**: Kumpulan angka (contoh: `28374651`).
- **`App api_hash`**: Kumpulan 32 karakter kombinasi huruf dan angka (contoh: `9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d`).

> ⚠️ **PENTING:** Simpan kedua data ini di catatan HP (Keep/Notepad). Jangan pernah membagikan `api_hash` ke orang asing!

<details>
<summary><b>📖 Klik di sini jika mengalami kendala/error di my.telegram.org (Read More)</b></summary>
<br>

- **Muncul tulisan "ERROR" warna merah saat klik Create application?**
  - **Penyebab:** Format *Short name* mengandung spasi/simbol, atau IP internet Anda sedang terkena limit sementara oleh Telegram.
  - **Solusi:**
    1. Pastikan *Short name* hanya huruf kecil dan angka saja (misal: `cekmisi123`).
    2. Coba ganti koneksi internet (matikan WiFi lalu gunakan data seluler, atau sebaliknya).
    3. Jika tetap error, coba gunakan mode *Incognito/Samaran* di Google Chrome.
- **Tidak menerima kode login?**
  - Kode tidak dikirim via SMS biasa, melainkan dikirim langsung ke obrolan/chat di dalam **Aplikasi Telegram**. Cek folder chat Telegram Anda.
</details>

---

## 📲 Panduan Lengkap Install di HP Android (Termux)

> ⚠️ **PERINGATAN SANGAT PENTING (BACA DULU):**  
> **JANGAN PERNAH** mengunduh Termux dari Google Play Store! Versi di Play Store sudah tidak diperbarui sejak tahun 2020 dan sudah rusak/error.  
> Gunakan Termux versi resmi dari **F-Droid** atau **GitHub**.

### 1. Download & Pasang Termux
Silakan download file APK Termux terbaru melalui salah satu link resmi berikut:
- 📥 **Link Download Termux (F-Droid):** [f-droid.org/packages/com.termux](https://f-droid.org/packages/com.termux/) *(Gulir ke bawah, klik "Download APK")*
- 📥 **Link Download Alternatif (GitHub Resmi):** [Termux v0.118+ Release](https://github.com/termux/termux-app/releases) *(Pilih file termux-app_v...universal.apk)*

Pasang (install) APK tersebut di HP Android Anda, lalu buka aplikasinya.

---

### 2. Jalankan Perintah Persiapan di Termux

Salin dan tempel perintah berikut satu per satu ke dalam Termux, lalu tekan **Enter** pada keyboard HP Anda:

#### Step A: Berikan Izin Penyimpanan
```bash
termux-setup-storage
```
*(Akan muncul jendela pop-up di layar HP, pilih **Izinkan / Allow**).*

#### Step B: Perbarui Sistem Termux
```bash
pkg update && pkg upgrade -y
```
*(Jika muncul pertanyaan dengan pilihan `[Y/n]` atau `default=N`, cukup tekan **Enter** saja).*

#### Step C: Pasang Python dan Git
```bash
pkg install python git -y
```

#### Step D: Unduh Script Cek-Misi dari GitHub
```bash
git clone https://github.com/RoseRina/Cek-Misi.git
```

#### Step E: Masuk ke Folder Script
```bash
cd Cek-Misi
```

#### Step F: Pasang Pustaka Pendukung (Telethon)
```bash
pip install -r requirements.txt
```

<details>
<summary><b>⚡ Ingin Cara Praktis? Jalankan Semua Perintah Sekaligus (1-Klik Copy)</b></summary>
<br>

Jika Anda ingin langsung menginstall semuanya sekaligus tanpa mengetik satu per satu, salin kode panjang di bawah ini lalu tempel di Termux:

```bash
pkg update && pkg upgrade -y && pkg install python git -y && git clone https://github.com/RoseRina/Cek-Misi.git && cd Cek-Misi && pip install -r requirements.txt
```
Tunggu hingga proses unduhan selesai dan muncul tanda `$` kembali.
</details>

---

## 🚀 Cara Menjalankan Script

Pastikan Anda sudah berada di dalam folder `Cek-Misi` (jika baru membuka Termux, ketik `cd Cek-Misi` lalu Enter).

### 🔹 Mode 1: Masukkan Username Satu Per Satu (Interaktif)
Jalankan perintah:
```bash
python cek_misi_termux.py
```

**Alur yang akan tampil di layar:**
1. **Masukkan username Shopee**: Ketik username Shopee Anda satu per baris.
2. Jika sudah selesai memasukkan daftar username, tekan **Enter** pada baris kosong.
3. Masukkan **API_ID** Anda lalu tekan Enter.
4. Masukkan **API_HASH** Anda lalu tekan Enter.  
   *(Catatan: Teks API Hash tidak akan terlihat di layar saat diketik/paste, ini normal).*
5. Masukkan **Nomor HP Telegram** (contoh: `+6281234567890`).
6. Masukkan **Kode OTP login Telegram** yang masuk ke aplikasi Telegram Anda.
7. Masukkan **Password Verifikasi Dua Langkah (2FA)** jika akun Anda mengaktifkannya (jika tidak ada, langsung Enter).
8. Script akan otomatis memproses dan memeriksa misi secara bergantian!

---

### 🔹 Mode 2: Masukkan Banyak Username Otomatis (Pakai File TXT)
Jika Anda memiliki puluhan atau ratusan akun, Anda bisa menyiapkan file teks berisi daftar username.

1. Buat atau edit file `daftar_username.txt`:
   ```bash
   nano daftar_username.txt
   ```
2. Ketik atau tempel username Shopee Anda (satu baris satu username):
   ```text
   user_shopee_1
   user_shopee_2
   user_shopee_3
   ```
3. Tekan **Ctrl + X**, lalu ketik **Y**, lalu tekan **Enter** untuk menyimpan.
4. Jalankan script dengan memanggil file tersebut:
   ```bash
   python cek_misi_termux.py daftar_username.txt
   ```

<details>
<summary><b>💡 Tips Login Telegram Berikutnya (Tidak Perlu Input Ulang)</b></summary>
<br>

Setelah Anda berhasil login pertama kali, script akan membuat file sesi bernama `cek_misi_termux.session`.  
Untuk penggunaan berikutnya, Anda **TIDAK PERLU** lagi memasukkan nomor telepon dan kode OTP Telegram, script akan langsung masuk otomatis!
</details>

---

## 📊 Cara Membuka Hasil Cek (CSV) di HP

Semua riwayat dan hasil pengecekan otomatis tersimpan di file **`hasil_cek_misi.csv`**.

Format tabel di dalam file CSV:
| Tanggal & Waktu | Username | Koin Bayar QRIS | Status | Keterangan |
| :--- | :--- | :--- | :--- | :--- |
| 2026-10-23 19:30:00 | akun_shopee_1 | 2.500 | SELESAI | Bayar QRIS: 2.500 koin |
| 2026-10-23 19:30:15 | akun_shopee_2 | 1.000 | BELUM SELESAI | Bayar QRIS: 1.000 koin |

### Cara Memindahkan File CSV ke Memori HP (Folder Download):
Ketik perintah ini di Termux:
```bash
cp hasil_cek_misi.csv /sdcard/Download/
```
Sekarang buka aplikasi **File Manager / Pengelola File** di HP Anda, buka folder **Download**, dan buka file `hasil_cek_misi.csv` menggunakan **WPS Office**, **Microsoft Excel**, atau **Google Spreadsheet**.

---

## ❓ Tanya Jawab & Solusi Error (Troubleshooting)

<details>
<summary><b>1. Kenapa saat ketik API_HASH atau Password Telegram tidak ada huruf yang muncul?</b></summary>
<br>
<b>Jawaban:</b> Tenang, itu bukan rusak! Di sistem Linux/Termux, setiap input kata sandi sengaja disembunyikan total (tidak keluar tanda bintang <code>***</code>) demi keamanan agar tidak diintip orang lain. Ketik atau paste saja seperti biasa, lalu langsung tekan <b>Enter</b>.
</details>

<details>
<summary><b>2. Termux error "Repository under maintenance" atau "Unable to locate package"?</b></summary>
<br>
<b>Jawaban:</b> Server mirror bawaan Termux sedang sibuk. Ubah server mirror dengan cara:
<pre><code>termux-change-repo</code></pre>
Pilih <i>Main repository</i> -> tekan OK -> pilih mirror <i>Grimler</i> atau <i>Albatross</i> -> tekan OK. Lalu jalankan lagi <code>pkg update</code>.
</details>

<details>
<summary><b>3. Apa maksudnya "FloodWaitError: Telegram meminta jeda X detik"?</b></summary>
<br>
<b>Jawaban:</b> Telegram memiliki sistem anti-spam. Jika Anda mengecek terlalu banyak akun dalam waktu singkat, Telegram akan meminta istirahat beberapa detik/menit. Script ini sudah dilengkapi proteksi agar otomatis berhenti aman sehingga akun Telegram Anda tetap aman dan tidak dibatasi.
</details>

<details>
<summary><b>4. Bagaimana jika ingin ganti nomor Telegram atau login ulang dari awal?</b></summary>
<br>
<b>Jawaban:</b> Cukup hapus file sesi lama dengan perintah:
<pre><code>rm cek_misi_termux.session</code></pre>
Saat Anda menjalankan script lagi, Anda akan diminta login kembali dengan nomor baru.
</details>

<details>
<summary><b>5. Muncul tulisan "File daftar tidak ditemukan"?</b></summary>
<br>
<b>Jawaban:</b> Pastikan nama file yang Anda ketik sama persis dengan nama file aslinya di dalam folder. Cek nama file yang ada dengan perintah <code>ls</code>.
</details>

---

## 🔒 Keamanan & Privasi

- File konfigurasi sesi Telegram (`*.session`) dan data pribadi Anda **tidak pernah** dikirim ke server manapun selain langsung ke server resmi Telegram via pustaka Telethon.
- Repositori ini sudah dilengkapi aturan `.gitignore` agar file sesi dan file pribadi Anda tidak akan pernah terunggah ke GitHub publik.
- **Selalu jaga kerahasiaan `API_HASH` dan kode OTP Telegram Anda dari siapapun!**

---

<p align="center">
  Dibuat dengan ❤️ untuk memudahkan pengecekan misi Shopee secara otomatis.
</p>
