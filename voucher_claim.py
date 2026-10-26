#!/usr/bin/env python3
"""Modul Klaim Voucher ShopeeFood Otomatis (@shp_tools_bot).

Mendukung otomatisasi klaim voucher ShopeeFood melalui bot Telegram:
1. Mengirim perintah /account
2. Mengklik tombol 'Claim Voucher'
3. Mengirim link voucher yang telah dikonfigurasi
4. Memilih metode identifikasi akun (Email / Username / ID)
5. Mengirim identitas akun dan menangkap balasan bot
6. Menyimpan riwayat incremental ke file output (bot_responses.txt)
7. Menampilkan ringkasan akhir terminal berbingkai rapi
"""

import asyncio
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
from typing import List, Optional, Tuple, Union, Dict, Set, Any

from telethon.errors import FloodWaitError

import shopee_core

# Inisialisasi pewarnaan terminal
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

DEFAULT_BOT = "@shp_tools_bot"
DEFAULT_VOUCHER_LINK = (
    "https://shopee.co.id/voucher/details?evcode=NEWFOODIES&infocuan&"
    "promotionId=1535384308957184&signature=9d5740e39dedc95c5aeb12ae7ed5455e1163bcbb2f659624052c33b633baf853"
)
DEFAULT_VOUCHER_LINK_2 = (
    "https://shopee.co.id/voucher/details?evcode=ONGKIRGRATIS&infocuan&"
    "promotionId=1535384308826112&signature=b675a8f1d1b61eb8bec9d565cfe99871b7d45c8aef6bb88dc0d7a5c8f1372205"
)
DEFAULT_VOUCHER_LINKS = [DEFAULT_VOUCHER_LINK, DEFAULT_VOUCHER_LINK_2]
DEFAULT_ACCOUNTS_FILE = Path("accounts.txt")
DEFAULT_OUTPUT_FILE = Path("bot_responses.txt")
RESULTS_CLAIM_FILE = Path("hasil_klaim.csv")
CONFIG_CLAIM_FILE = Path("voucher_claim_config.json")


def check_telegram_credentials_configured() -> bool:
    """Memeriksa apakah API ID dan API HASH Telegram sudah tersimpan atau dikonfigurasi."""
    api_id, api_hash = shopee_core.load_credentials()
    return bool(api_id and api_hash)


def load_voucher_claim_configs(config_file: Optional[Union[str, Path]] = None) -> List[str]:
    """Mengambil daftar tautan voucher tersimpan dari environment atau file konfigurasi lokal.

    Format file baru: {"voucher_links": [link1, link2]}
    Kompatibilitas mundur: jika file lama hanya {"voucher_link": "..."}, jadikan voucher 1
    dan padukan dengan default voucher 2 (ONGKIRGRATIS).
    Jika SHOPEE_VOUCHER_LINK ada di env, itu menggantikan voucher 1 saja.
    """
    cfg_path = Path(config_file) if config_file else CONFIG_CLAIM_FILE
    links: List[str] = []

    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(data.get("voucher_links"), list) and data["voucher_links"]:
                links = [str(x).strip() for x in data["voucher_links"] if str(x).strip()]
            elif "voucher_link" in data:
                old_link = str(data.get("voucher_link", "")).strip()
                if old_link:
                    links = [old_link, DEFAULT_VOUCHER_LINK_2]
        except Exception:
            pass

    if not links:
        links = [DEFAULT_VOUCHER_LINK, DEFAULT_VOUCHER_LINK_2]

    # Environment variable SHOPEE_VOUCHER_LINK menggantikan voucher 1 saja
    env_link = os.environ.get("SHOPEE_VOUCHER_LINK", "").strip()
    if env_link:
        if links:
            links[0] = env_link
        else:
            links = [env_link, DEFAULT_VOUCHER_LINK_2]

    return links


def save_voucher_claim_configs(
    voucher_links: List[str],
    config_file: Optional[Union[str, Path]] = None,
) -> bool:
    """Menyimpan daftar tautan voucher ke file konfigurasi lokal dengan format baru {"voucher_links": [link1, link2]}."""
    clean_links = [str(l).strip() for l in voucher_links if str(l).strip()]
    if not clean_links:
        return False

    cfg_path = Path(config_file) if config_file else CONFIG_CLAIM_FILE
    try:
        data = {
            "voucher_links": clean_links,
            "voucher_link": clean_links[0],
        }
        cfg_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def load_voucher_claim_config(config_file: Optional[Union[str, Path]] = None) -> str:
    """Mengambil tautan voucher 1 tersimpan (wrapper kompatibilitas mundur)."""
    configs = load_voucher_claim_configs(config_file=config_file)
    return configs[0] if configs else DEFAULT_VOUCHER_LINK


def save_voucher_claim_config(
    voucher_link: str,
    config_file: Optional[Union[str, Path]] = None,
) -> bool:
    """Menyimpan tautan voucher 1 ke file konfigurasi lokal (wrapper kompatibilitas mundur)."""
    clean_link = (voucher_link or "").strip()
    if not clean_link:
        return False
    current_configs = load_voucher_claim_configs(config_file=config_file)
    v2 = current_configs[1] if len(current_configs) > 1 else DEFAULT_VOUCHER_LINK_2
    return save_voucher_claim_configs([clean_link, v2], config_file=config_file)


def read_claim_accounts(file_path: Union[str, Path]) -> Tuple[List[str], int]:
    """Membaca daftar identitas akun (email, username, atau ID) dari file teks.

    Mengabaikan baris kosong dan komentar (#), serta menghapus duplikasi
    dengan tetap mempertahankan urutan awal input.
    Mengembalikan (daftar_akun_unik, jumlah_duplikat_dihapus).
    """
    path_obj = Path(file_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"File '{path_obj.name}' tidak ditemukan!")

    raw_lines = path_obj.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    accounts = []
    seen = set()
    duplicates_count = 0

    for line in raw_lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        case_key = cleaned.casefold()
        if case_key in seen:
            duplicates_count += 1
            continue
        seen.add(case_key)
        accounts.append(cleaned)

    return accounts, duplicates_count


def sanitize_log_text(text: str) -> str:
    """Membersihkan informasi sensitif (API HASH, OTP, password, token, nomor telepon) dari teks log."""
    if not text:
        return ""
    # Mask 32-karakter hex (seperti API HASH atau token session)
    cleaned = re.sub(r"\b[0-9a-fA-F]{32}\b", "[REDACTED_HASH]", text)
    # Mask nomor telepon internasional
    cleaned = re.sub(r"(?:\+?62|08)\d{8,13}", "[REDACTED_PHONE]", cleaned)
    # Mask OTP / kode numerik 5-6 digit terisolasi
    cleaned = re.sub(r"\b(?<!\w)\d{5,6}(?!\w)\b", "[REDACTED_CODE]", cleaned)
    return cleaned


def is_intermediate_response(text: str) -> bool:
    """Mengecek apakah teks respons bot merupakan pesan perantara / placeholder
    yang masih dalam antrean / pemrosesan dan bukan hasil akhir klaim."""
    raw_str = (text or "").strip()
    if not raw_str:
        return False
    clean = " ".join(raw_str.casefold().split())
    if not clean:
        return False

    # KECUALI jika mengandung kata hasil akhir:
    final_indicators = (
        "berhasil",
        "gagal",
        "maaf",
        "tidak memenuhi",
        "sudah diklaim",
        "telah diklaim",
        "kuota",
        "expired",
        "kadaluwarsa",
        "kedaluwarsa",
        "tidak ditemukan",
        "tidak valid",
        "failed",
    )
    if any(k in clean for k in final_indicators):
        return False

    # 1. Mengandung ⏳ atau ⌛
    if "⏳" in raw_str or "⌛" in raw_str:
        return True

    # 2. Mengandung kata 'klaim' dan berakhir dengan '...' atau '…'
    if "klaim" in clean and (clean.endswith("...") or clean.endswith("…")):
        return True

    # 3. Mengandung kata proses/tunggu/antre
    intermediate_indicators = (
        "memproses",
        "sedang diproses",
        "diproses",
        "mohon tunggu",
        "harap tunggu",
        "tunggu sebentar",
        "antre",
        "antri",
        "loading",
        "processing",
        "please wait",
    )
    if any(k in clean for k in intermediate_indicators):
        return True

    return False


def classify_claim_response(text: str) -> Tuple[str, str]:
    """Mengklasifikasikan respons bot ke salah satu dari 3 kategori mutlak:
    1. 'BERHASIL'        : Klaim sukses diverifikasi
    2. 'GAGAL'           : Klaim ditolak / kuota habis / syarat tidak terpenuhi / sudah diklaim
    3. 'TIDAK DIKETAHUI' : Respons tidak dikenal, pesan perantara, atau terjadi anomali
    """
    raw_str = (text or "").strip()
    clean = " ".join(raw_str.casefold().split())
    if not clean:
        return "TIDAK DIKETAHUI", "Bot tidak memberikan teks balasan"

    # 1. Deteksi pesan perantara / loading (tidak boleh dianggap sukses/gagal final)
    if is_intermediate_response(raw_str):
        return "TIDAK DIKETAHUI", "Respons perantara bot (masih dalam proses, bukan hasil akhir)"

    has_negative_indicators = any(k in clean for k in ("tidak", "belum", "gagal", "bukan", "maaf", "❌", "failed"))

    # 2. Kriteria Berhasil (HANYA jika tidak ada indikator negatif)
    if not has_negative_indicators:
        success_keywords = (
            "berhasil diklaim",
            "claim voucher berhasil",
            "voucher berhasil",
            "berhasil klaim",
            "berhasil ditambahkan",
            "voucher telah masuk",
            "voucher masuk",
            "klaim sukses",
            "sukses klaim",
            "claimed successfully",
            "selamat! voucher",
        )
        if any(k in clean for k in success_keywords):
            return "BERHASIL", "Voucher berhasil diklaim ke akun"

        if "berhasil" in clean:
            return "BERHASIL", "Voucher berhasil diklaim"

    # 3. Kriteria Gagal (Penolakan Kelayakan / Kriteria / Syarat)
    if (
        "belum memenuhi kriteria" in clean
        or "tidak memenuhi kriteria" in clean
        or "belum memenuhi syarat" in clean
        or "tidak memenuhi syarat" in clean
        or "belum memenuhi" in clean
        or "tidak memenuhi" in clean
        or "tidak berhak" in clean
        or "ineligible" in clean
        or "not eligible" in clean
        or ("kriteria" in clean and any(w in clean for w in ("belum", "tidak", "kurang", "bukan")))
        or ("syarat" in clean and any(w in clean for w in ("belum", "tidak", "kurang", "bukan")))
    ):
        return "GAGAL", "TIDAK MEMENUHI KRITERIA: Belum/tidak memenuhi kriteria atau syarat klaim"

    # Kriteria Gagal Lainnya
    if any(k in clean for k in ("sudah pernah", "sudah diklaim", "already claimed", "telah diklaim", "pernah diklaim")):
        return "GAGAL", "Voucher sudah pernah diklaim sebelumnya"

    if "kuota" in clean and any(w in clean for w in ("habis", "penuh", "limit", "kosong", "mencapai batas")):
        return "GAGAL", "Kuota klaim voucher habis"

    if any(k in clean for k in ("expired", "kadaluwarsa", "kedaluwarsa", "telah berakhir")):
        return "GAGAL", "Voucher sudah kedaluwarsa"

    if any(k in clean for k in ("limit", "dibatasi", "banned", "terbatas")):
        return "GAGAL", "Akun atau kuota terkena limit"

    if any(k in clean for k in (
        "tidak ditemukan",
        "not found",
        "user tidak valid",
        "akun tidak valid",
        "tidak terdaftar",
        "user tidak ditemukan",
        "akun tidak terdaftar",
        "user tidak terdaftar",
    )):
        return "GAGAL", "Identitas akun tidak ditemukan atau tidak valid"

    if any(k in clean for k in ("belum punya nomor hp", "belum punya nomor", "tidak punya nomor hp", "tidak memiliki nomor hp")):
        return "GAGAL", "Akun belum memiliki nomor HP"

    if any(k in clean for k in (
        "cookie tidak valid",
        "invalid cookie",
        "cookie expired",
        "cookie kadaluarsa",
        "cookie sudah kadaluwarsa",
        "format cookie salah",
    )):
        return "GAGAL", "Cookie tidak valid atau sudah kedaluwarsa"

    if any(k in clean for k in ("voucher tidak valid", "voucher salah", "invalid voucher", "voucher tidak ditemukan")):
        return "GAGAL", "Tautan atau kode voucher tidak valid"

    if "maaf" in clean and any(w in clean for w in ("tidak", "belum", "gagal", "batal")):
        return "GAGAL", "Klaim voucher ditolak bot"

    if "gagal" in clean or "failed" in clean:
        return "GAGAL", "Gagal mengklaim voucher (ditolak bot)"

    if "❌" in raw_str:
        detail_txt = raw_str.replace("❌", "").strip() or raw_str
        return "GAGAL", detail_txt

    snippet = sanitize_log_text(raw_str.replace("\n", " "))
    if len(snippet) > 60:
        snippet = snippet[:57] + "..."
    return "TIDAK DIKETAHUI", f"Respons bot tidak dikenal: {snippet}"


def get_voucher_label(link: str, index: int = 0) -> str:
    """Mengembalikan label deskriptif untuk tautan voucher."""
    lower = (link or "").casefold()
    if "newfoodies" in lower:
        return "Diskon NewFoodies"
    elif "ongkir" in lower:
        return "Ongkir Gratis"
    elif "diskon" in lower or "food" in lower:
        return "Diskon Food"
    return f"Voucher {index + 1}"


def save_claim_result(
    account: str,
    status: str,
    detail: str,
    raw_response: str,
    output_file: Union[str, Path] = DEFAULT_OUTPUT_FILE,
    voucher_label: Optional[str] = None,
    voucher_index: Optional[int] = None,
    csv_file: Union[str, Path] = RESULTS_CLAIM_FILE,
):
    """Menyimpan hasil klaim voucher secara bertahap (incremental append) ke:
    1. File log teks (bot_responses.txt) untuk kompatibilitas riwayat lama.
    2. File terstruktur CSV (hasil_klaim.csv) untuk pencatatan per voucher yang rapi.
    Menyaring seluruh informasi sensitif (cookie/token/password/PIN mentah).
    """
    out_path = Path(output_file)
    csv_path = Path(csv_file)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sanitized_resp = sanitize_log_text(raw_response or "")
    clean_resp = " ".join(sanitized_resp.split())
    if len(clean_resp) > 200:
        clean_resp = clean_resp[:197] + "..."

    sanitized_acc = sanitize_log_text(account or "-")
    # Jika akun berupa cookie mentah, samarkan untuk tampilan log/CSV
    if shopee_core.detect_auth_method(account) == "cookie":
        sanitized_acc = shopee_core.format_account_display(account, "cookie")

    v_tag = f" [{voucher_label}]" if voucher_label else ""
    line = f"[{now_str}] [{sanitized_acc}]{v_tag} [{status}] {detail} | Respons: {clean_resp or '-'}\n"
    try:
        with out_path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

    # Simpan juga ke CSV terstruktur hasil_klaim.csv
    try:
        file_exists = csv_path.exists() and csv_path.stat().st_size > 0
        v_idx_val = voucher_index
        if v_idx_val is None:
            lbl_lower = (voucher_label or "").casefold()
            if "voucher 2" in lbl_lower or "ongkir" in lbl_lower:
                v_idx_val = 2
            else:
                v_idx_val = 1
        v_lbl_val = voucher_label or f"Voucher {v_idx_val}"

        with csv_path.open("a", newline="", encoding="utf-8-sig") as f_csv:
            writer = csv.writer(f_csv)
            if not file_exists:
                writer.writerow(["Tanggal & Waktu", "Akun", "Voucher Index", "Label Voucher", "Status", "Keterangan"])
            writer.writerow([
                now_str,
                sanitized_acc,
                v_idx_val,
                v_lbl_val,
                status,
                detail or "-",
            ])
    except Exception:
        pass


def parse_bot_responses_log(log_path: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, Any]]:
    """Mengekstrak riwayat klaim dari bot_responses.txt (backward compatibility).
    Hanya baris dengan label voucher jelas (Voucher 1 / Voucher 2) DAN status BERHASIL
    yang dihitung sebagai sukses untuk voucher tersebut. Baris tanpa label voucher jelas,
    tanpa status jelas, atau berstatus GAGAL/TIMEOUT/TIDAK DIKETAHUI TIDAK boleh dianggap sukses.
    """
    path = Path(log_path) if log_path else DEFAULT_OUTPUT_FILE
    records: Dict[str, Dict[str, Any]] = {}
    if not path.is_file():
        return records

    line_re = re.compile(
        r"^\[(?P<date>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+"
        r"\[(?P<account>[^\]]+)\]"
        r"(?:\s+\[(?P<voucher>[^\]]+)\])?"
        r"\s+\[(?P<status>[^\]]+)\]\s+"
        r"(?P<detail>[^|]+?)"
        r"(?:\s+\|\s+Respons:\s*(?P<resp>.*))?$"
    )

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return records

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = line_re.match(line)
        if not m:
            continue
        date_str = m.group("date").strip()
        account = m.group("account").strip()
        v_tag = (m.group("voucher") or "").strip()
        status = m.group("status").strip()
        detail = m.group("detail").strip()

        v_idx = None
        v_label = ""
        v_tag_lower = v_tag.casefold()
        if "voucher 1" in v_tag_lower or ("diskon" in v_tag_lower and "ongkir" not in v_tag_lower) or "newfoodies" in v_tag_lower:
            v_idx = 1
            v_label = v_tag or "Voucher 1: Diskon"
        elif "voucher 2" in v_tag_lower or "ongkir" in v_tag_lower:
            v_idx = 2
            v_label = v_tag or "Voucher 2: Ongkir Gratis"

        if v_idx is None:
            # Baris tanpa label voucher yang jelas tidak dihitung sebagai sukses V1/V2
            continue

        is_success = (status.upper() == "BERHASIL")

        if account not in records:
            records[account] = {
                "account": account,
                "display": account,
                "v1": {"status": "-", "detail": "-", "date": "-", "is_success": False, "voucher_label": "Voucher 1: Diskon", "source": "none"},
                "v2": {"status": "-", "detail": "-", "date": "-", "is_success": False, "voucher_label": "Voucher 2: Ongkir Gratis", "source": "none"},
                "conflicts": [],
            }

        v_key = f"v{v_idx}"
        records[account][v_key] = {
            "status": status,
            "detail": detail,
            "date": date_str,
            "is_success": is_success,
            "voucher_label": v_label,
            "source": "log",
        }

    return records


def get_checked_claim_records(
    csv_file: Optional[Union[str, Path]] = None,
    log_file: Optional[Union[str, Path]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Membaca riwayat hasil klaim dengan pendekatan 2 lapis:
    Lapis 1: Log lama bot_responses.txt (backward compatibility).
    Lapis 2: File terstruktur baru hasil_klaim.csv (ke depan).
    Resolusi konflik: jika tanggal di CSV baru lebih baru atau sama, CSV menang dan konflik dicatat.
    """
    csv_path = Path(csv_file) if csv_file else RESULTS_CLAIM_FILE
    log_path = Path(log_file) if log_file else DEFAULT_OUTPUT_FILE

    # 1. Baca log lama
    records = parse_bot_responses_log(log_path)

    # 2. Baca CSV baru
    if csv_path.is_file():
        try:
            with csv_path.open("r", encoding="utf-8-sig", errors="ignore") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 5:
                        date_str = row[0].strip()
                        user = row[1].strip()
                        if not user:
                            continue
                        try:
                            v_idx = int(row[2].strip())
                        except (ValueError, TypeError):
                            v_idx = 1 if "1" in row[2] else (2 if "2" in row[2] else None)
                        if v_idx not in (1, 2):
                            continue
                        v_label = row[3].strip() if len(row) > 3 else f"Voucher {v_idx}"
                        st = row[4].strip() if len(row) > 4 else ""
                        ket = row[5].strip() if len(row) > 5 else "-"

                        # Bot balasan "sudah pernah diklaim" / already claimed dihitung sukses
                        is_succ = (st.upper() == "BERHASIL") or ("sudah pernah" in ket.casefold())

                        if user not in records:
                            records[user] = {
                                "account": user,
                                "display": user,
                                "v1": {"status": "-", "detail": "-", "date": "-", "is_success": False, "voucher_label": "Voucher 1: Diskon", "source": "none"},
                                "v2": {"status": "-", "detail": "-", "date": "-", "is_success": False, "voucher_label": "Voucher 2: Ongkir Gratis", "source": "none"},
                                "conflicts": [],
                            }

                        v_key = f"v{v_idx}"
                        old_entry = records[user][v_key]

                        # Resolusi konflik jika sudah ada dari log lama
                        if old_entry.get("source") == "log" and old_entry.get("date") != "-":
                            if old_entry.get("is_success") != is_succ:
                                if date_str >= old_entry["date"]:
                                    records[user]["conflicts"].append(
                                        f"Konflik Voucher {v_idx} pada akun '{user}': "
                                        f"Log lama ({old_entry['status']}, {old_entry['date']}) vs "
                                        f"CSV baru ({st}, {date_str}) -> CSV baru dimenangkan."
                                    )
                                    records[user][v_key] = {
                                        "status": st,
                                        "detail": ket,
                                        "date": date_str,
                                        "is_success": is_succ,
                                        "voucher_label": v_label,
                                        "source": "csv",
                                    }
                                else:
                                    records[user]["conflicts"].append(
                                        f"Konflik Voucher {v_idx} pada akun '{user}': "
                                        f"CSV ({st}, {date_str}) vs Log lebih baru ({old_entry['status']}, {old_entry['date']}) -> Log dimenangkan."
                                    )
                            else:
                                if date_str >= old_entry["date"]:
                                    records[user][v_key] = {
                                        "status": st,
                                        "detail": ket,
                                        "date": date_str,
                                        "is_success": is_succ,
                                        "voucher_label": v_label,
                                        "source": "csv",
                                    }
                        else:
                            records[user][v_key] = {
                                "status": st,
                                "detail": ket,
                                "date": date_str,
                                "is_success": is_succ,
                                "voucher_label": v_label,
                                "source": "csv",
                            }
        except Exception:
            pass

    # 3. Hitung properti gabungan
    for user, rec in list(records.items()):
        v1 = rec["v1"]
        v2 = rec["v2"]
        v1_succ = v1.get("is_success", False)
        v2_succ = v2.get("is_success", False)
        rec["is_fully_success"] = (v1_succ and v2_succ)
        rec["is_partially_success"] = (v1_succ != v2_succ)
        rec["has_any_success"] = (v1_succ or v2_succ)
        rec["is_success"] = rec["is_fully_success"]
        rec["status"] = f"V1: {v1['status']} | V2: {v2['status']}"
        rec["detail"] = f"V1: {v1['detail']} | V2: {v2['detail']}"
        rec["date"] = v2["date"] if v2["date"] != "-" else v1["date"]

        lower_user = user.casefold()
        if lower_user not in records:
            records[lower_user] = rec

    return records


def render_claim_combined_summary(
    total_accounts: int,
    total_tasks: int,
    newly_results: Optional[List[Dict[str, Any]]] = None,
    reused_records: Optional[List[Dict[str, Any]]] = None,
    preserved_records: Optional[List[Dict[str, Any]]] = None,
    conflicts: Optional[List[str]] = None,
    csv_file: Union[str, Path] = RESULTS_CLAIM_FILE,
    log_file: Union[str, Path] = DEFAULT_OUTPUT_FILE,
    auth_method: str = "username",
) -> str:
    """Menghasilkan teks laporan akhir 3 kelompok dengan hitungan PER VOUCHER (tugas):
    [A] Baru diklaim di run ini (total tugas, sukses, gagal, timeout/error per voucher)
    [B] Dipakai ulang dari hasil lama (daftar per akun per voucher)
    [C] Total gabungan per voucher dan per akun
    """
    newly = newly_results or []
    reused = reused_records or []
    preserved = preserved_records or []
    c_list = conflicts or []

    # Hitung per-voucher tugas baru
    v1_new_succ = 0
    v1_new_fail = 0
    v1_new_err = 0

    v2_new_succ = 0
    v2_new_fail = 0
    v2_new_err = 0

    for item in newly:
        for v in item.get("vouchers", []):
            idx = v.get("voucher_index", 1)
            st = v.get("status", "").upper()
            if st == "BERHASIL":
                if idx == 1:
                    v1_new_succ += 1
                else:
                    v2_new_succ += 1
            elif any(err in st for err in ("TIMEOUT", "ERROR", "TIDAK DIKETAHUI", "FLOOD")):
                if idx == 1:
                    v1_new_err += 1
                else:
                    v2_new_err += 1
            else:
                if idx == 1:
                    v1_new_fail += 1
                else:
                    v2_new_fail += 1

    new_tasks_total = (v1_new_succ + v1_new_fail + v1_new_err) + (v2_new_succ + v2_new_fail + v2_new_err)
    preserved_count = len(preserved)

    # Hitung tugas dipakai ulang
    reused_v1_count = 0
    reused_v2_count = 0
    for r in reused:
        reused_v = r.get("reused_vouchers", [1, 2] if r.get("is_fully_success") else ([1] if r.get("v1", {}).get("is_success") else ([2] if r.get("v2", {}).get("is_success") else [])))
        if 1 in reused_v:
            reused_v1_count += 1
        if 2 in reused_v:
            reused_v2_count += 1

    total_reused_tasks = reused_v1_count + reused_v2_count
    total_success_tasks = (v1_new_succ + v2_new_succ) + total_reused_tasks + preserved_count

    full_success_accounts = 0
    for r in reused:
        if r.get("is_fully_success"):
            full_success_accounts += 1
    for item in newly:
        v_list = item.get("vouchers", [])
        if len(v_list) == 2 and all(v.get("status") == "BERHASIL" for v in v_list):
            full_success_accounts += 1
        elif len(v_list) == 1 and v_list[0].get("status") == "BERHASIL":
            acc_name = item.get("account")
            if any(r.get("account") == acc_name for r in reused):
                full_success_accounts += 1

    lines = []
    lines.append(f"{CYAN}{BOLD}======================================================================{RESET}")
    lines.append(f"📊 {BOLD}LAPORAN RINGKASAN AKHIR KLAIM VOUCHER (REKAPITULASI GABUNGAN){RESET}")
    lines.append(f"{CYAN}======================================================================{RESET}")
    lines.append(f"🎯 Total Keseluruhan: {BOLD}{total_accounts} akun{RESET} | {BOLD}{total_tasks} tugas voucher{RESET}\n")

    lines.append(f"{CYAN}[A] HASIL DIKLAIM DI RUN INI ({new_tasks_total} tugas voucher):{RESET}")
    if new_tasks_total == 0:
        lines.append(f"    ℹ️  Tidak ada tugas klaim baru di run ini (semua memakai hasil sukses sebelumnya).")
    else:
        lines.append(f"    🏷️  Voucher 1 (Diskon) : {GREEN}{BOLD}{v1_new_succ}{RESET} sukses, {YELLOW}{v1_new_fail}{RESET} gagal, {RED}{v1_new_err}{RESET} timeout/error")
        lines.append(f"    🚚 Voucher 2 (Ongkir) : {GREEN}{BOLD}{v2_new_succ}{RESET} sukses, {YELLOW}{v2_new_fail}{RESET} gagal, {RED}{v2_new_err}{RESET} timeout/error")
        if preserved_count > 0:
            lines.append(f"    🛡️  Hasil Lama Dipertahankan: {GREEN}{BOLD}{preserved_count}{RESET} tugas (klaim ulang timeout/error)")

    lines.append(f"\n{CYAN}[B] DIPAKAI ULANG DARI HASIL LAMA ({total_reused_tasks} tugas voucher):{RESET}")
    if total_reused_tasks == 0:
        lines.append(f"    ℹ️  Tidak ada voucher yang memakai hasil lama (semua diklaim di run ini).")
    else:
        for idx, r in enumerate(reused, 1):
            disp = r.get("display") or shopee_core.format_account_display(r.get("account", "-"), auth_method)
            v1_info = f"V1: {r.get('v1', {}).get('status', '-')} ({r.get('v1', {}).get('date', '-')})"
            v2_info = f"V2: {r.get('v2', {}).get('status', '-')} ({r.get('v2', {}).get('date', '-')})"
            lines.append(f"    [{idx}] {disp} | {v1_info} | {v2_info}")

    lines.append(f"\n{CYAN}[C] TOTAL REKAPITULASI GABUNGAN:{RESET}")
    lines.append(f"    🏆 Total Tugas Sukses   : {GREEN}{BOLD}{total_success_tasks}{RESET} dari {total_tasks} tugas voucher")
    lines.append(f"    👥 Akun Sukses Penuh    : {GREEN}{BOLD}{full_success_accounts}{RESET} dari {total_accounts} akun")
    lines.append(f"    📁 Rincian data tersimpan di: {Path(csv_file).name} (CSV) & {Path(log_file).name} (Log)")

    if c_list:
        lines.append(f"\n{YELLOW}⚠️  KONFLIK SUMBER RIWAYAT TERCATAT ({len(c_list)}):{RESET}")
        for c in c_list:
            lines.append(f"    • {c}")

    lines.append(f"{CYAN}======================================================================{RESET}")
    return "\n".join(lines)


def print_claim_combined_summary(
    total_accounts: int,
    total_tasks: int,
    newly_results: Optional[List[Dict[str, Any]]] = None,
    reused_records: Optional[List[Dict[str, Any]]] = None,
    preserved_records: Optional[List[Dict[str, Any]]] = None,
    conflicts: Optional[List[str]] = None,
    csv_file: Union[str, Path] = RESULTS_CLAIM_FILE,
    log_file: Union[str, Path] = DEFAULT_OUTPUT_FILE,
    auth_method: str = "username",
):
    """Menampilkan laporan ringkasan klaim akhir gabungan langsung ke stdout."""
    print("\n" + render_claim_combined_summary(
        total_accounts=total_accounts,
        total_tasks=total_tasks,
        newly_results=newly_results,
        reused_records=reused_records,
        preserved_records=preserved_records,
        conflicts=conflicts,
        csv_file=csv_file,
        log_file=log_file,
        auth_method=auth_method,
    ) + "\n")


def handle_claim_reuse_wizard(
    usernames: List[str],
    voucher_links: Optional[List[str]] = None,
    auth_method: str = "username",
    auto_mode: Optional[str] = None,
    csv_file: Optional[Path] = None,
    log_file: Optional[Path] = None,
) -> Tuple[str, List[str], List[Dict[str, Any]], Set[str], Dict[str, List[int]]]:
    """Wizard interaktif per-voucher untuk menentukan pemakaian hasil lama (reuse) vs klaim ulang.
    
    Menu Pilihan:
      [1] Pakai hasil lama, lewati voucher yang sudah sukses (default)
      [2] Klaim ulang semua voucher (abaikan hasil lama)
      [3] Pilih per akun untuk klaim ulang penuh
      [b] Kembali ke langkah sebelumnya

    Mengembalikan:
      (action, to_process, reused_records, recheck_targets, account_vouchers_plan)
      action: "proceed", "finish", atau "back"
      to_process: daftar akun yang membutuhkan minimal 1 tugas klaim
      reused_records: daftar akun/voucher yang memakai hasil sukses lama
      recheck_targets: set akun yang diklaim ulang penuh
      account_vouchers_plan: dict {akun: [1], [2], atau [1, 2]} daftar voucher yang harus diklaim
    """
    if not usernames:
        return "proceed", [], [], set(), {}

    claim_records = get_checked_claim_records(csv_file=csv_file, log_file=log_file)
    csv_name = Path(csv_file).name if csv_file else RESULTS_CLAIM_FILE.name

    success_accounts = []
    for acc in usernames:
        rec = shopee_core.find_matching_record(acc, claim_records, auth_method)
        if rec and rec.get("has_any_success"):
            rec_copy = dict(rec)
            rec_copy["account"] = acc
            rec_copy["display"] = shopee_core.format_account_display(acc, auth_method)
            success_accounts.append(rec_copy)

    # Jika tidak ada akun yang memiliki riwayat klaim sukses, langsung jalankan semua
    if not success_accounts:
        all_plan = {acc: [1, 2] for acc in usernames}
        return "proceed", usernames, [], set(), all_plan

    # Mode otomatis (misal dari flag --resume)
    if auto_mode == "reuse":
        plan: Dict[str, List[int]] = {}
        reused: List[Dict[str, Any]] = []
        for acc in usernames:
            rec = shopee_core.find_matching_record(acc, claim_records, auth_method)
            v1_ok = rec.get("v1", {}).get("is_success", False) if rec else False
            v2_ok = rec.get("v2", {}).get("is_success", False) if rec else False
            if v1_ok and v2_ok:
                plan[acc] = []
                reused.append(rec)
            elif v1_ok and not v2_ok:
                plan[acc] = [2]
                reused.append({**rec, "reused_vouchers": [1]})
            elif v2_ok and not v1_ok:
                plan[acc] = [1]
                reused.append({**rec, "reused_vouchers": [2]})
            else:
                plan[acc] = [1, 2]
        to_proc = [acc for acc in usernames if len(plan[acc]) > 0]
        if not to_proc:
            return "finish", [], reused, set(), plan
        return "proceed", to_proc, reused, set(), plan

    while True:
        print(f"\n{GREEN}ℹ️  Ditemukan {len(success_accounts)} dari {len(usernames)} akun memiliki riwayat klaim sukses di riwayat klaim ({csv_name}).{RESET}")
        print(f"{CYAN}{BOLD}PILIH OPSI PEMROSESAN HASIL KLAIM:{RESET}")
        print(f"  [1] Pakai hasil lama, lewati voucher yang sudah sukses (default)")
        print(f"  [2] Klaim ulang semua voucher (abaikan hasil lama)")
        print(f"  [3] Pilih per akun untuk klaim ulang penuh")
        print(f"  [b] Kembali ke langkah sebelumnya")

        pilihan = input(f"\n{WHITE}Pilih opsi [1/2/3/b, default: 1]: {RESET}").strip().casefold()

        if pilihan in ("", "1", "default", "y", "ya", "yes"):
            plan = {}
            reused = []
            for acc in usernames:
                rec = shopee_core.find_matching_record(acc, claim_records, auth_method)
                v1_ok = rec.get("v1", {}).get("is_success", False) if rec else False
                v2_ok = rec.get("v2", {}).get("is_success", False) if rec else False
                if v1_ok and v2_ok:
                    plan[acc] = []
                    reused.append(rec)
                elif v1_ok and not v2_ok:
                    plan[acc] = [2]
                    reused.append({**rec, "reused_vouchers": [1]})
                elif v2_ok and not v1_ok:
                    plan[acc] = [1]
                    reused.append({**rec, "reused_vouchers": [2]})
                else:
                    plan[acc] = [1, 2]

            to_proc = [acc for acc in usernames if len(plan[acc]) > 0]

            # Dead-end avoidance jika semua akun/voucher sudah sukses
            if not to_proc:
                print(f"\n{CYAN}{BOLD}===================================================={RESET}")
                print(f"♻️  {GREEN}{BOLD}RINGKASAN HASIL LAMA KLAIM YANG DIPAKAI ULANG ({len(reused)} Akun):{RESET}")
                print(f"{CYAN}===================================================={RESET}")
                for idx, r in enumerate(reused, 1):
                    v1_st = f"V1: {r.get('v1', {}).get('status', '-')} ({r.get('v1', {}).get('date', '-')})"
                    v2_st = f"V2: {r.get('v2', {}).get('status', '-')} ({r.get('v2', {}).get('date', '-')})"
                    disp = r.get("display") or shopee_core.format_account_display(r.get("account", "-"), auth_method)
                    print(f"  [{idx}] {disp} | {v1_st} | {v2_st}")

                print(f"\n{WHITE}Semua akun/voucher dalam daftar sudah berhasil diklaim sebelumnya.{RESET}")
                print("Pilihan:")
                print("  [1] Selesai, pakai hasil lama ini saja (default)")
                print("  [2] Klaim ulang sebagian (masuk ke pilihan per akun)")
                print("  [3] Klaim ulang semua")

                sub_c = input(f"{WHITE}Pilih [1/2/3, default: 1]: {RESET}").strip()
                if sub_c in ("", "1"):
                    return "finish", [], reused, set(), plan
                elif sub_c == "2":
                    pilihan = "3"
                elif sub_c == "3":
                    all_plan = {acc: [1, 2] for acc in usernames}
                    return "proceed", usernames, [], set(usernames), all_plan
                else:
                    return "finish", [], reused, set(), plan

            if pilihan != "3":
                return "proceed", to_proc, reused, set(), plan

        if pilihan == "2":
            all_plan = {acc: [1, 2] for acc in usernames}
            return "proceed", usernames, [], set(usernames), all_plan

        elif pilihan == "3":
            print(f"\n{CYAN}{BOLD}📋 DAFTAR AKUN YANG MEMILIKI RIWAYAT KLAIM SUKSES:{RESET}")
            for idx, rec in enumerate(success_accounts, 1):
                disp = rec.get("display") or shopee_core.format_account_display(rec.get("account", "-"), auth_method)
                v1_icon = "✅ SUKSES" if rec.get("v1", {}).get("is_success") else "❌ BELUM"
                v2_icon = "✅ SUKSES" if rec.get("v2", {}).get("is_success") else "❌ BELUM"
                print(f"  [{idx}] {disp} | V1: {v1_icon} ({rec.get('v1', {}).get('date', '-')}) | V2: {v2_icon} ({rec.get('v2', {}).get('date', '-')})")

            print(f"\n{WHITE}Ketik nomor akun yang ingin DIKLAIM ULANG PENUH (kedua voucher) [pisahkan koma/spasi].")
            print(f"Ketik 'semua' untuk klaim ulang semua, atau Enter / 'tidak ada' untuk memakai hasil lama:{RESET}")

            while True:
                pilih_str = input(f"{WHITE}Nomor akun yang diklaim ulang [default: tidak ada]: {RESET}").strip()
                if not pilih_str or pilih_str.casefold() in ("tidak ada", "none"):
                    chosen_indices = []
                    break
                elif pilih_str.casefold() in ("semua", "all"):
                    chosen_indices = list(range(1, len(success_accounts) + 1))
                    break
                else:
                    tokens = [t.strip() for t in re.split(r"[,;\s]+", pilih_str) if t.strip()]
                    valid = True
                    temp_indices = []
                    for tok in tokens:
                        if not tok.isdigit():
                            print(f"{RED}❌ Input '{tok}' bukan angka valid! Masukkan nomor urut 1-{len(success_accounts)}.{RESET}")
                            valid = False
                            break
                        num = int(tok)
                        if num < 1 or num > len(success_accounts):
                            print(f"{RED}❌ Nomor '{num}' di luar rentang (1-{len(success_accounts)})! Silakan coba lagi.{RESET}")
                            valid = False
                            break
                        if num not in temp_indices:
                            temp_indices.append(num)
                    if valid:
                        chosen_indices = temp_indices
                        break

            chosen_accs = {success_accounts[i - 1]["account"] for i in chosen_indices}
            plan = {}
            reused = []
            for acc in usernames:
                if acc in chosen_accs:
                    plan[acc] = [1, 2]
                else:
                    rec = shopee_core.find_matching_record(acc, claim_records, auth_method)
                    v1_ok = rec.get("v1", {}).get("is_success", False) if rec else False
                    v2_ok = rec.get("v2", {}).get("is_success", False) if rec else False
                    if v1_ok and v2_ok:
                        plan[acc] = []
                        reused.append(rec)
                    elif v1_ok and not v2_ok:
                        plan[acc] = [2]
                        reused.append({**rec, "reused_vouchers": [1]})
                    elif v2_ok and not v1_ok:
                        plan[acc] = [1]
                        reused.append({**rec, "reused_vouchers": [2]})
                    else:
                        plan[acc] = [1, 2]

            to_proc = [acc for acc in usernames if len(plan[acc]) > 0]
            return "proceed", to_proc, reused, chosen_accs, plan

        elif pilihan in ("b", "back", "kembali"):
            return "back", [], [], set(), {}
        else:
            print(f"{YELLOW}⚠️ Pilihan tidak valid, silakan ketik 1, 2, 3, atau b.{RESET}")


def render_claim_summary_box(
    total_accounts: int,
    completed_count: int,
    success_count: int,
    fail_count: int,
    unknown_count: int,
    box_width: Optional[int] = None,
    output_file_name: Optional[str] = "bot_responses.txt",
) -> str:
    """Membuat laporan ringkasan terminal berbingkai rapi yang konsisten dengan estetika Cek-Misi."""
    if box_width is None:
        try:
            term_cols = shutil.get_terminal_size((48, 20)).columns
            if term_cols < 48:
                box_width = max(40, term_cols)
            elif term_cols <= 64:
                box_width = min(term_cols - 2, 48)
            else:
                box_width = 48
        except Exception:
            box_width = 48

    inner_width = max(38, box_width - 2)

    clr_border = '\033[92m'      # Hijau
    clr_title = '\033[1;93m'     # Kuning tebal
    clr_cyan = '\033[96m'        # Biru muda / cyan
    clr_green = '\033[92m'       # Hijau
    clr_yellow = '\033[93m'      # Kuning
    clr_red = '\033[91m'         # Merah
    clr_num = '\033[1;96m'       # Angka cyan tebal
    clr_reset = '\033[0m'

    def _make_line(content: str) -> str:
        vis = shopee_core.get_visible_width(content)
        pad = max(0, inner_width - vis)
        return f"{clr_border}│{clr_reset}{content}{' ' * pad}{clr_border}│{clr_reset}"

    top = f"{clr_border}╭{'─' * inner_width}╮{clr_reset}"
    sep = f"{clr_border}├{'─' * inner_width}┤{clr_reset}"
    bot = f"{clr_border}╰{'─' * inner_width}╯{clr_reset}"

    title = f"{clr_title}🎟️ KLAIM VOUCHER SHOPEEFOOD 🎟️{clr_reset}"
    t_vis = shopee_core.get_visible_width(title)
    l_pad = max(0, (inner_width - t_vis) // 2)
    r_pad = max(0, inner_width - t_vis - l_pad)
    title_line = f"{clr_border}│{clr_reset}{' ' * l_pad}{title}{' ' * r_pad}{clr_border}│{clr_reset}"

    lines = [
        top,
        title_line,
        sep,
        _make_line(f" 🎯 {clr_cyan}Total akun{clr_reset}       : {clr_num}{total_accounts}{clr_reset}"),
        _make_line(f" 🏁 {clr_cyan}Selesai{clr_reset}          : {clr_num}{completed_count}{clr_reset}"),
        _make_line(f" ✅ {clr_green}Berhasil{clr_reset}         : {clr_num}{success_count}{clr_reset}"),
        _make_line(f" ❌ {clr_red}Gagal{clr_reset}            : {clr_num}{fail_count}{clr_reset}"),
        _make_line(f" ❓ {clr_yellow}Tidak diketahui{clr_reset}  : {clr_num}{unknown_count}{clr_reset}"),
        bot,
    ]
    if output_file_name:
        lines.append("")
        lines.append(f"📂 {clr_cyan}Rincian respons tersimpan di '{output_file_name}'{clr_reset}")

    return "\n".join(lines)


async def click_button(btn, msg, row_idx: int = 0, col_idx: int = 0):
    """Mengklik tombol inline Telegram bot secara aman."""
    if hasattr(btn, "click") and callable(btn.click):
        await btn.click()
    elif hasattr(msg, "click") and callable(msg.click):
        await msg.click(row_idx, col_idx)
    else:
        raise RuntimeError("Objek tombol tidak mendukung interaksi klik")


async def wait_for_bot_message_with_buttons(
    client,
    target_bot: str,
    after_id: int,
    match_fn,
    timeout: float = 15.0,
    poll_interval: float = 1.0,
):
    """Menunggu pesan bot setelah after_id yang memiliki tombol inline yang cocok."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(target_bot, limit=10)
        # Saring pesan bot setelah ID pemicu
        candidates = sorted(
            (m for m in messages if m.id > after_id and not getattr(m, "out", False) and getattr(m, "buttons", None)),
            key=lambda m: m.id,
        )
        for msg in candidates:
            for r_idx, row in enumerate(msg.buttons):
                for c_idx, btn in enumerate(row):
                    btn_text = getattr(btn, "text", "") or ""
                    if match_fn(btn_text):
                        return msg, btn, r_idx, c_idx
        await asyncio.sleep(poll_interval)
    return None, None, -1, -1


async def wait_for_bot_final_response(
    client,
    target_bot: str,
    after_id: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> str:
    """Menunggu pesan respons akhir dari bot setelah pengiriman identitas akun."""
    deadline = asyncio.get_running_loop().time() + timeout
    latest_text = ""
    while asyncio.get_running_loop().time() < deadline:
        messages = await client.get_messages(target_bot, limit=5)
        candidates = sorted(
            (m for m in messages if m.id > after_id and not getattr(m, "out", False)),
            key=lambda m: m.id,
        )
        for msg in candidates:
            text = (getattr(msg, "text", "") or "").strip()
            if text:
                latest_text = text
                if not is_intermediate_response(text):
                    return text
        await asyncio.sleep(poll_interval)
    return latest_text


async def claim_voucher_for_account(
    client,
    account_identity: str,
    voucher_link: str,
    target_bot: str = DEFAULT_BOT,
    timeout: float = 30.0,
) -> Tuple[str, str, str]:
    """Menjalankan alur klaim voucher untuk 1 akun ke @shp_tools_bot:
    1. Kirim /account
    2. Deteksi & klik tombol 'Claim Voucher'
    3. Kirim link voucher
    4. Deteksi & klik tombol metode identifikasi akun (Email / Username / ID)
    5. Kirim identitas akun
    6. Tangkap respons akhir bot dan klasifikasikan
    Mengembalikan: (status, detail, raw_response)
    """
    clean_id = (account_identity or "").strip()
    if not clean_id:
        return "TIDAK DIKETAHUI", "Identitas akun kosong", ""

    # 1. Kirim perintah /account
    try:
        sent_cmd = await client.send_message(target_bot, "/account")
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengirim /account: {exc}", ""

    # 2. Deteksi tombol Claim Voucher
    def match_claim(text: str) -> bool:
        t = text.casefold()
        return "claim" in t and "voucher" in t

    msg_claim, btn_claim, r_c, c_c = await wait_for_bot_message_with_buttons(
        client, target_bot, sent_cmd.id, match_claim, timeout=timeout
    )
    if not msg_claim or not btn_claim:
        return "TIDAK DIKETAHUI", "Tombol 'Claim Voucher' tidak ditemukan pada balasan bot", ""

    # Klik tombol Claim Voucher
    try:
        await click_button(btn_claim, msg_claim, r_c, c_c)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengklik tombol 'Claim Voucher': {exc}", ""

    await asyncio.sleep(1.5)

    # 3. Kirim link voucher
    try:
        sent_link = await client.send_message(target_bot, voucher_link)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengirim tautan voucher: {exc}", ""

    # 4. Deteksi tombol metode identifikasi
    is_email = "@" in clean_id
    is_numeric = clean_id.isdigit()

    def match_method(text: str) -> bool:
        t = text.casefold()
        if is_email and "email" in t:
            return True
        if is_numeric and ("id" in t or "user" in t):
            return True
        if not is_email and not is_numeric and ("username" in t or "user" in t or "akun" in t):
            return True
        return any(k in t for k in ("email", "username", "id", "akun"))

    msg_method, btn_method, r_m, c_m = await wait_for_bot_message_with_buttons(
        client, target_bot, sent_link.id, match_method, timeout=timeout
    )
    if not msg_method or not btn_method:
        return "TIDAK DIKETAHUI", "Tombol metode identifikasi tidak ditemukan pada balasan bot", ""

    try:
        await click_button(btn_method, msg_method, r_m, c_m)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengklik tombol metode identifikasi: {exc}", ""

    await asyncio.sleep(1.5)

    # 5. Kirim identitas akun
    try:
        sent_id_msg = await client.send_message(target_bot, clean_id)
    except Exception as exc:
        return "TIDAK DIKETAHUI", f"Gagal mengirim identitas akun: {exc}", ""

    # 6. Tangkap respons akhir dari bot
    final_text = await wait_for_bot_final_response(
        client, target_bot, sent_id_msg.id, timeout=timeout
    )
    if not final_text:
        return "TIDAK DIKETAHUI", "Timeout menunggu balasan akhir dari bot", ""

    status, detail = classify_claim_response(final_text)
    return status, detail, final_text


async def run_voucher_claim_mode(
    client=None,
    accounts: Optional[List[str]] = None,
    accounts_file: Optional[Union[str, Path]] = None,
    voucher_link: Optional[str] = None,
    voucher_links: Optional[List[str]] = None,
    step_delay: float = 4.0,
    voucher_delay: float = 2.0,
    output_file: Union[str, Path] = DEFAULT_OUTPUT_FILE,
    target_bot: str = DEFAULT_BOT,
    timeout: float = 30.0,
    reused_records: Optional[List[Dict[str, Any]]] = None,
    recheck_targets: Optional[Set[str]] = None,
    account_vouchers_plan: Optional[Dict[str, List[int]]] = None,
    csv_file: Union[str, Path] = RESULTS_CLAIM_FILE,
    auth_method: str = "username",
) -> dict:
    """Menjalankan antrean proses klaim voucher ShopeeFood secara berurutan.

    Mendukung klaim multiple voucher (contoh: Voucher Diskon + Voucher Ongkir Gratis)
    secara berurutan per username, dengan logika reuse per-voucher dan proteksi hasil lama.
    """
    out_file = Path(output_file)
    csv_path = Path(csv_file)

    # 1. Validasi Tautan Voucher
    if voucher_links:
        active_voucher_links = [str(l).strip() for l in voucher_links if str(l).strip()]
    elif voucher_link:
        active_voucher_links = [voucher_link.strip()]
    else:
        active_voucher_links = load_voucher_claim_configs()

    if not active_voucher_links:
        active_voucher_links = [DEFAULT_VOUCHER_LINK, DEFAULT_VOUCHER_LINK_2]

    # 2. Ambil Daftar Akun
    if accounts is None:
        file_to_read = accounts_file or DEFAULT_ACCOUNTS_FILE
        try:
            accounts, dupes = read_claim_accounts(file_to_read)
            if dupes > 0:
                print(f"{YELLOW}ℹ️ Membersihkan {dupes} entri duplikat dari daftar akun.{RESET}")
        except FileNotFoundError as err:
            print(f"{RED}❌ {err}{RESET}")
            return {"total": 0, "completed": 0, "success": 0, "fail": 0, "unknown": 0, "results": []}

    reused = list(reused_records or [])
    rc_targets = set(recheck_targets or set())
    v_plan_map = dict(account_vouchers_plan or {})

    # Gabungan seluruh akun untuk pelaporan
    all_known_accounts = []
    if accounts:
        all_known_accounts.extend(accounts)
    for r in reused:
        acc_r = r.get("account")
        if acc_r and acc_r not in all_known_accounts:
            all_known_accounts.append(acc_r)

    total_all_accounts = len(all_known_accounts) if all_known_accounts else (len(accounts) if accounts else 0)
    total_all_tasks = total_all_accounts * len(active_voucher_links)

    # Jika antrean akun yang akan diproses kosong (semua akun sudah selesai dipakai ulang)
    if not accounts:
        old_claim_records = get_checked_claim_records(csv_file=csv_path, log_file=out_file)
        c_list = []
        for rec in old_claim_records.values():
            if isinstance(rec, dict) and rec.get("conflicts"):
                c_list.extend(rec["conflicts"])

        print_claim_combined_summary(
            total_accounts=total_all_accounts,
            total_tasks=total_all_tasks,
            newly_results=[],
            reused_records=reused,
            preserved_records=[],
            conflicts=c_list,
            csv_file=csv_path,
            log_file=out_file,
            auth_method=auth_method,
        )
        return {
            "total": total_all_accounts,
            "completed": 0,
            "success": len(reused),
            "fail": 0,
            "unknown": 0,
            "results": [],
            "reused_records": reused,
            "preserved_records": [],
        }

    total = len(accounts)

    print(f"\n{CYAN}{BOLD}===================================================={RESET}")
    print(f"🎟️ {BOLD}MEMULAI PROSES KLAIM VOUCHER SHOPEEFOOD{RESET}")
    print(f"{CYAN}===================================================={RESET}")
    print(f"🎯 Target Bot   : {BOLD}{target_bot}{RESET}")
    for i, v_l in enumerate(active_voucher_links, 1):
        lbl = get_voucher_label(v_l, i - 1)
        print(f"🔗 Voucher {i}    : [{lbl}] {v_l[:55]}...")
    v_note = f" ({len(active_voucher_links)} voucher per akun)" if len(active_voucher_links) > 1 else ""
    print(f"📋 Total Antrean: {BOLD}{total} akun{v_note} (Total gabungan: {total_all_accounts} akun){RESET}")
    print(f"📂 File Output  : {csv_path.name} (CSV) & {out_file.name} (Log)")
    print(f"{CYAN}----------------------------------------------------{RESET}\n")

    # Inisialisasi client jika belum diberikan
    own_client = False
    if client is None:
        client = shopee_core.create_client()
        await shopee_core.start_client(client)
        own_client = True

    completed_count = 0
    success_count = 0
    fail_count = 0
    unknown_count = 0
    results = []
    preserved_records = []

    # Baca riwayat lama untuk proteksi penimpaan hasil sukses
    old_claim_records = get_checked_claim_records(csv_file=csv_path, log_file=out_file)

    try:
        for idx, acc in enumerate(accounts, 1):
            target_vouchers = v_plan_map.get(acc, [1, 2]) if v_plan_map else [1, 2]
            if not target_vouchers:
                continue

            bar = shopee_core.render_progress_bar(idx, total)
            print(f"{CYAN}{bar}{RESET} {BOLD}{acc}{RESET}")

            old_acc_rec = shopee_core.find_matching_record(acc, old_claim_records, auth_method)

            acc_statuses = []
            acc_details = []
            acc_vouchers_results = []
            hit_floodwait = False

            for v_idx, v_url in enumerate(active_voucher_links, 1):
                if v_idx not in target_vouchers:
                    continue

                v_label = get_voucher_label(v_url, v_idx - 1)
                is_last_v = (v_idx == len(active_voucher_links))
                tree_prefix = "  └─" if (is_last_v and len(active_voucher_links) == 1) else ("  ├─" if not is_last_v else "  └─")

                if len(active_voucher_links) > 1:
                    print(f"{tree_prefix} [{v_idx}/{len(active_voucher_links)}] 🎟️ {BOLD}{v_label}{RESET}...")

                old_v_key = f"v{v_idx}"
                old_v_info = old_acc_rec.get(old_v_key, {}) if old_acc_rec else {}
                old_v_had_success = old_v_info.get("is_success", False)

                try:
                    status, detail, raw_resp = await claim_voucher_for_account(
                        client=client,
                        account_identity=acc,
                        voucher_link=v_url,
                        target_bot=target_bot,
                        timeout=timeout,
                    )

                    # Jika voucher yang dipaksa klaim ulang dibalas "sudah pernah diklaim"
                    raw_cf = (raw_resp or "").casefold()
                    det_cf = (detail or "").casefold()
                    if any(k in raw_cf for k in ("sudah pernah", "sudah diklaim", "already claimed", "telah diklaim", "pernah diklaim")) or "sudah pernah diklaim" in det_cf:
                        status = "BERHASIL"
                        detail = "Sudah pernah diklaim sebelumnya"

                    # Proteksi: jika klaim ulang sebuah voucher berakhir TIMEOUT/ERROR/TIDAK DIKETAHUI,
                    # pertahankan hasil sukses lama voucher itu
                    is_err = any(err in status.upper() for err in ("TIMEOUT", "ERROR", "TIDAK DIKETAHUI"))
                    v_tag = f"Voucher {v_idx}: {v_label}" if len(active_voucher_links) > 1 else ""

                    if is_err and old_v_had_success:
                        preserved_records.append({
                            "account": acc,
                            "voucher_index": v_idx,
                            "voucher_label": v_label,
                            "old_status": old_v_info.get("status", "BERHASIL"),
                            "old_date": old_v_info.get("date", "-"),
                            "reason": f"Klaim ulang {status}: {detail}",
                        })
                        status = "BERHASIL"
                        detail = "🛡️ Hasil lama dipertahankan (klaim ulang timeout/error)"
                    else:
                        save_claim_result(
                            acc,
                            status,
                            detail,
                            raw_resp,
                            output_file=out_file,
                            voucher_label=v_tag,
                            voucher_index=v_idx,
                            csv_file=csv_path,
                        )

                    acc_statuses.append(status)
                    acc_details.append(detail)
                    acc_vouchers_results.append({
                        "voucher_index": v_idx,
                        "voucher_label": v_label,
                        "voucher_link": v_url,
                        "status": status,
                        "detail": detail,
                        "response": raw_resp,
                    })

                    indent = "  │  └─ " if (not is_last_v and len(active_voucher_links) > 1) else ("     └─ " if len(active_voucher_links) > 1 else "  └─ ")
                    if status == "BERHASIL":
                        print(f"{indent}{GREEN}{BOLD}✅ {status}: {detail}{RESET}")
                    elif status == "GAGAL":
                        print(f"{indent}{RED}❌ {status}: {detail}{RESET}")
                    else:
                        print(f"{indent}{YELLOW}❓ {status}: {detail}{RESET}")

                except FloodWaitError as exc:
                    msg = f"Telegram FloodWait {exc.seconds}s. Antrean dihentikan."
                    v_tag = f"Voucher {v_idx}: {v_label}" if len(active_voucher_links) > 1 else ""
                    indent = "     └─ " if len(active_voucher_links) > 1 else "  └─ "

                    if old_v_had_success:
                        preserved_records.append({
                            "account": acc,
                            "voucher_index": v_idx,
                            "voucher_label": v_label,
                            "old_status": old_v_info.get("status", "BERHASIL"),
                            "old_date": old_v_info.get("date", "-"),
                            "reason": f"Klaim ulang FloodWait: {exc.seconds}s",
                        })
                        status = "BERHASIL"
                        detail = "🛡️ Hasil lama dipertahankan (klaim ulang timeout/error)"
                        print(f"{indent}{GREEN}{BOLD}✅ {status}: {detail}{RESET}")
                    else:
                        status = "TIDAK DIKETAHUI"
                        detail = msg
                        save_claim_result(
                            acc,
                            status,
                            detail,
                            str(exc),
                            output_file=out_file,
                            voucher_label=v_tag,
                            voucher_index=v_idx,
                            csv_file=csv_path,
                        )
                        print(f"{indent}{RED}⚠️ FloodWait {exc.seconds}s! Antrean dihentikan demi keamanan.{RESET}\n")

                    acc_statuses.append(status)
                    acc_details.append(detail)
                    acc_vouchers_results.append({
                        "voucher_index": v_idx,
                        "voucher_label": v_label,
                        "voucher_link": v_url,
                        "status": status,
                        "detail": detail,
                        "response": str(exc),
                    })
                    hit_floodwait = True
                    break

                except Exception as exc:
                    err_msg = f"Error: {exc}"
                    v_tag = f"Voucher {v_idx}: {v_label}" if len(active_voucher_links) > 1 else ""
                    indent = "     └─ " if len(active_voucher_links) > 1 else "  └─ "

                    if old_v_had_success:
                        preserved_records.append({
                            "account": acc,
                            "voucher_index": v_idx,
                            "voucher_label": v_label,
                            "old_status": old_v_info.get("status", "BERHASIL"),
                            "old_date": old_v_info.get("date", "-"),
                            "reason": f"Klaim ulang Error: {exc}",
                        })
                        status = "BERHASIL"
                        detail = "🛡️ Hasil lama dipertahankan (klaim ulang timeout/error)"
                        print(f"{indent}{GREEN}{BOLD}✅ {status}: {detail}{RESET}")
                    else:
                        status = "TIDAK DIKETAHUI"
                        detail = err_msg
                        save_claim_result(
                            acc,
                            status,
                            detail,
                            str(exc),
                            output_file=out_file,
                            voucher_label=v_tag,
                            voucher_index=v_idx,
                            csv_file=csv_path,
                        )
                        print(f"{indent}{RED}❌ Error: {exc}{RESET}")

                    acc_statuses.append(status)
                    acc_details.append(detail)
                    acc_vouchers_results.append({
                        "voucher_index": v_idx,
                        "voucher_label": v_label,
                        "voucher_link": v_url,
                        "status": status,
                        "detail": detail,
                        "response": str(exc),
                    })

                if not is_last_v:
                    await asyncio.sleep(voucher_delay)

            # Selesai satu akun
            print()
            completed_count += 1

            if hit_floodwait:
                final_acc_status = "TIDAK DIKETAHUI"
                final_acc_detail = "Dihentikan karena FloodWait Telegram"
                unknown_count += 1
            elif all(s == "BERHASIL" for s in acc_statuses):
                final_acc_status = "BERHASIL"
                final_acc_detail = "Semua voucher berhasil diklaim"
                success_count += 1
            elif any(s == "BERHASIL" for s in acc_statuses):
                final_acc_status = "BERHASIL"
                final_acc_detail = f"Sebagian voucher berhasil diklaim ({acc_statuses.count('BERHASIL')}/{len(acc_statuses)})"
                success_count += 1
            elif any(s == "TIDAK DIKETAHUI" for s in acc_statuses):
                final_acc_status = "TIDAK DIKETAHUI"
                final_acc_detail = "Respons perantara atau bot tidak dikenal"
                unknown_count += 1
            else:
                final_acc_status = "GAGAL"
                final_acc_detail = "Gagal mengklaim voucher"
                fail_count += 1

            results.append({
                "account": acc,
                "status": final_acc_status,
                "detail": final_acc_detail,
                "vouchers": acc_vouchers_results,
            })

            if hit_floodwait:
                break

            if idx < total:
                await asyncio.sleep(step_delay)

    finally:
        if own_client:
            try:
                await client.disconnect()
            except Exception:
                pass

    # Ambil seluruh konflik riwayat untuk pelaporan
    c_list = []
    for rec in old_claim_records.values():
        if isinstance(rec, dict) and rec.get("conflicts"):
            c_list.extend(rec["conflicts"])

    # Tampilkan Ringkasan Akhir 3 Kelompok (Per-Voucher & Per-Akun)
    print_claim_combined_summary(
        total_accounts=total_all_accounts,
        total_tasks=total_all_tasks,
        newly_results=results,
        reused_records=reused,
        preserved_records=preserved_records,
        conflicts=c_list,
        csv_file=csv_path,
        log_file=out_file,
        auth_method=auth_method,
    )

    return {
        "total": total_all_accounts,
        "completed": completed_count,
        "success": success_count,
        "fail": fail_count,
        "unknown": unknown_count,
        "results": results,
        "reused_records": reused,
        "preserved_records": preserved_records,
    }


async def interactive_voucher_claim_menu():
    """Menu interaktif khusus klaim voucher yang dipanggil dari menu utama."""
    print(f"\n{CYAN}{BOLD}===================================================={RESET}")
    print(f"🎟️ {BOLD}MENU KLAIM VOUCHER SHOPEEFOOD (@shp_tools_bot){RESET}")
    print(f"{CYAN}===================================================={RESET}")

    # 1. Konfigurasi Tautan Voucher (2 Voucher: Diskon & Ongkir Gratis)
    current_links = load_voucher_claim_configs()
    v1 = current_links[0] if len(current_links) > 0 else DEFAULT_VOUCHER_LINK
    v2 = current_links[1] if len(current_links) > 1 else DEFAULT_VOUCHER_LINK_2

    print(f"\n🔗 {BOLD}Tautan Voucher yang Akan Diklaim Berurutan per Akun:{RESET}")
    print(f"   1. 🏷️  {BOLD}Voucher Diskon{RESET}        : {CYAN}{v1}{RESET}")
    print(f"   2. 🚚 {BOLD}Voucher Ongkir Gratis{RESET} : {CYAN}{v2}{RESET}")
    print(f"   {WHITE}💡 Setiap akun akan diklaimkan 2 voucher ini secara otomatis.{RESET}")

    ubah = input(f"\n{WHITE}Ingin mengganti tautan voucher? [1/2/Semua/N] (Default N): {RESET}").strip().casefold()
    if ubah in ("1",):
        new_v1 = input("Masukkan tautan Voucher 1 (Diskon): ").strip()
        if new_v1:
            v1 = new_v1
            save_voucher_claim_configs([v1, v2])
            print(f"{GREEN}✅ Tautan Voucher 1 berhasil diperbarui!{RESET}")
    elif ubah in ("2",):
        new_v2 = input("Masukkan tautan Voucher 2 (Ongkir Gratis): ").strip()
        if new_v2:
            v2 = new_v2
            save_voucher_claim_configs([v1, v2])
            print(f"{GREEN}✅ Tautan Voucher 2 berhasil diperbarui!{RESET}")
    elif ubah in ("s", "semua", "y", "ya", "yes", "all", "a"):
        new_v1 = input("Tautan Voucher 1 [Enter untuk tetap]: ").strip()
        if new_v1:
            v1 = new_v1
        new_v2 = input("Tautan Voucher 2 [Enter untuk tetap]: ").strip()
        if new_v2:
            v2 = new_v2
        save_voucher_claim_configs([v1, v2])
        print(f"{GREEN}✅ Kedua tautan voucher berhasil diperbarui!{RESET}")

    current_links = [v1, v2]

    # 2. Pemilihan Tipe Pengisian Akun (Manual vs Bulk File) dengan integrasi reuse
    while True:
        print(f"\n{CYAN}{BOLD}⚙️ PILIH TIPE EKSEKUSI PENGISIAN AKUN KLAIM VOUCHER:{RESET}")
        print(f"  [1] ⚡ {BOLD}Isi Manual (1 Akun){RESET}")
        print(f"      👉 Langsung ketik 1 username/email/ID Shopee di terminal.")
        print(f"      👉 Dilengkapi validasi format, preview tersamar, & konfirmasi.")
        print(f"  [2] 📦 {BOLD}Mode Massal / Bulk File{RESET}")
        print(f"      👉 Klaim otomatis untuk banyak akun sekaligus dari file teks (.txt).")
        tipe_klaim = input(f"{WHITE}Pilih tipe [1/2, default: 2]: {RESET}").strip()

        if tipe_klaim == "1":
            acc = shopee_core.input_manual_account(auth_method="username")
            if not acc:
                print(f"{YELLOW}↩️ Kembali ke pilihan tipe pengisian akun klaim.{RESET}")
                continue

            # Periksa apakah akun tunggal ini sudah memiliki riwayat klaim sukses
            claim_records = get_checked_claim_records()
            rec = shopee_core.find_matching_record(acc, claim_records, auth_method="username")
            disp = shopee_core.format_account_display(acc, "username")

            if rec and rec.get("is_fully_success"):
                print(f"\n{GREEN}ℹ️  Akun {disp} sudah memiliki riwayat klaim SUKSES untuk KEDUA voucher:{RESET}")
                print(f"   • Voucher 1: {rec['v1']['status']} ({rec['v1']['date']})")
                print(f"   • Voucher 2: {rec['v2']['status']} ({rec['v2']['date']})")
                print(f"\n{CYAN}{BOLD}Konfirmasi Eksekusi:{RESET}")
                print("  [1] Pakai hasil lama (selesai tanpa klaim ulang) [default]")
                print("  [2] Klaim ulang kedua voucher")
                c_single = input(f"{WHITE}Pilih [1/2, default: 1]: {RESET}").strip()
                if c_single in ("", "1"):
                    rec_copy = dict(rec)
                    rec_copy["account"] = acc
                    rec_copy["display"] = disp
                    print_claim_combined_summary(
                        total_accounts=1,
                        total_tasks=len(current_links),
                        newly_results=[],
                        reused_records=[rec_copy],
                        preserved_records=[],
                    )
                    return
                else:
                    await run_voucher_claim_mode(
                        accounts=[acc],
                        voucher_links=current_links,
                        step_delay=4.0,
                        voucher_delay=2.0,
                        recheck_targets={acc},
                        account_vouchers_plan={acc: [1, 2]},
                    )
                    return
            elif rec and rec.get("has_any_success"):
                v1_ok = rec.get("v1", {}).get("is_success", False)
                v2_ok = rec.get("v2", {}).get("is_success", False)
                print(f"\n{GREEN}ℹ️  Akun {disp} memiliki riwayat klaim sukses sebagian:{RESET}")
                print(f"   • Voucher 1: {rec['v1']['status']} ({rec['v1']['date']})")
                print(f"   • Voucher 2: {rec['v2']['status']} ({rec['v2']['date']})")
                print(f"\n{CYAN}{BOLD}Konfirmasi Eksekusi:{RESET}")
                print("  [1] Lanjutkan klaim voucher yang belum sukses saja [default]")
                print("  [2] Klaim ulang kedua voucher")
                c_single = input(f"{WHITE}Pilih [1/2, default: 1]: {RESET}").strip()
                if c_single in ("", "1"):
                    plan = {acc: [2] if v1_ok else [1]}
                    reused_v = [1] if v1_ok else [2]
                    await run_voucher_claim_mode(
                        accounts=[acc],
                        voucher_links=current_links,
                        step_delay=4.0,
                        voucher_delay=2.0,
                        reused_records=[{**rec, "account": acc, "display": disp, "reused_vouchers": reused_v}],
                        account_vouchers_plan=plan,
                    )
                    return
                else:
                    await run_voucher_claim_mode(
                        accounts=[acc],
                        voucher_links=current_links,
                        step_delay=4.0,
                        voucher_delay=2.0,
                        recheck_targets={acc},
                        account_vouchers_plan={acc: [1, 2]},
                    )
                    return
            else:
                await run_voucher_claim_mode(
                    accounts=[acc],
                    voucher_links=current_links,
                    step_delay=4.0,
                    voucher_delay=2.0,
                )
                return

        elif tipe_klaim in ("", "2"):
            # Pemilihan File Sumber Akun
            print(f"\n📁 {BOLD}Pilih File Sumber Akun/Identitas:{RESET}")
            file_options = []
            if DEFAULT_ACCOUNTS_FILE.is_file():
                file_options.append(DEFAULT_ACCOUNTS_FILE)
            for p, _ in shopee_core.get_available_txt_files():
                if p not in file_options and p.name not in ("requirements.txt", "valid_food.txt"):
                    file_options.append(p)

            selected_file = None
            if file_options:
                for idx, fpath in enumerate(file_options, 1):
                    print(f"  [{idx}] 📄 {fpath.name}")
                print(f"  [{len(file_options) + 1}] ✍️  Ketik nama/path file lain")
                choice = input(f"{WHITE}Pilih file [1-{len(file_options) + 1}] (Default 1): {RESET}").strip()
                try:
                    choice_idx = int(choice) if choice else 1
                    if 1 <= choice_idx <= len(file_options):
                        selected_file = file_options[choice_idx - 1]
                except ValueError:
                    pass

            if not selected_file:
                custom_file = input("Masukkan nama/path file akun: ").strip()
                selected_file = Path(custom_file) if custom_file else DEFAULT_ACCOUNTS_FILE

            try:
                bulk_accs, dupes = read_claim_accounts(selected_file)
                if dupes > 0:
                    print(f"{YELLOW}ℹ️ Membersihkan {dupes} entri duplikat dari daftar akun.{RESET}")
            except FileNotFoundError as err:
                print(f"{RED}❌ {err}{RESET}")
                continue

            if not bulk_accs:
                print(f"{RED}❌ File akun kosong! Silakan pilih file lain.{RESET}")
                continue

            action, to_proc, reused, recheck_accs, plan = handle_claim_reuse_wizard(
                usernames=bulk_accs,
                voucher_links=current_links,
                auth_method="username",
            )

            if action == "back":
                print(f"\n{YELLOW}↩️ Kembali ke pilihan tipe pengisian akun klaim...{RESET}")
                continue
            elif action == "finish":
                print_claim_combined_summary(
                    total_accounts=len(bulk_accs),
                    total_tasks=len(bulk_accs) * len(current_links),
                    newly_results=[],
                    reused_records=reused,
                    preserved_records=[],
                )
                return
            else:
                await run_voucher_claim_mode(
                    accounts=to_proc,
                    voucher_links=current_links,
                    step_delay=4.0,
                    voucher_delay=2.0,
                    reused_records=reused,
                    recheck_targets=recheck_accs,
                    account_vouchers_plan=plan,
                )
                return
        else:
            print(f"{YELLOW}⚠️ Pilihan tidak valid, silakan ketik 1 atau 2.{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(interactive_voucher_claim_menu())
    except (KeyboardInterrupt, EOFError):
        print("\nDihentikan oleh pengguna.")
    except Exception as exc:
        print(f"\n❌ Terjadi kesalahan: {exc}")
