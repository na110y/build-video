import asyncio
import edge_tts
import re
from pathlib import Path

def clean_text(text: str) -> str:
    """Làm sạch văn bản để AI đọc mượt hơn."""
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[#*_~`>|-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _warm_audio(input_path: str, output_path: str) -> None:
    """Post-process: bass boost + treble cut + normalize để giọng ấm hơn."""
    import subprocess
    af = (
        "equalizer=f=180:width_type=h:width=120:g=3,"
        "equalizer=f=3000:width_type=h:width=700:g=-2,"
        "dynaudnorm=f=150:g=5"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", af,
            "-c:a", "libmp3lame", "-b:a", "192k",
            output_path,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def generate_voice(text: str, output_file: str, voice: str = "vi-VN-HoaiMyNeural", rate: str = "-10%", pitch: str = "+0Hz"):
    """
    Tạo giọng đọc bằng Microsoft Edge TTS (Miễn phí, không cần API Key).
    - voice: vi-VN-HoaiMyNeural (Nữ) hoặc vi-VN-NamMinhNeural (Nam)
    - rate: Tốc độ đọc (-10% là chậm hơn 10%)
    - pitch: Độ cao thấp của giọng
    """
    print(f"--- Đang tạo giọng đọc: {voice} ---")
    text = clean_text(text)
    raw_file = output_file + ".raw.mp3"
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(raw_file)
    print("--- Đang xử lý âm thanh cho ấm hơn... ---")
    _warm_audio(raw_file, output_file)
    Path(raw_file).unlink(missing_ok=True)
    print(f"--- Hoàn thành! File lưu tại: {Path(output_file).absolute()} ---")

if __name__ == "__main__":
    input_path = Path("convert-txt/input/demo.txt")
    if not input_path.exists():
        print(f"[LOI] Khong tim thay file: {input_path}")
        exit(1)
    
    text = input_path.read_text(encoding="utf-8")
    print(f"[INFO] Dang doc file: {input_path.name} ({len(text)} ky tu)")
    
    # CHẠY TẠO GIỌNG
    output_dir = Path("convert-txt/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(generate_voice(text, str(output_dir / "giong_doc_chuan.mp3"), voice="vi-VN-HoaiMyNeural", rate="-13%"))
