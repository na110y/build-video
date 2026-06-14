"""TXT → MP4 converter (free, no API key needed).

Place .txt files in input/ and run:
    python convert.py

Output MP4 files go to output/ with the same base filename.
"""
import sys
import io
from pathlib import Path

# Fix encoding for Vietnamese characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from src.video_engine import video_from_file

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"


def extract_chapter_number(filename: str) -> int:
    """Extract số chương từ tên file."""
    import re
    match = re.search(r'\d+', filename)
    if match:
        return int(match.group())
    return 0


def main(start_chapter: int = 27):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Duyệt qua các thư mục truyện trong input/
    story_dirs = [d for d in INPUT_DIR.iterdir() if d.is_dir()]
    
    if not story_dirs:
        # Nếu không có thư mục, tìm file .txt trực tiếp trong input/
        files = sorted(INPUT_DIR.glob("*.txt"))
        if not files:
            print(f"[INFO] Khong co file .txt nao trong {INPUT_DIR}")
            print("[INFO] Bo file .txt vao thu muc input/ va chay lai")
            return
        print(f"[INFO] Tim thay {len(files)} file .txt\n")
        ok = fail = 0
        for f in files:
            out_path = OUTPUT_DIR / f.with_suffix(".mp4").name
            
            # Bỏ qua nếu file output đã tồn tại
            if out_path.exists():
                print(f"  ====================================================")
                print(f"  File  : {f.name}")
                print(f"  Output: {out_path.name} (da ton tai, bo qua)")
                print(f"  ====================================================")
                ok += 1
                continue
            
            print(f"  ====================================================")
            print(f"  File  : {f.name}")
            print(f"  Output: {out_path.name}")
            print(f"  ====================================================")
            try:
                video_from_file(f, out_path, show_subtitles=False)
                ok += 1
            except Exception as exc:
                import traceback
                print(f"  [ERR ] {exc}")
                traceback.print_exc()
                fail += 1
    else:
        # Có thư mục truyện, duyệt qua từng thư mục
        print(f"[INFO] Tim thay {len(story_dirs)} thu muc truyen\n")
        ok = fail = 0
        for story_dir in sorted(story_dirs):
            print(f"  ====================================================")
            print(f"  Truyen : {story_dir.name}")
            print(f"  ====================================================")
            
            # Tạo thư mục output tương ứng
            output_story_dir = OUTPUT_DIR / story_dir.name
            output_story_dir.mkdir(parents=True, exist_ok=True)
            
            # Duyệt qua các file .txt trong thư mục truyện
            files = sorted(story_dir.glob("*.txt"), key=lambda f: extract_chapter_number(f.name))
            # Lọc chỉ các chương từ start_chapter trở đi
            files = [f for f in files if extract_chapter_number(f.name) >= start_chapter]
            if not files:
                print(f"  [INFO] Khong co file .txt trong {story_dir.name}")
                continue

            print(f"  [INFO] Tim thay {len(files)} file .txt trong {story_dir.name} (tu chuong {start_chapter} tro di)")
            
            for f in files:
                out_path = output_story_dir / f.with_suffix(".mp4").name
                
                # Bỏ qua nếu file output đã tồn tại
                if out_path.exists():
                    print(f"  ----------------------------------------------------")
                    print(f"  File  : {f.name}")
                    print(f"  Output: {out_path.name} (da ton tai, bo qua)")
                    print(f"  ----------------------------------------------------")
                    ok += 1
                    continue
                
                print(f"  ----------------------------------------------------")
                print(f"  File  : {f.name}")
                print(f"  Output: {out_path.name}")
                print(f"  ----------------------------------------------------")
                try:
                    video_from_file(f, out_path, show_subtitles=False)
                    ok += 1
                except Exception as exc:
                    import traceback
                    print(f"  [ERR ] {exc}")
                    traceback.print_exc()
                    fail += 1

    print(f"\n  ====================================================")
    print(f"  HOAN TAT  -  {ok} file thanh cong  |  {fail} loi")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  ====================================================")


if __name__ == "__main__":
    main()
