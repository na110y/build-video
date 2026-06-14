"""
Scraper hoàn toàn từ metruyenchuvn.com - cào từ chương 1 tới cuối.

Cách dùng:
    python scrape_complete_metruyenchuvn.py

Sẽ cào lại tất cả chương từ metruyenchuvn để đảm bảo tính nhất quán,
không trộn lẫn từ các nguồn khác nhau.
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
STORY_URL = f"https://metruyenchuvn.com/{STORY_SLUG}"
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


def get_all_chapter_urls(session: requests.Session) -> dict[int, str]:
    """
    Lấy danh sách URL tất cả chương từ trang chính của truyện.
    Trả về {chapter_num: full_url} dict, sắp xếp theo số chương.
    """
    chapter_urls = {}

    print(f"[INFO] Đang quét trang {STORY_URL}...")
    try:
        resp = session.get(STORY_URL, headers=HEADERS, timeout=30)
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
            # Format: /vo-luyen-dinh-phong/chuong-101-slug hoặc /chuong-1-slug
            m = re.search(r"chuong-(\d+)", href)
            if m:
                chap_num = int(m.group(1))
                full_url = href if href.startswith("http") else f"https://metruyenchuvn.com{href}"
                chapter_urls[chap_num] = full_url

    if chapter_urls:
        print(f"[INFO] Tìm thấy {len(chapter_urls)} chương")
        min_chap = min(chapter_urls.keys())
        max_chap = max(chapter_urls.keys())
        print(f"[INFO] Chương {min_chap} - {max_chap}")
    else:
        print("[LỖI] Không tìm thấy chương nào!")

    return chapter_urls


def clean_content(text: str) -> str:
    """
    Loại bỏ các dòng không cần thiết:
    - Converter: ...
    - Chương XX: ...
    - Cập nhật lúc ...
    """
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()

        # Bỏ các dòng không cần
        if stripped.startswith("Converter:"):
            continue
        if re.match(r"^Chương\s+\d+:", stripped, re.IGNORECASE):
            continue
        if re.match(r"^Cập nhật lúc", stripped, re.IGNORECASE):
            continue

        cleaned.append(line)

    # Nối lại và dọn dẹp
    result = "\n".join(cleaned).strip()
    # Xóa các dòng trống liên tiếp (>2 dòng)
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result


def fetch_chapter_content(url: str, session: requests.Session) -> str | None:
    """
    Tải nội dung chương từ URL.
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

        # Ưu tiên lấy từ <p> tags
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
            # Loại bỏ các header không cần
            content = clean_content(content)
            return content if content else None

    except requests.RequestException:
        return None

    return None


def save_chapter(chapter_num: int, content: str, output_dir: Path) -> Path:
    """Lưu nội dung chương vào file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"chương {chapter_num}.txt"
    out_file.write_text(content, encoding="utf-8")
    return out_file


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    print(f"[INFO] Lấy danh sách tất cả chương từ metruyenchuvn.com...")
    chapter_urls = get_all_chapter_urls(session)

    if not chapter_urls:
        print("[ERR] Không tìm được chương nào, thoát.")
        return

    # Sắp xếp theo số chương
    sorted_chapters = sorted(chapter_urls.keys())
    print(f"\n[INFO] Bắt đầu cào {len(sorted_chapters)} chương từ metruyenchuvn.com...")
    print(f"{'='*52}\n")

    ok = fail = 0
    failed_chapters = []

    for idx, chap_num in enumerate(sorted_chapters, 1):
        url = chapter_urls[chap_num]
        print(f"  [{idx:3d}/{len(sorted_chapters)}] Chương {chap_num:5d} <- {url[-60:]}")

        content = fetch_chapter_content(url, session)
        if content is None:
            fail += 1
            failed_chapters.append(chap_num)
            print(f"            [LỖI] Không lấy được nội dung")
        else:
            out_file = save_chapter(chap_num, content, OUTPUT_DIR)
            chars = len(content)
            print(f"            [OK]   {chars:,} ký tự")
            ok += 1

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    print(f"\n{'='*52}")
    print(f"  HOÀN TẤT")
    print(f"  Cào thành công : {ok:3d} chương")
    print(f"  Lỗi            : {fail:3d} chương", end="")
    if failed_chapters:
        print(f" {failed_chapters}")
    else:
        print()
    print(f"  Lưu tại        : {OUTPUT_DIR}")
    print(f"{'='*52}")


if __name__ == "__main__":
    main()
