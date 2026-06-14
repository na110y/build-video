"""
Scraper sử dụng API /get/listchap/ để lấy tất cả chapter slugs,
sau đó cào từng chapter.

Story ID: 35492
Có 61 trang chapter list
"""

import re
import sys
import json
import time
import random
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────
STORY_ID = "35492"
STORY_SLUG = "vo-luyen-dinh-phong"
BASE_URL = "https://metruyenchuvn.com"
LIST_API = f"{BASE_URL}/get/listchap/{STORY_ID}?page={{page}}"
OUTPUT_DIR = Path(__file__).parent.parent / "convert-txt" / "input" / "Võ Luyện Đỉnh Phong"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

DELAY_MIN = 0.5
DELAY_MAX = 1.2
# ─────────────────────────────────────────────────────────────────────────────


def get_existing_chapters(output_dir: Path) -> set[int]:
    """Trả về các chương đã có."""
    existing = set()
    for f in output_dir.glob("chương *.txt"):
        m = re.match(r"chương\s+(\d+)\.txt", f.name, re.IGNORECASE)
        if m:
            existing.add(int(m.group(1)))
    return existing


def get_all_chapter_slugs(session: requests.Session, total_pages: int = 61) -> dict[int, str]:
    """Lấy tất cả chapter slugs từ API."""
    chapter_urls = {}

    print(f"[INFO] Lấy danh sách {total_pages} trang chapter từ API...")

    for page_num in range(1, total_pages + 1):
        url = LIST_API.format(page=page_num)

        if page_num % 10 == 0 or page_num == 1:
            print(f"  [{page_num:2d}/{total_pages}] Đang quét...")

        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                continue

            # API trả về JSON với HTML escape
            try:
                data = resp.json()
                html_content = data.get("data", "")
            except:
                html_content = resp.text

            if not html_content:
                continue

            soup = BeautifulSoup(html_content, "lxml")

            # Tìm tất cả links tới chương
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "chuong-" in href:
                    m = re.search(r"chuong-(\d+)", href)
                    if m:
                        chap_num = int(m.group(1))
                        full_url = urljoin(BASE_URL, href)
                        if chap_num not in chapter_urls:
                            chapter_urls[chap_num] = full_url

        except requests.RequestException as e:
            print(f"  [{page_num:2d}/{total_pages}] Lỗi: {e}")

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    print(f"[INFO] Tìm được {len(chapter_urls)} chương")
    if chapter_urls:
        print(f"[INFO] Chương {min(chapter_urls.keys())} - {max(chapter_urls.keys())}")

    return chapter_urls


def clean_content(text: str) -> str:
    """Loại bỏ header không cần."""
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Converter:"):
            continue
        if re.match(r"^Chương\s+\d+:", stripped, re.IGNORECASE):
            continue
        if re.match(r"^Cập nhật lúc", stripped, re.IGNORECASE):
            continue
        cleaned.append(line)

    result = "\n".join(cleaned).strip()
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def fetch_chapter(url: str, session: requests.Session) -> str | None:
    """Tải nội dung chương."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        content_div = soup.find("div", class_="truyen")

        if not content_div:
            return None

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
            content = re.sub(r"\n{3,}", "\n\n", content)
            content = content.strip()
            content = clean_content(content)
            return content if content else None

    except requests.RequestException:
        return None

    return None


def save_chapter(chapter_num: int, content: str, output_dir: Path) -> Path:
    """Lưu chương."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"chương {chapter_num}.txt"
    out_file.write_text(content, encoding="utf-8")
    return out_file


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    existing = get_existing_chapters(OUTPUT_DIR)
    print(f"[INFO] Đã có {len(existing)} chương\n")

    session = requests.Session()

    # Lấy tất cả chapter slugs từ API
    chapter_urls = get_all_chapter_slugs(session, total_pages=61)

    if not chapter_urls:
        print("[ERR] Không lấy được chapter nào!")
        return

    sorted_chapters = sorted(chapter_urls.keys())
    print(f"\n[INFO] Cào {len(sorted_chapters)} chương...")
    print(f"{'='*60}\n")

    ok = skip = fail = 0

    for idx, chap_num in enumerate(sorted_chapters, 1):
        if chap_num in existing:
            skip += 1
            if idx % 100 == 0:
                print(f"  [{idx:4d}/{len(sorted_chapters)}] Chương {chap_num:5d} ⊘ SKIP")
            continue

        url = chapter_urls[chap_num]
        content = fetch_chapter(url, session)

        if content is None:
            fail += 1
            if idx % 50 == 0:
                print(f"  [{idx:4d}/{len(sorted_chapters)}] Chương {chap_num:5d} ✗ LỖI")
        else:
            save_chapter(chap_num, content, OUTPUT_DIR)
            ok += 1
            if idx % 100 == 0 or idx <= 110:
                chars = len(content)
                print(f"  [{idx:4d}/{len(sorted_chapters)}] Chương {chap_num:5d} ✓ OK ({chars:,} ký tự)")

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    print(f"\n\n{'='*60}")
    print(f"  HOÀN TẤT - Cào từ metruyenchuvn.com (đầy đủ)")
    print(f"  Cào mới       : {ok:6d} chương")
    print(f"  Bỏ qua        : {skip:6d} chương (đã có)")
    print(f"  Lỗi           : {fail:6d} chương")
    print(f"  Tổng cộng     : {ok + skip:6d} chương")
    print(f"  Lưu tại       : {OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
