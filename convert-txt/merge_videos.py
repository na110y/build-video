"""Gộp 30 chương thành 1 video (tập 1, tập 2, ...)"""
import subprocess
import asyncio
import edge_tts
import time
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

INPUT_DIR = Path(__file__).parent / "output" / "Võ Luyện Đỉnh Phong"
OUTPUT_DIR = Path(__file__).parent.parent / "product" / "Võ Luyện Đỉnh Phong"
AUDIO_ASSETS_DIR = Path(__file__).parent / "audio_assets"
TEMP_DIR = Path(__file__).parent / "temp_merge"
CHAPTERS_PER_EPISODE = 2

VOICE = "vi-VN-NamMinhNeural"
STORY_NAME = "Võ Luyện Đỉnh Phong"
BACKGROUND_IMAGE = Path(__file__).parent.parent / "product" / STORY_NAME / "thumbnail.jpg"

TRANSITION_AUDIO = AUDIO_ASSETS_DIR / "transition.mp3"
OUTRO_AUDIO = AUDIO_ASSETS_DIR / "outro.mp3"

async def create_intro_audio(episode_num: int) -> Path:
    """Tạo audio intro động cho từng tập"""
    text = f"Bộ chuyện, {STORY_NAME}, tập {episode_num}, chúc các bạn nghe truyện vui vẻ"
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    output_path = AUDIO_ASSETS_DIR / f"intro_ep{episode_num}.mp3"
    await communicate.save(str(output_path))
    return output_path

async def create_transition_audio() -> Path:
    """Tạo audio transition động"""
    text = ", Follow kênh mình để nhận thông báo mới truyện mới nhất,"
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    output_path = AUDIO_ASSETS_DIR / "transition.mp3"
    await communicate.save(str(output_path))
    return output_path

async def create_outro_audio(episode_num: int) -> Path:
    """Tạo audio outro động"""
    text = f"Hết tập {episode_num}, cảm ơn các bạn đã nghe, chúc các bạn một ngày vui vẻ!"
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    output_path = AUDIO_ASSETS_DIR / f"outro_ep{episode_num}.mp3"
    await communicate.save(str(output_path))
    return output_path

def add_intro_to_video(video_path: Path, intro_audio_path: Path, output_path: Path, episode_num: int) -> None:
    """Thêm intro vào đầu video (video intro + video gốc)"""
    # Lấy độ dài audio intro bằng ffprobe
    cmd_probe = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(intro_audio_path)
    ]
    result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
    audio_duration = float(result.stdout.strip())
    
    # Tạo video intro từ ảnh nền
    cmd_intro = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(BACKGROUND_IMAGE),
        "-i", str(intro_audio_path),
        "-vf", "pad=iw:ih+1:0:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-t", str(audio_duration),
        str(TEMP_DIR / "intro_video.mp4")
    ]
    subprocess.run(cmd_intro, check=True)
    
    # Concat intro video + video gốc
    list_file = TEMP_DIR / "intro_concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        f.write(f"file '{(TEMP_DIR / 'intro_video.mp4').absolute()}'\n")
        f.write(f"file '{video_path.absolute()}'\n")
    
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    result = subprocess.run(cmd_concat, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERR ] Concat intro failed: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd_concat)
    
    # Cleanup
    time.sleep(0.1)
    (TEMP_DIR / "intro_video.mp4").unlink(missing_ok=True)
    time.sleep(0.1)
    list_file.unlink(missing_ok=True)

def add_transition_between_videos(video1_path: Path, video2_path: Path, transition_audio_path: Path, output_path: Path) -> None:
    """Thêm transition giữa 2 video (video1 + transition + video2)"""
    # Lấy độ dài audio transition bằng ffprobe
    cmd_probe = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(transition_audio_path)
    ]
    result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
    audio_duration = float(result.stdout.strip())
    
    # Tạo video transition từ audio transition
    cmd_transition = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1280x720:d={audio_duration}",
        "-i", str(transition_audio_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(TEMP_DIR / "transition_video.mp4")
    ]
    subprocess.run(cmd_transition, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Concat video1 + transition + video2
    list_file = TEMP_DIR / "transition_concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        f.write(f"file '{video1_path.absolute()}'\n")
        f.write(f"file '{(TEMP_DIR / 'transition_video.mp4').absolute()}'\n")
        f.write(f"file '{video2_path.absolute()}'\n")
    
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    result = subprocess.run(cmd_concat, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERR ] Concat transition failed: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd_concat)
    
    # Cleanup
    time.sleep(0.1)
    (TEMP_DIR / "transition_video.mp4").unlink(missing_ok=True)
    time.sleep(0.1)
    list_file.unlink(missing_ok=True)

def add_outro_to_video(video_path: Path, outro_audio_path: Path, output_path: Path) -> None:
    """Thêm outro vào cuối video (video gốc + video outro)"""
    # Lấy độ dài audio outro bằng ffprobe
    cmd_probe = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(outro_audio_path)
    ]
    result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
    audio_duration = float(result.stdout.strip())
    
    # Tạo video outro từ audio outro
    cmd_outro = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1280x720:d={audio_duration}",
        "-i", str(outro_audio_path),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(TEMP_DIR / "outro_video.mp4")
    ]
    subprocess.run(cmd_outro, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Concat video gốc + outro video
    list_file = TEMP_DIR / "outro_concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        f.write(f"file '{video_path.absolute()}'\n")
        f.write(f"file '{(TEMP_DIR / 'outro_video.mp4').absolute()}'\n")
    
    cmd_concat = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    result = subprocess.run(cmd_concat, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERR ] Concat outro failed: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd_concat)
    
    # Cleanup
    time.sleep(0.1)
    (TEMP_DIR / "outro_video.mp4").unlink(missing_ok=True)
    time.sleep(0.1)
    list_file.unlink(missing_ok=True)

def overlay_background_on_video(video_path: Path, output_path: Path, episode_num: int) -> None:
    """Overlay thumbnail.jpg làm nền cho toàn bộ video"""
    cmd_overlay = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-loop", "1", "-i", str(BACKGROUND_IMAGE),
        "-filter_complex", "[1]scale=1280:720[bg];[0]scale=1280:720[fg];[bg][fg]overlay=0:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path)
    ]
    result = subprocess.run(cmd_overlay, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERR ] Overlay failed: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd_overlay)

def main(episode_to_build=None):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # Lấy danh sách file video, sắp xếp theo số chương
    video_files = sorted(INPUT_DIR.glob("*.mp4"), key=lambda f: int(''.join(filter(str.isdigit, f.name))))

    if not video_files:
        print(f"[INFO] Khong co file video trong {INPUT_DIR}")
        return

    print(f"[INFO] Tim thay {len(video_files)} file video\n")

    episode_num = 1
    for i in range(0, len(video_files), CHAPTERS_PER_EPISODE):
        if episode_to_build and episode_num != episode_to_build:
            episode_num += 1
            continue
        # Lấy 30 chương cho mỗi tập
        episode_files = video_files[i:i + CHAPTERS_PER_EPISODE]
        
        print(f"  ====================================================")
        print(f"  Tap   : {episode_num}")
        print(f"  ====================================================")
        
        # Tạo intro audio động cho tập này
        print(f"  [INFO] Dang tao intro cho tap {episode_num}...")
        intro_audio_path = asyncio.run(create_intro_audio(episode_num))
        
        # Tạo transition audio
        print(f"  [INFO] Dang tao transition audio...")
        transition_audio_path = asyncio.run(create_transition_audio())
        
        # Tạo outro audio
        print(f"  [INFO] Dang tao outro audio...")
        outro_audio_path = asyncio.run(create_outro_audio(episode_num))
        
        # Thêm intro vào chương đầu tiên của tập
        print(f"  [INFO] Dang them intro vao {episode_files[0].name}...")
        first_chapter_with_intro = TEMP_DIR / f"{episode_files[0].stem}_with_intro.mp4"
        add_intro_to_video(episode_files[0], intro_audio_path, first_chapter_with_intro, episode_num)
        
        # Gộp các chương với transition ở giữa
        current_output = first_chapter_with_intro
        
        for j in range(1, len(episode_files)):
            print(f"  [INFO] Dang them transition giua {episode_files[j-1].name} va {episode_files[j].name}...")
            next_output = TEMP_DIR / f"temp_merge_{episode_num}_{j}.mp4"
            add_transition_between_videos(current_output, episode_files[j], transition_audio_path, next_output)
            
            # Xóa file tạm cũ
            if j > 1:
                current_output.unlink(missing_ok=True)
            
            current_output = next_output
        
        # Thêm outro vào cuối tập
        print(f"  [INFO] Dang them outro vao cuon tap...")
        temp_output = TEMP_DIR / f"temp_merge_{episode_num}_final.mp4"
        add_outro_to_video(current_output, outro_audio_path, temp_output)
        
        # Kiểm tra file temp_output có tồn tại không
        if not temp_output.exists():
            print(f"  [ERR ] temp_output khong ton tai: {temp_output}")
            continue
        
        # Xóa file tạm cũ
        if len(episode_files) > 1:
            current_output.unlink(missing_ok=True)
        
        # Output file cuối cùng
        output_file = OUTPUT_DIR / f"tập {episode_num}.mp4"
        
        # Xóa file output cũ nếu tồn tại
        output_file.unlink(missing_ok=True)
        
        # Overlay bgc.png làm nền cho toàn bộ video
        print(f"  [INFO] Dang overlay bgc.png lam nen cho toan bo video...")
        overlay_background_on_video(temp_output, output_file, episode_num)
        
        # Xóa file tạm
        temp_output.unlink(missing_ok=True)
        first_chapter_with_intro.unlink(missing_ok=True)
        
        print(f"  [OK] Da gộp xong: {output_file.name}")
        
        episode_num += 1
    
    print(f"\n  ====================================================")
    print(f"  HOAN TAT  -  Da gộp thành {episode_num - 1} tap")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  ====================================================")

if __name__ == "__main__":
    import sys
    episode = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(episode_to_build=episode)
