"""Convert một chương từ TXT sang MP4"""
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from src.video_engine import video_from_file

INPUT_DIR = Path(__file__).parent / "input" / "Võ Luyện Đỉnh Phong"
OUTPUT_DIR = Path(__file__).parent / "output" / "Võ Luyện Đỉnh Phong"


def convert_chapter(chapter_num: int):
    """Convert một chương cụ thể"""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Tìm file input
    input_file = INPUT_DIR / f"chương {chapter_num}.txt"

    if not input_file.exists():
        print(f"[ERR] File không tồn tại: {input_file}")
        return False

    output_file = OUTPUT_DIR / f"chương {chapter_num}.mp4"

    # Kiểm tra file output đã tồn tại chưa
    if output_file.exists():
        print(f"[INFO] File đã tồn tại: {output_file.name}")
        return True

    print(f"====================================================")
    print(f"Chương  : {chapter_num}")
    print(f"Input   : {input_file.name}")
    print(f"Output  : {output_file.name}")
    print(f"====================================================")

    try:
        video_from_file(input_file, output_file, show_subtitles=False)
        print(f"[OK] Hoàn tất: {output_file.name}")
        return True
    except Exception as exc:
        import traceback
        print(f"[ERR] {exc}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng: python convert_single.py <số_chương>")
        print("Ví dụ: python convert_single.py 27")
        sys.exit(1)

    try:
        chapter_num = int(sys.argv[1])
        success = convert_chapter(chapter_num)
        sys.exit(0 if success else 1)
    except ValueError:
        print(f"[ERR] Số chương không hợp lệ: {sys.argv[1]}")
        sys.exit(1)
