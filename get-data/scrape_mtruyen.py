"""
Scraper cho mtruyen.net - cào nội dung chương truyện.

Cách dùng:
    python scrape_mtruyen.py

Cấu hình bên dưới:
    BASE_URL    : URL gốc của truyện (thay đổi nếu muốn cào truyện khác)
    START_CHAP  : Chương bắt đầu
    END_CHAP    : Chương kết thúc (None = tự động dừng khi không tìm thấy chương tiếp)
    OUTPUT_DIR  : Thư mục lưu file .txt
"""

import re
import sys
import time
import random
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Fix Windows terminal encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────
BASE_URL   = "https://mtruyen.net/truyen/vo-luyen-dinh-phong-dich/chuong-{n}"
START_CHAP = 1
END_CHAP   = None   # None = chạy đến khi không còn chương nào
OUTPUT_DIR = Path(__file__).parent.parent / "convert-txt" / "input" / "Võ Luyện Đỉnh Phong"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

DELAY_MIN = 1.0   # giây nghỉ tối thiểu giữa các request
DELAY_MAX = 2.5   # giây nghỉ tối đa
# ─────────────────────────────────────────────────────────────────────────────


def get_existing_chapters(output_dir: Path) -> set[int]:
    """Trả về tập hợp các số chương đã tồn tại trong thư mục output."""
    existing = set()
    for f in output_dir.glob("chương *.txt"):
        m = re.match(r"chương\s+(\d+)\.txt", f.name, re.IGNORECASE)
        if m:
            existing.add(int(m.group(1)))
    return existing


def fetch_chapter(url: str, session: requests.Session) -> str | None:
    """
    Tải trang chương, trả về nội dung văn bản thuần túy.
    Trả về None nếu không tìm thấy hoặc lỗi.
    """
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [LỖI] Không thể tải {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Tìm div chapter-content
    content_div = soup.find("div", class_=lambda c: c and "chapter-content" in c.split())
    if not content_div:
        # fallback: tìm div có class chứa chapter-content
        content_div = soup.find("div", attrs={"class": re.compile(r"\bchapter-content\b")})

    if not content_div:
        print(f"  [WARN] Không tìm thấy chapter-content tại {url}")
        return None

    # Lấy văn bản, giữ nguyên xuống dòng theo thẻ <p> và <br>
    # Thay <br> bằng newline trước khi get_text
    for br in content_div.find_all("br"):
        br.replace_with("\n")

    paragraphs = content_div.find_all("p")
    if paragraphs:
        lines = []
        for p in paragraphs:
            text = p.get_text(separator="\n").strip()
            if text:
                lines.append(text)
        text = "\n\n".join(lines)
    else:
        text = content_div.get_text(separator="\n").strip()

    # Dọn dẹp khoảng trắng thừa
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text if text else None


def save_chapter(chapter_num: int, content: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"chương {chapter_num}.txt"
    out_file.write_text(content, encoding="utf-8")
    return out_file


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing = get_existing_chapters(OUTPUT_DIR)
    if existing:
        print(f"[INFO] Đã có {len(existing)} chương: {sorted(existing)}")
    else:
        print("[INFO] Chưa có chương nào, bắt đầu từ chương 1.")

    session = requests.Session()
    chap = START_CHAP
    ok = skip = fail = 0
    consecutive_miss = 0  # đếm số chương liên tiếp không tìm thấy

    while True:
        if END_CHAP is not None and chap > END_CHAP:
            break

        if chap in existing:
            print(f"  [BỎ QUA] Chương {chap} đã tồn tại.")
            skip += 1
            chap += 1
            continue

        url = BASE_URL.format(n=chap)
        print(f"  [CÀO] Chương {chap} <- {url}")

        content = fetch_chapter(url, session)
        if content is None:
            fail += 1
            consecutive_miss += 1
            print(f"  [LỖI] Không lấy được nội dung chương {chap}.")
            if consecutive_miss >= 3:
                print(f"\n[DỪNG] Không tìm thấy {consecutive_miss} chương liên tiếp, kết thúc.")
                break
        else:
            consecutive_miss = 0
            out_file = save_chapter(chap, content, OUTPUT_DIR)
            chars = len(content)
            print(f"  [OK]   Chương {chap} -> {out_file.name} ({chars:,} ký tự)")
            ok += 1

        chap += 1

        # Nghỉ ngẫu nhiên để tránh bị chặn
        if consecutive_miss == 0:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    print(f"\n{'='*52}")
    print(f"  HOÀN TẤT")
    print(f"  Đã cào mới : {ok} chương")
    print(f"  Bỏ qua     : {skip} chương (đã có)")
    print(f"  Lỗi        : {fail} chương")
    print(f"  Lưu tại    : {OUTPUT_DIR}")
    print(f"{'='*52}")


if __name__ == "__main__":
    main()
