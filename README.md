# 🎯 Shopee Tools Bot All-in-One (Termux & PC)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3" />
  <img src="https://img.shields.io/badge/Android-Termux-black?style=for-the-badge&logo=android&logoColor=white" alt="Termux" />
  <img src="https://img.shields.io/badge/Telethon-Telegram_Client-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telethon" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" alt="Status" />
</p>

Tools otomatisasi terpadu berbasis **Python & Telethon** untuk HP Android (Termux) dan PC. Terintegrasi penuh dengan bot Telegram `@shp_tools_bot` dalam satu kesatuan sistem untuk:
1. 🎯 **Cek Misi Bayar QRIS (Check-in Koin Shopee)**: Memeriksa progres koin bayar QRIS per akun dan mencatat hasilnya rapi ke CSV.
2. 🍔 **Cek Voucher Shopee Food (Diskon 25RB & 12RB)**: Memeriksa ketersediaan voucher makanan (Diskon 100% s.d. 25RB & Diskon Ongkir 12RB tanpa minimum belanja), menyimpan akun yang lolos ke `valid_food.txt` dan rekap lengkap ke CSV.
3. ⚡ **Cek Keduanya Sekaligus**: Memeriksa Misi QRIS dan Voucher Food secara otomatis bergantian untuk setiap akun.
4. 🎟️ **Klaim Voucher ShopeeFood**: Otomatisasi proses klaim voucher ShopeeFood ke `@shp_tools_bot` secara berurutan dan mencatat respons akhir ke `bot_responses.txt`.

---

## 📑 Daftar Isi
1. [🔄 Cara Update Script](#-cara-update-script)
2. [📦 Panduan Menyiapkan Daftar Akun (Mode Bulk / Massal)](#-panduan-menyiapkan-daftar-akun-mode-bulk--massal)
3. [📱 Syarat & Persiapan Awal](#-syarat--persiapan-awal)
4. [🔑 Panduan Mendapatkan API ID & API HASH Telegram](#-panduan-mendapatkan-api-id--api-hash-telegram)
5. [📲 Panduan Lengkap Install di HP Android (Termux)](#-panduan-lengkap-install-di-hp-android-termux)
6. [🚀 Cara Menjalankan Script](#-cara-menjalankan-script)
   - [Menu Utama (Interaktif)](#1-menu-utama-interaktif)
   - [Panduan Alur Pengisian Akun (Manual vs Bulk)](#2-panduan-alur-pengisian-akun-manual-vs-bulk)
   - [Panduan Mode Massal / Bulk](#3--panduan-mode-massal--bulk-banyak-akun-sekaligus)
   - [Mode Satuan Cepat](#4--mode-satuan-cepat-cek-1-akun-langsung)
   - [Runner Khusus Voucher Food (food.py)](#5-runner-khusus-voucher-food-foodpy)
   - [Klaim Voucher ShopeeFood (voucher_claim.py)](#6-klaim-voucher-shopeefood-voucher_claimpy)
   - [Cek Ganti Nomor (Checker Only)](#7--cek-ganti-nomor-checker-only-opsi-8)
7. [📊 Penjelasan File Output & Hasil](#-penjelasan-file-output--hasil)
8. [❓ Tanya Jawab & Solusi Error (Troubleshooting)](#-tanya-jawab--solusi-error-troubleshooting)
9. [🔒 Keamanan & Privasi](#-keamanan--privasi)

---

## 🔄 Cara Update Script

### Pengguna Lama (Sudah Pernah Clone)
Cukup jalankan perintah berikut di folder project:
```bash
cd Cek-Misi
git pull origin main
```

### Pengguna Baru (Instalasi Pertama Kali)
Unduh project langsung dari GitHub:
```bash
git clone https://github.com/RoseRina/Cek-Misi.git
cd Cek-Misi
```

### Setelah Update
Jalankan ulang program seperti biasa:
```bash
python cek_misi_termux.py
```
*(Opsional)* Jalankan pengujian untuk memastikan semua modul berfungsi normal:
```bash
python -m unittest tests/test_voucher_claim.py
```

> 💡 **Catatan:** File lokal seperti sesi Telegram (`*.session`), `telegram_config.json`, dan file daftar akun tidak akan tertimpa atau hilang saat `git pull` karena sudah dilindungi oleh aturan `.gitignore`.

---

## 📦 Panduan Menyiapkan Daftar Akun (Mode Bulk / Massal)

Program ini mendukung pengecekan banyak akun sekaligus (hingga ratusan akun) di **Terminal / Termux**.

### 📝 Aturan Format Penulisan Akun (Sangat Fleksibel):
- **1 Baris untuk 1 Username** *(Sangat Direkomendasikan)*:
  ```text
  shopee_user_pertama
  shopee_user_kedua
  shopee_user_ketiga
  ```
- **Pemisah Fleksibel:** Anda juga bisa memisahkan username dengan tanda koma (`,`), titik koma (`;`), atau spasi.
- **Tanda Komentar (`#`):** Baris yang diawali tanda pagar `#` akan otomatis diabaikan oleh program (bisa digunakan untuk memberi catatan atau kategori akun).
- **Otomatis Hapus Duplikat:** Jika ada username yang tertulis dua kali, sistem otomatis membersihkannya agar tidak dicek berulang.

---

### 💻 Cara Menyiapkan File di Termux / Linux / PC:
Di dalam repositori ini sudah disediakan template file contoh:
- [`daftar_username.example.txt`](file:///c:/Users/Ferdi/Pictures/vsphone/daftar_username.example.txt) (Template umum)
- [`food.example.txt`](file:///c:/Users/Ferdi/Pictures/vsphone/food.example.txt) (Template khusus voucher food)
- [`accounts.example.txt`](file:///c:/Users/Ferdi/Pictures/vsphone/accounts.example.txt) (Template klaim voucher ShopeeFood: email, username, atau ID)

#### 1. Di HP Android (Termux):
Salin template contoh menjadi file kerja Anda:
```bash
# Salin file contoh:
cp daftar_username.example.txt daftar_username.txt

# Buka dan edit file dengan nano editor:
nano daftar_username.txt
```
* **Cara Edit di Termux:**
  1. Hapus teks contoh dan tempel/ketik daftar username akun Anda (satu per baris).
  2. Untuk menyimpan: Tekan tombol **CTRL** lalu tekan **X** di keyboard.
  3. Ketik **Y** lalu tekan **Enter**. Selesai!

#### 2. Di Komputer (Windows / PC):
1. Buka folder script ini di File Explorer.
2. Buat file baru bernama `daftar_username.txt` atau `food.txt` menggunakan **Notepad**.
3. Tempel daftar akun Anda, lalu klik **Save**.
4. Script akan otomatis mendeteksi file tersebut saat Anda memilih Menu [4] di terminal!

---

## 📱 Syarat & Persiapan Awal

Sebelum mulai, pastikan Anda sudah menyiapkan:
- [x] **HP Android** dengan koneksi internet aktif.
- [x] **Aplikasi Telegram** yang aktif di HP Anda.
- [x] **Aplikasi Termux** (WAJIB ikuti panduan download di bawah agar tidak error).
- [x] **API ID & API HASH Telegram** (Gratis dari situs resmi Telegram, ikuti panduan di bawah).

---

## 🔑 Panduan Mendapatkan API ID & API HASH Telegram

> 💡 **Untuk Orang Awam:**  
> Apa itu API ID dan API HASH? Anggap ini seperti **Kunci Resmi** dari Telegram agar Termux di HP Anda diizinkan berkomunikasi dengan bot secara aman melalui akun Telegram Anda sendiri. Langkah ini **hanya dilakukan 1 kali seumur hidup**.

Ikuti langkah demi langkah berikut secara teliti:

### Langkah 1: Buka Situs Resmi Telegram Core
Buka browser (Google Chrome disarankan) di HP atau PC Anda, lalu kunjungi:
👉 **[https://my.telegram.org](https://my.telegram.org)**

### Langkah 2: Masukkan Nomor HP Telegram
1. Masukkan nomor HP yang terdaftar di Telegram dengan format internasional.  
   *Contoh untuk Indonesia:* `+6281234567890` (gunakan tanda `+`).
2. Klik tombol **Next**.
3. Buka **aplikasi Telegram** Anda. Anda akan menerima pesan resmi dari Telegram berisi **Kode Konfirmasi (Web login code)**.
4. Salin kode tersebut, tempelkan ke kolom **Confirmation code** di browser, lalu klik **Sign In**.

### Langkah 3: Masuk ke Menu API
Setelah berhasil login, klik menu **API development tools**.

### Langkah 4: Isi Formulir Pembuatan Aplikasi
Isi formulir sederhana seperti contoh berikut:
- **App title**: Masukkan nama bebas, contoh: `ShopeeTools`
- **Short name**: Huruf kecil tanpa spasi, contoh: `shopeetools`
- **URL**: Biarkan kosong.
- **Platform**: Pilih **Android** (atau Others).
- **Description**: Biarkan kosong.
- Klik tombol **Create application**.

### Langkah 5: Salin API ID & API HASH Anda
Halaman akan menampilkan kredensial aplikasi Anda:
- **`App api_id`**: Kumpulan angka (contoh: `28374651`).
- **`App api_hash`**: Kumpulan 32 karakter kombinasi huruf dan angka (contoh: `9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d`).

> ⚠️ **PENTING:** Simpan kedua data ini di catatan HP Anda. Jangan pernah membagikan `api_hash` ke orang lain!

<details>
<summary><b>📖 Klik di sini jika mengalami kendala/error di my.telegram.org (Read More)</b></summary>
<br>

- **Muncul tulisan "ERROR" warna merah saat klik Create application?**
  - **Penyebab:** Format *Short name* mengandung spasi/karakter terlarang, atau IP internet sedang terkena limit sementara oleh Telegram.
  - **Solusi:**
    1. Pastikan *Short name* hanya huruf kecil dan angka saja (misal: `cekmisi99`).
    2. Coba ganti koneksi internet (matikan WiFi lalu gunakan paket data HP, atau sebaliknya).
    3. Buka browser dalam mode *Incognito/Samaran*.
- **Tidak menerima kode login?**
  - Kode tidak dikirim lewat SMS pulsa, melainkan dikirim langsung ke obrolan/chat di dalam **Aplikasi Telegram**.
</details>

---

## 📲 Panduan Lengkap Install di HP Android (Termux)

> ⚠️ **PERINGATAN SANGAT PENTING (BACA DULU):**  
> **JANGAN PERNAH** mengunduh Termux dari Google Play Store! Versi Play Store sudah usang (sejak 2020) dan server repository-nya rusak.  
> Gunakan Termux resmi dari **F-Droid** atau **GitHub**.

### 1. Download & Pasang Termux
Silakan unduh APK Termux terbaru melalui link resmi berikut:
- 📥 **Link Download Termux (F-Droid):** [f-droid.org/packages/com.termux](https://f-droid.org/packages/com.termux/) *(Gulir ke bawah, klik "Download APK")*
- 📥 **Link Download Alternatif (GitHub Resmi):** [Termux v0.118+ Release](https://github.com/termux/termux-app/releases) *(Pilih file termux-app_v...universal.apk)*

Pasang (install) APK tersebut di HP Android Anda, lalu buka aplikasinya.

---

### 2. Jalankan Perintah Persiapan di Termux

Ketik atau tempel perintah berikut satu per satu ke dalam Termux, lalu tekan **Enter**:

#### Step A: Berikan Izin Penyimpanan
```bash
termux-setup-storage
```
*(Pilih **Izinkan / Allow** pada pop-up di layar HP).*

#### Step B: Perbarui Paket Termux
```bash
pkg update && pkg upgrade -y
```
*(Jika muncul pilihan `[Y/n]` atau `default=N`, tekan **Enter** saja).*

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

#### Step F: Pasang Pustaka Pendukung
```bash
pip install -r requirements.txt
```

<details>
<summary><b>⚡ Ingin Cara Praktis? Jalankan Semua Perintah Sekaligus (1-Klik Copy)</b></summary>
<br>

Salin seluruh teks di bawah ini dan tempel di Termux:

```bash
pkg update && pkg upgrade -y && pkg install python git -y && git clone https://github.com/RoseRina/Cek-Misi.git && cd Cek-Misi && pip install -r requirements.txt
```
Tunggu proses hingga selesai dan muncul tanda `$` kembali.
</details>

---

## 🚀 Cara Menjalankan Script

### 1. Menu Utama (Interaktif)
Jalankan perintah:
```bash
python cek_misi_termux.py
```
Akan tampil menu interaktif:
```text
======================================================================
     🚀 SHOPEE BOT ALL-IN-ONE (TERMUX & PC AUTOMATION)
======================================================================
 1. 🎯 Cek Misi Bayar QRIS      (Check-in Koin QRIS Shopee)
 2. 🍔 Cek Voucher Shopee Food  (Diskon 25RB & Ongkir 12RB)
 3. ⚡ Cek Keduanya Sekaligus   (Misi QRIS + Voucher Food)
 4. 📦 MODE MASSAL / BULK CEPAT (Auto-Detect File .txt & Resume)
 5. 👥 Kelola Multi-Worker     (Multi-Login Akun Telegram)
 6. ⚙️  Reset Pengaturan        (Hapus Sesi & API Telegram)
 7. 🎟️ Klaim Voucher ShopeeFood (Auto-Claim Voucher ke Bot)
 8. 🔑 Cek Ganti Nomor          (Checker, Tanpa Mengubah Nomor)
 0. 🚪 Keluar
======================================================================
```

---

### 2. 🧭 Panduan Alur Pengisian Akun (Manual vs Bulk)

Setelah Anda memilih mode pemeriksaan di menu utama (misalnya opsi `[1] Cek Misi Bayar QRIS` atau opsi `[2] Cek Voucher Shopee Food`), bot akan menuntun Anda melalui 2 langkah awal yang sangat jelas:

#### 🔑 Langkah A: Pilih Metode Login Bot (`@shp_tools_bot`)
Pilih jenis identitas yang ingin Anda gunakan untuk berkomunikasi dengan bot:
- **`[1] Username / Email / ID` (Standar)**:  
  Metode bawaan. Bot Shopee akan meminta kode verifikasi/OTP jika akun belum login di bot.
- **`[2] Raw Cookie` (SPC_EC / SPC_U)**:  
  Metode login instan langsung menggunakan token sesi Shopee tanpa menunggu OTP.
- **`[3] Campuran / Otomatis`**:  
  Auto-detect otomatis per entri. Cocok jika Anda punya file campuran yang berisi sebagian username dan sebagian raw cookie.

---

#### ⚙️ Langkah B: Pilih Tipe Eksekusi Pengisian Akun
Tentukan bagaimana Anda ingin memasukkan akun:
```text
⚙️ LANGKAH B - PILIH TIPE EKSEKUSI PENGISIAN AKUN:
  [1] ⚡ Isi Manual (1 Akun)
      👉 Langsung ketik 1 akun (username atau cookie) di terminal.
      👉 Dilengkapi validasi format, preview tersamar, & konfirmasi.
  [2] 📦 Mode Massal / Bulk
      👉 Dituntun wizard 3 langkah: pilih sumber file / paste,
         panduan format sesuai metode, & preview tersamar.
Pilih tipe eksekusi [1/2, default: 2]:
```

##### ⚡ Jika Anda Memilih [1] Isi Manual (1 Akun):
1. Terminal akan menampilkan prompt pengisian sesuai metode yang dipilih pada Langkah A (misal: `Masukkan username / email / ID Shopee:` atau `Masukkan raw cookie Shopee (SPC_EC / SPC_U):`).
2. **Validasi & Peringatan Otomatis**: Jika Anda memilih metode Cookie namun tidak sengaja memasukkan username biasa (atau sebaliknya), script akan memberi peringatan dan opsi konfirmasi atau perbaikan.
3. **Preview Tersamar (Privacy Masking)**: Terminal menampilkan cuplikan akun dengan sensor/bintang (`****`) demi melindungi kerahasiaan cookie/token Anda dari intipan layar.
4. **Konfirmasi Ramah**: Ketik `Y` untuk langsung eksekusi, `r` untuk ketik ulang jika salah, atau `b` untuk membatalkan dan kembali ke pilihan tipe eksekusi.

##### 📦 Jika Anda Memilih [2] Mode Massal / Bulk:
Anda akan dituntun secara interaktif melalui 3 langkah berurutan:
1. **Langkah 1 (Pilih Sumber Akun)**:  
   - Memilih file `.txt` yang otomatis terdeteksi di folder kerja (misal `daftar_username.txt` atau `food.txt`).
   - Atau mengetik nama/path file lain.
   - Atau memilih opsi *Paste Langsung* banyak akun sekaligus ke terminal.
2. **Langkah 2 (Panduan Format & Contoh Sintetis yang Valid)**:  
   Script menampilkan aturan format yang diharapkan sesuai metode di Langkah A, lengkap dengan contoh sintetis yang aman (tanpa data pribadi/asli).
3. **Langkah 3 (Preview & Konfirmasi Sebelum Eksekusi)**:  
   Script menghitung total akun, menampilkan rincian jenis entri, serta memperlihatkan 3 akun pertama dalam format tersamar (masked). Cukup tekan `Enter` atau `Y` untuk memulai eksekusi!
4. **Penanganan Masalah yang Aman (Error Handling)**:  
   Jika nama file yang diketik salah, file kosong, atau format tidak sesuai, script **tidak akan berhenti atau crash**, melainkan memberikan pesan petunjuk jelas dan secara otomatis mengembalikan Anda ke Langkah 1.

> 🎟️ **Fitur yang Sama pada Menu [7] (Klaim Voucher ShopeeFood):**  
> Saat membuka Menu `[7]` (`voucher_claim.py`), Anda juga disuguhkan pilihan:
> - `[1] Isi Manual (1 Akun)`: Untuk klaim kilat 1 akun/email langsung tanpa repot membuat file `.txt`.
> - `[2] Mode Massal / Bulk File`: Untuk memproses antrean klaim banyak akun secara berurutan dari file `.txt`.

---

### 3. 📦 Panduan Mode Massal / Bulk (Banyak Akun Sekaligus)

Mode ini dirancang khusus untuk memproses puluhan hingga ratusan akun tanpa ribet:

- **Otomatis Deteksi File `.txt`**:  
  Cukup letakkan file akun Anda (misal `daftar_username.txt` atau `food.txt`) di folder yang sama. Script akan otomatis mendeteksi nama file dan jumlah akun di dalamnya. Anda cukup memilih nomornya saja tanpa perlu mengetik nama file!
- **Fitur Auto-Resume (Anti Mengulang dari Nol)**:  
  Jika proses pengecekan ratusan akun terputus di tengah jalan (misal Termux tertutup atau HP mati), saat dijalankan kembali script akan otomatis menawarkan:
  `Lewati akun yang sudah ada hasil suksesnya di CSV? (Y/n) [Default: Y]`  
  Akun yang sudah dicek akan otomatis dilewati dan script langsung melanjutkan akun yang tersisa!
- **Pengaturan Jeda / Delay**:  
  Untuk menghindari pembatasan Telegram (*FloodWait*), terdapat jeda aman bawaan 2.5 detik yang bisa Anda sesuaikan jika ingin lebih santai (misal 3-5 detik).

#### Jalankan Mode Bulk Cepat via Terminal:
```bash
# Cek Misi QRIS massal dari file:
python cek_misi_termux.py daftar_username.txt --mode misi

# Cek Voucher Food massal dari file:
python cek_misi_termux.py food.txt --mode food

# Klaim Voucher Food massal dari file:
python cek_misi_termux.py accounts.txt --mode claim

# Cek Keduanya sekaligus dari file dengan jeda 3 detik dan lewati akun yang sudah dicek:
python cek_misi_termux.py daftar_username.txt --mode both --resume --delay 3
```

---

### 4. ⚡ Mode Satuan Cepat (Cek 1 Akun Langsung)
Jika Anda hanya ingin mengecek atau mengklaim 1 akun cepat tanpa membuka menu:
```bash
# Cek Misi QRIS untuk 1 akun:
python cek_misi_termux.py --single username_shopee --mode misi

# Cek Voucher Food untuk 1 akun:
python food.py --single username_shopee

# Klaim Voucher ShopeeFood untuk 1 akun/email:
python cek_misi_termux.py --single email_target@gmail.com --mode claim
```

---

### 5. Runner Khusus Voucher Food (`food.py`)
Bagi Anda yang fokus mengecek voucher Shopee Food (Diskon 25RB & 12RB):
```bash
python food.py
# Atau langsung panggil file akun:
python food.py food.txt
```

---

### 6. 🎟️ Klaim Voucher ShopeeFood (`voucher_claim.py`)
Fitur otomatisasi klaim voucher ShopeeFood ke bot Telegram `@shp_tools_bot`:
1. Mengirim perintah `/account`
2. Menemukan & mengklik tombol **Claim Voucher**
3. Mengirim tautan voucher yang telah dikonfigurasi
4. Menemukan & mengklik tombol metode identifikasi (**Email / Username / ID**)
5. Mengirim identitas akun pengguna
6. Membaca respons akhir bot dan menyimpannya secara inkremental ke `bot_responses.txt`

#### Cara Menjalankan:
```bash
# Cara 1: Lewat Menu Utama interaktif (Pilih opsi [7])
python cek_misi_termux.py

# Cara 2: Langsung jalankan modul klaim voucher
python voucher_claim.py

# Cara 3: Mode CLI dengan file dan tautan voucher kustom
python cek_misi_termux.py accounts.txt --mode claim --voucher-link "https://shopee.co.id/voucher/..."
```

---

### 7. 🔑 Cek Ganti Nomor (Checker Only, Opsi 8)
Fitur otomatisasi pengecekan status kelayakan ganti nomor akun Shopee di bot Telegram `@shp_tools_bot`.

> ⚠️ **PENTING — PRINSIP KEAMANAN & PRIVASI:**  
> - **HANYA CHECKER:** Fitur ini **TIDAK PERNAH** mengganti nomor telepon akun Anda.
> - **SELALU DIBATALKAN:** Script selalu mengklik tombol **Batal** setelah klasifikasi metode verifikasi terdeteksi dari bot.
> - **TANPA OTP / PIN / PASSWORD:** Script **TIDAK PERNAH** mengirimkan kode OTP, kata sandi, ataupun PIN ShopeePay ke bot Telegram dalam kondisi apapun.
> - **SENSOR PRIVASI (MASKING):** Seluruh tampilan terminal dan pencatatan riwayat (CSV & TXT) menggunakan sensor privasi `format_account_display()`, sehingga cookie utuh **tidak pernah dibocorkan atau disimpan terbuka**.

#### Alur Pengecekan:
1. Meminta bot membuka menu `/account` dan memilih opsi **Ganti Nomor**.
2. Memilih metode identifikasi akun (Username/Email/ID atau Raw Cookie) dan menunggu prompt input identitas dari bot.
3. Mengirim identitas akun, lalu bot mengembalikan syarat verifikasi:
   - **Meminta OTP:** Script langsung mengklik tombol **Batal**, menghentikan proses akun tersebut, dan mencatat status `GAGAL` (*"Meminta OTP — dibatalkan, tidak dilanjutkan"*).
   - **Tersedia Password / PIN ShopeePay:** Script mengklik tombol **Batal**, mencatat status `SUKSES` (*"Butuh Password/PIN — dibatalkan, tercatat layak"*), dan otomatis menyimpan akun ke daftar bersih `reedem_gantinomor.txt` tanpa duplikat.
   - **Metode Verifikasi Lainnya:** Script mengklik tombol **Batal** dan mencatat status `GAGAL`.

#### Cara Menjalankan:
```bash
# Lewat Menu Utama interaktif (Pilih opsi [8]):
python cek_misi_termux.py

# Atau lewat mode CLI satuan langsung:
python cek_misi_termux.py --single user_target --mode ganti_nomor
```

<details>
<summary><b>💡 Fitur Hemat Waktu: Simpan Otomatis API ID & Hash</b></summary>
<br>

Pada saat pertama kali dijalankan, script akan menanyakan apakah Anda ingin menyimpan `API_ID` dan `API_HASH` di perangkat.  
Ketik **Y** (Ya), maka untuk hari-hari berikutnya Anda **tidak perlu repot mengetik ulang API ID & API Hash lagi**!
File konfigurasi disimpan lokal dan tidak akan terupload ke internet. Jika ingin mengganti akun, cukup pilih menu nomor **6 (Reset Pengaturan)**.
</details>

---

## 📊 Penjelasan File Output & Hasil

Bot ini otomatis menyimpan hasil dalam **2 format sekaligus** (CSV untuk Excel & TXT untuk dibaca langsung di Termux / Notepad):

| Nama File | Format | Fungsi & Keterangan |
| :--- | :--- | :--- |
| **`hasil_gabungan.txt`** / `.csv` | TXT / CSV | Laporan lengkap **Misi QRIS + Voucher Food** (Cek Keduanya). |
| **`hasil_voucher_food.txt`** / `.csv` | TXT / CSV | Laporan rinci pengecekan voucher Food (Status, Diskon 25RB, Ongkir 12RB). |
| **`hasil_cek_misi.txt`** / `.csv` | TXT / CSV | Laporan riwayat pengecekan Misi Bayar QRIS (Tanggal, Koin, Status). |
| **`hasil_ganti_nomor.txt`** / `.csv` | TXT / CSV | Laporan riwayat pengecekan kelayakan ganti nomor (Tanggal, Akun tersamar, Status, Keterangan). |
| **`reedem_gantinomor.txt`** | TXT | Kumpulan akun bersih yang **layak (terdeteksi butuh Password/PIN)** tanpa duplikat. |
| **`diskon_25rb.txt`** | TXT | Kumpulan akun yang **memiliki Diskon 25RB** (lengkap maupun parsial). |
| **`valid_food.txt`** | TXT | Kumpulan akun yang **100% lolos syarat lengkap** (Diskon 25RB + Ongkir 12RB). |
| **`misi_selesai.txt`** | TXT | Kumpulan akun yang misi bayar QRIS-nya sudah selesai atau berkoin. |
| **`bot_responses.txt`** | TXT | Catatan riwayat respons bot hasil proses klaim voucher ShopeeFood. |

### Cara Membuka Langsung di Layar Termux:
```bash
# Membaca isi file teks di layar Termux:
cat hasil_gabungan.txt
cat hasil_voucher_food.txt
cat diskon_25rb.txt

# Buka dengan scroll layar atas-bawah (tekan 'q' untuk keluar):
less -S hasil_gabungan.txt
```

### Cara Membuka / Menyalin File Hasil ke Memori HP:
Jalankan perintah ini di Termux untuk menyalin semua file hasil ke folder **Download** HP:
```bash
cp hasil_*.* valid_food.txt diskon_25rb.txt /sdcard/Download/
```
Buka folder **Download** di File Manager HP Anda, bisa langsung dibuka menggunakan aplikasi teks, **WPS Office**, atau **Excel**!

---

## ❓ Tanya Jawab & Solusi Error (Troubleshooting)

<details>
<summary><b>1. Kenapa saat ketik API_HASH atau Password Telegram tidak ada huruf yang muncul?</b></summary>
<br>
<b>Jawaban:</b> Tenang, itu normal! Di sistem Linux/Termux, setiap input kata sandi sengaja disembunyikan total (tidak ada tanda bintang <code>***</code>) demi keamanan agar tidak diintip orang lain. Ketik atau paste saja seperti biasa, lalu langsung tekan <b>Enter</b>.
</details>

<details>
<summary><b>2. Termux error "Repository under maintenance" atau "Unable to locate package"?</b></summary>
<br>
<b>Jawaban:</b> Server mirror bawaan Termux sedang sibuk. Ganti server mirror dengan cara:
<pre><code>termux-change-repo</code></pre>
Pilih <i>Main repository</i> -> tekan OK -> pilih mirror <i>Grimler</i> atau <i>Albatross</i> -> tekan OK. Lalu jalankan lagi <code>pkg update</code>.
</details>

<details>
<summary><b>3. Apa maksudnya "FloodWaitError: Telegram meminta jeda X detik"?</b></summary>
<br>
<b>Jawaban:</b> Telegram memiliki sistem anti-spam. Jika Anda mengecek terlalu banyak akun berturut-turut, Telegram akan meminta istirahat sejenak. Script ini sudah dilengkapi proteksi agar otomatis berhenti aman sehingga akun Telegram Anda tetap terlindungi dan tidak terkena pembatasan.
</details>

<details>
<summary><b>4. Bagaimana cara mengganti akun Telegram atau memasukkan API baru?</b></summary>
<br>
<b>Jawaban:</b> Cukup jalankan script lalu pilih menu nomor <b>4 (Reset Pengaturan)</b>, atau ketik perintah:
<pre><code>python cek_misi_termux.py --reset</code></pre>
Data sesi lama akan terhapus dan Anda bisa memasukkan akun baru.
</details>

---

## 🔒 Keamanan & Privasi

- File sesi Telegram (`*.session`) dan konfigurasi lokal disimpan secara lokal di perangkat Anda dan **tidak pernah dikirim ke pihak ketiga**.
- Repositori ini sudah dilengkapi aturan ketat di file `.gitignore` agar file sesi, data akun, file HTML unduhan, dan file CSV Anda **tidak pernah terunggah** ke GitHub publik.
- **Selalu jaga kerahasiaan `API_HASH` dan kode OTP Telegram Anda!**

---

<p align="center">
  Dibuat dengan ❤️ untuk kemudahan otomasi komunitas Shopee Tools.
</p>
