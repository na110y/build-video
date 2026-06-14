"""Standalone TTS script — đọc file TXT tiếng Việt → xuất file MP3.
Không cần API key, không cần dịch, chỉ cần internet để tải giọng từ Microsoft Edge.

Cách dùng:
    python tts.py input/demo.txt
    python tts.py input/demo.txt --voice vi-VN-HoaiMyNeural --rate -5%
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.tts_engine import tts_from_file


def main():
    parser = argparse.ArgumentParser(description="Chuyen van ban tieng Viet sang giong noi MP3")
    parser.add_argument("input", help="Duong dan file .txt can doc")
    parser.add_argument("--output", "-o", default=None, help="Duong dan file .mp3 xuat ra")
    parser.add_argument("--voice", default="vi-VN-HoaiMyNeural", help="Giong doc (mac dinh: vi-VN-HoaiMyNeural)")
    parser.add_argument("--rate", default="-5%", help="Toc do doc, vi du: -5% (cham hon), +10% (nhanh hon)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[LOI] Khong tim thay file: {input_path}")
        sys.exit(1)

    output_path = args.output
    if output_path is None:
        output_path = input_path.with_suffix(".mp3")
    else:
        output_path = Path(output_path)

    print(f"[INFO] Dang doc file: {input_path.name}")
    print(f"[INFO] Giong: {args.voice}")
    print(f"[INFO] Toc do: {args.rate}")
    print(f"[INFO] Dang xu ly... (can internet de tai giong tu Microsoft Edge)")

    try:
        result = tts_from_file(input_path, output_path, voice=args.voice, rate=args.rate)
        print(f"[OK] Da xuat: {result}")
    except ImportError:
        print("[LOI] edge-tts chua duoc cai. Chay: pip install edge-tts")
        sys.exit(1)
    except Exception as exc:
        print(f"[LOI] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
