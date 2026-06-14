import asyncio
import re
import subprocess
from pathlib import Path
from typing import Optional
import edge_tts

VOICE_MALE = "vi-VN-NamMinhNeural"
VOICE_FEMALE = "vi-VN-HoaiMyNeural"
DEFAULT_VOICE = VOICE_MALE

def _sanitize_text(text: str) -> str:
    # Xóa sạch bất kỳ ký tự nào giống thẻ (phòng ngừa lỗi)
    text = re.sub(r'<[^>]+>', '', text)
    # Loại bỏ ngoặc, dấu nháy
    text = re.sub(r'["\'“”‘’«»\[\]\{\}<>]', '', text)
    # Thay thế các dấu ngắt bằng dấu phẩy
    text = text.replace(':', ',').replace('-', ',').replace('—', ',')
    # Chỉ giữ chữ, số, dấu câu
    text = re.sub(r'[^\w\s.,!?]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

async def _save_audio_plain(text: str, output_path: Path) -> None:
    # Tuyệt đối không dùng SSML tại đây để tránh lỗi
    # Tốc độ -10% để đọc chậm hơn, dễ nghe hơn
    communicate = edge_tts.Communicate(text, VOICE_MALE, rate="-10%")
    await communicate.save(str(output_path))

def _apply_pro_fx(input_path: Path, output_path: Path) -> None:
    """
    FFmpeg đơn giản: Chỉ tăng âm lượng, không làm méo tiếng.
    """
    # Chỉ cần tăng âm lượng lên 1.2 là đủ, không dùng echo hay EQ
    af = "volume=1.2"
    
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path), 
            "-af", af, 
            "-c:a", "libmp3lame", "-b:a", "192k", 
            str(output_path)
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def tts_storytelling_auto(text: str, output_path: str | Path, **kwargs) -> str:
    output_path = Path(output_path)
    clean_text = _sanitize_text(text)
    
    # CHỈ CHIA ĐOẠN (Paragraph) KHÔNG CHIA CÂU
    # Chia theo xuống dòng \n để AI đọc dài hơi, lấy hơi đúng chỗ
    paragraphs = [p for p in clean_text.split('\n') if p.strip()]
    
    temp_dir = output_path.parent / "temp_segments"
    temp_dir.mkdir(exist_ok=True, parents=True)
    audio_paths = []
    
    for i, para in enumerate(paragraphs):
        if not para.strip(): continue
        p = temp_dir / f"seg_{i}.mp3"
        asyncio.run(_save_audio_plain(para, p))
        audio_paths.append(p)
    
    # Ghép file
    list_file = temp_dir / "list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in audio_paths: f.write(f"file '{p.absolute()}'\n")
    
    raw_file = output_path.with_suffix(".raw.mp3")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(raw_file)], 
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Áp dụng hiệu ứng sát khí qua FFmpeg
    _apply_pro_fx(raw_file, output_path)
    raw_file.unlink(missing_ok=True)
    
    import shutil
    shutil.rmtree(temp_dir)
    return str(output_path)

tts_sync = tts_storytelling_auto

def tts_from_file(input_path: str | Path, output_path: Optional[str | Path] = None, slow: bool = True, voice: str = DEFAULT_VOICE) -> str:
    input_path = Path(input_path)
    text = input_path.read_text(encoding="utf-8")
    if output_path is None:
        output_path = input_path.with_suffix(".mp3")
    return tts_storytelling_auto(text, output_path, slow=slow, voice=voice)