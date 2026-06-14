"""
Scraper cho metruyenchuvn.com - cào nội dung chương truyện.

Cách dùng:
    python scrape_metruyenchuvn.py

Cấu hình bên dưới:
    BASE_URL    : URL gốc của truyện (slug: vo-luyen-dinh-phong)
    START_CHAP  : Chương bắt đầu
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
STORY_SLUG = "vo-luyen-dinh-phong"
BASE_URL   = "https://metruyenchuvn.com/{slug}/chuong-{n}"
START_CHAP = 101   # Bắt đầu từ chương 101 (mtruyen có tới 100)
OUTPUT_DIR = Path(__file__).parent.parent / "convert-txt" / "input" / "Võ Luyện Đỉnh Phong"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

DELAY_MIN = 1.0
DELAY_MAX = 2.5
# ─────────────────────────────────────────────────────────────────────────────


def get_existing_chapters(output_dir: Path) -> set[int]:
    """Trả về tập hợp các số chương đã tồn tại trong thư mục output."""
    existing = set()
    for f in output_dir.glob("chương *.txt"):
        m = re.match(r"chương\s+(\d+)\.txt", f.name, re.IGNORECASE)
        if m:
            existing.add(int(m.group(1)))
    return existing


def get_chapter_urls(session: requests.Session) -> dict[int, str]:
    """
    Lấy danh sách URL các chương từ trang chính của truyện.
    Trả về {chapter_num: url} dict
    """
    story_url = f"https://metruyenchuvn.com/{STORY_SLUG}"
    chapter_urls = {}

    try:
        resp = session.get(story_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[LỖI] Không thể tải trang chính: {e}")
        return chapter_urls

    soup = BeautifulSoup(resp.text, "lxml")

    # Tìm tất cả links chứa "chuong-"
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "chuong-" in href:
            # Parse chapter number từ URL
            # Format: /vo-luyen-dinh-phong/chuong-101-slug
            m = re.search(r"chuong-(\d+)", href)
            if m:
                chap_num = int(m.group(1))
                full_url = href if href.startswith("http") else f"https://metruyenchuvn.com{href}"
                chapter_urls[chap_num] = full_url

    return chapter_urls


def fetch_chapter_from_metruyenchuvn(url: str, session: requests.Session) -> str | None:
    """
    Tải chương từ URL đã biết
    Tìm nội dung trong div.truyen
    """
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        content_div = soup.find("div", class_="truyen")

        if not content_div:
            return None

        # Lấy văn bản từ div.truyen
        for br in content_div.find_all("br"):
            br.replace_with("\n")

        paragraphs = content_div.find_all("p")
        if paragraphs:
            lines = []
            for p in paragraphs:
                text = p.get_text(separator="\n").strip()
                if text:
                    lines.append(text)
            content = "\n\n".join(lines)
        else:
            content = content_div.get_text(separator="\n").strip()

        if content:
            # Dọn dẹp khoảng trắng thừa
            content = re.sub(r"\n{3,}", "\n\n", content)
            content = content.strip()
            return content if content else None

    except requests.RequestException:
        return None

    return None


def save_chapter(chapter_num: int, content: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"chương {chapter_num}.txt"
    out_file.write_text(content, encoding="utf-8")
    return out_file


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing = get_existing_chapters(OUTPUT_DIR)
    if existing:
        print(f"[INFO] Đã có {len(existing)} chương: {min(existing)}-{max(existing)}")
    else:
        print("[INFO] Chưa có chương nào")

    session = requests.Session()

    print(f"[INFO] Đang lấy danh sách chương từ {STORY_SLUG}...")
    chapter_urls = get_chapter_urls(session)

    if not chapter_urls:
        print("[ERR] Không lấy được danh sách chương!")
        return

    print(f"[INFO] Tìm thấy {len(chapter_urls)} chương trên trang")

    ok = skip = fail = 0

    # Sắp xếp theo số chương
    for chap_num in sorted(chapter_urls.keys()):
        if chap_num < START_CHAP:
            continue

        if chap_num in existing:
            print(f"  [BỎ QUA] Chương {chap_num} đã tồn tại.")
            skip += 1
            continue

        url = chapter_urls[chap_num]
        print(f"  [CÀO] Chương {chap_num} <- {url}")

        content = fetch_chapter_from_metruyenchuvn(url, session)
        if content is None:
            fail += 1
            print(f"  [LỖI] Không lấy được nội dung chương {chap_num}.")
        else:
            out_file = save_chapter(chap_num, content, OUTPUT_DIR)
            chars = len(content)
            print(f"  [OK]   Chương {chap_num} -> {out_file.name} ({chars:,} ký tự)")
            ok += 1

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
