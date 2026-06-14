"""Tự động convert tất cả các chương từ số bắt đầu, bỏ qua các chương đã build"""
import sys
import io
import time
import traceback
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from src.video_engine import video_from_file

INPUT_DIR = Path(__file__).parent / "input" / "Võ Luyện Đỉnh Phong"
OUTPUT_DIR = Path(__file__).parent / "output" / "Võ Luyện Đỉnh Phong"


def extract_chapter_number(filename: str) -> int:
    """Extract số chương từ tên file"""
    import re
    match = re.search(r'\d+', filename)
    if match:
        return int(match.group())
    return 0


def should_retry(exc: Exception) -> bool:
    """Check if error is retryable"""
    error_str = str(exc) + traceback.format_exc()
    retryable_errors = [
        'NoAudioReceived',
        'timeout',
        'connection',
        'ConnectionError',
        'URLError',
        'socket',
        'PermissionError',
    ]
    return any(err in error_str for err in retryable_errors)


def convert_auto(start_chapter: int = 27):
    """Tự động convert các chương từ start_chapter trở đi"""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách file input, sắp xếp theo số chương
    input_files = sorted(INPUT_DIR.glob("*.txt"), key=lambda f: extract_chapter_number(f.name))

    if not input_files:
        print(f"[INFO] Không có file .txt nào trong {INPUT_DIR}")
        return

    # Lọc chỉ các chương từ start_chapter trở đi
    input_files = [f for f in input_files if extract_chapter_number(f.name) >= start_chapter]

    if not input_files:
        print(f"[INFO] Không có chương nào từ {start_chapter} trở đi")
        return

    print(f"[INFO] Tìm thấy {len(input_files)} chương từ chương {start_chapter} trở đi\n")

    ok = fail = 0
    for input_file in input_files:
        chapter_num = extract_chapter_number(input_file.name)
        output_file = OUTPUT_DIR / f"chương {chapter_num}.mp4"

        # Bỏ qua nếu file output đã tồn tại
        if output_file.exists():
            print(f"  ====================================================")
            print(f"  Chương  : {chapter_num}")
            print(f"  Output  : {output_file.name} (đã tồn tại, bỏ qua)")
            print(f"  ====================================================")
            ok += 1
            continue

        print(f"  ====================================================")
        print(f"  Chương  : {chapter_num}")
        print(f"  Input   : {input_file.name}")
        print(f"  Output  : {output_file.name}")
        print(f"  ====================================================")

        # Retry logic for network errors
        max_retries = 5
        for attempt in range(max_retries):
            try:
                video_from_file(input_file, output_file, show_subtitles=False)
                print(f"  [OK] Hoàn tất: {output_file.name}\n")
                ok += 1
                break
            except Exception as exc:
                if should_retry(exc) and attempt < max_retries - 1:
                    wait_time = 10 + (attempt * 5)  # 10s, 15s, 20s, 25s
                    print(f"  [RETRY {attempt + 1}/{max_retries}] Đợi {wait_time}s rồi thử lại...")
                    print(f"  Lỗi: {str(exc)[:100]}")
                    time.sleep(wait_time)
                else:
                    print(f"  [ERR] Không thể convert sau {attempt + 1} lần thử")
                    print(f"  {str(exc)}\n")
                    fail += 1
                    break

    print(f"\n  ====================================================")
    print(f"  HOÀN TẤT  -  {ok} file thành công  |  {fail} lỗi")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  ====================================================")


if __name__ == "__main__":
    start_chapter = 27
    if len(sys.argv) > 1:
        try:
            start_chapter = int(sys.argv[1])
        except ValueError:
            print(f"[ERR] Số chương không hợp lệ: {sys.argv[1]}")
            sys.exit(1)

    convert_auto(start_chapter)
