"""Standalone script: TXT → MP4 video (voice + subtitles).

Cach dung:
    python video.py input/demo_VI.txt
    python video.py input/demo_VI.txt --voice vi-VN-HoaiMyNeural --rate -5% -o output/demo.mp4
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.video_engine import video_from_file


def main():
    parser = argparse.ArgumentParser(description="Chuyen van ban tieng Viet sang video MP4 co giong doc va phu de")
    parser.add_argument("input", help="Duong dan file .txt can doc")
    parser.add_argument("--output", "-o", default=None, help="Duong dan file .mp4 xuat ra")
    parser.add_argument("--voice", default="vi-VN-HoaiMyNeural", help="Giong doc (mac dinh: vi-VN-HoaiMyNeural)")
    parser.add_argument("--rate", default="-5%", help="Toc do doc, vi du: -5% (cham hon)")
    parser.add_argument("--res", default="1280x720", help="Do phan giai video, mac dinh 1280x720")
    parser.add_argument("--fontsize", type=int, default=32, help="Co chu phu de, mac dinh 32")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[LOI] Khong tim thay file: {input_path}")
        sys.exit(1)

    output_path = args.output
    if output_path is None:
        output_path = input_path.with_suffix(".mp4")
    else:
        output_path = Path(output_path)

    print(f"[INFO] Dang xu ly: {input_path.name}")
    print(f"[INFO] Giong: {args.voice}")
    print(f"[INFO] Do phan giai: {args.res}")
    print("[INFO] Can internet de tai giong tu Microsoft Edge")
    print("[INFO] Can ffmpeg da cai tren may (chay: ffmpeg -version de kiem tra)")

    try:
        result = video_from_file(
            input_path,
            output_path,
            voice=args.voice,
            rate=args.rate,
            resolution=args.res,
            font_size=args.fontsize,
        )
        print(f"[OK] Da xuat: {result}")
    except ImportError:
        print("[LOI] edge-tts chua duoc cai. Chay: pip install edge-tts")
        sys.exit(1)
    except FileNotFoundError as exc:
        if "ffmpeg" in str(exc).lower():
            print("[LOI] ffmpeg chua duoc cai. Tai tai: https://ffmpeg.org/download.html#build-windows")
        else:
            print(f"[LOI] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"[LOI] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
