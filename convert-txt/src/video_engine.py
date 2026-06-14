"""Text → Speech → MP4 video engine. Uses edge-tts (free, no API key).
Needs ffmpeg installed separately.

Output: black-background MP4 with white subtitles and Vietnamese AI voice.
"""
import re
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List

from src.tts_engine import tts_sync, tts_from_file


def _estimate_duration(text: str, chars_per_sec: float = 5.5) -> float:
    """Rough estimate of how many seconds it takes to read this text."""
    return max(len(text.strip()) / chars_per_sec, 1.0)


def _split_into_subtitle_chunks(text: str, max_chars: int = 60) -> List[str]:
    """Split text into subtitle-sized chunks (sentences or phrases)."""
    raw = re.split(r"(?<=[.!?。！？\n])\s+", text)
    chunks: List[str] = []
    for part in raw:
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_chars:
            chunks.append(part)
        else:
            sub = re.split(r"(?<=[,;，；])\s+", part)
            current = ""
            for s in sub:
                s = s.strip()
                if not s:
                    continue
                if len(current) + len(s) > max_chars and current:
                    chunks.append(current)
                    current = s
                else:
                    current = current + " " + s if current else s
            if current:
                chunks.append(current)
    return [c for c in chunks if c]


def _generate_srt(chunks: List[str], output_path: Path) -> None:
    """Generate an .srt subtitle file from text chunks with estimated timings."""
    lines: List[str] = []
    idx = 1
    current_ms = 0
    for chunk in chunks:
        duration_sec = _estimate_duration(chunk)
        start_ms = current_ms
        end_ms = current_ms + int(duration_sec * 1000)

        def _fmt(ms: int) -> str:
            h = ms // 3600000
            m = (ms % 3600000) // 60000
            s = (ms % 60000) // 1000
            mm = ms % 1000
            return f"{h:02d}:{m:02d}:{s:02d},{mm:03d}"

        lines.append(str(idx))
        lines.append(f"{_fmt(start_ms)} --> {_fmt(end_ms)}")
        lines.append(chunk)
        lines.append("")
        idx += 1
        current_ms = end_ms + 300

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _get_audio_duration(audio_path: Path) -> float:
    """Use ffprobe to get exact audio duration."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", str(audio_path),
            ],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return 0.0


def _scale_srt_timings(srt_path: Path, audio_duration: float) -> None:
    """After generating audio, rescale subtitle timings to match exact audio length."""
    text = srt_path.read_text(encoding="utf-8")
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2}),(\d{3})")
    matches = list(pattern.finditer(text))
    if not matches:
        return
    last_end_ms = int(matches[-1].group(5)) * 3600000 + int(matches[-1].group(6)) * 60000 + int(matches[-1].group(7)) * 1000 + int(matches[-1].group(8))
    if last_end_ms <= 0 or audio_duration <= 0:
        return
    ratio = (audio_duration * 1000) / last_end_ms

    def _scale(match: re.Match) -> str:
        sh, sm, ss, sms, eh, em, es, ems = match.groups()
        start_ms = int(sh) * 3600000 + int(sm) * 60000 + int(ss) * 1000 + int(sms)
        end_ms = int(eh) * 3600000 + int(em) * 60000 + int(es) * 1000 + int(ems)
        start_ms = int(start_ms * ratio)
        end_ms = int(end_ms * ratio)

        def _fmt(ms: int) -> str:
            h = ms // 3600000
            m = (ms % 3600000) // 60000
            s = (ms % 60000) // 1000
            mm = ms % 1000
            return f"{h:02d}:{m:02d}:{s:02d},{mm:03d}"

        return f"{_fmt(start_ms)} --> {_fmt(end_ms)}"

    new_text = pattern.sub(_scale, text)
    srt_path.write_text(new_text, encoding="utf-8")


def text_to_video(
    text: str,
    output_path: str | Path,
    slow: bool = True,
    resolution: str = "1280x720",
    font_size: int = 32,
    bg_color: str = "black",
    subtitle_color: str = "white",
    temp_dir: Optional[Path] = None,
    background_music: Optional[Path] = None,
    music_volume: float = 0.12,
    show_subtitles: bool = False,
) -> str:
    """Convert Vietnamese text → MP4 video with AI voice and subtitles.

    Args:
        text: Vietnamese text.
        output_path: Path to save .mp4.
        slow: Speak slowly if True.
        resolution: Video resolution "WxH".
        font_size: Subtitle font size.
        bg_color: Background color name.
        subtitle_color: Subtitle color name.
        temp_dir: Where to store temp files.
        background_music: Path to background music file (optional).
        music_volume: Volume of background music (0.0-1.0, default 0.12).
        show_subtitles: Whether to burn subtitles into video (default False).

    Returns:
        Path to generated MP4.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if temp_dir is None:
        temp_dir = Path(tempfile.gettempdir()) / "tts_video"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Cleanup text: loại bỏ hoàn toàn mã thẻ XML nếu có, chỉ giữ lại chữ và dấu câu chuẩn
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'[^\w\s.,!?]', '', text)

    # 1. Generate MP3
    mp3_path = temp_dir / "audio.mp3"
    print("  [TTS] Dang tao giong noi (gTTS)...")
    tts_sync(text, mp3_path, slow=slow, warm=True)

    # 2. Get exact audio duration
    audio_duration = _get_audio_duration(mp3_path)
    if audio_duration <= 0:
        audio_duration = _estimate_duration(text)
        print(f"  [WARN] Khong do duoc do dai audio, uoc tinh: {audio_duration:.1f}s")

    # 3. Generate SRT (chỉ tạo nếu show_subtitles=True)
    srt_path = temp_dir / "subs.srt"
    if show_subtitles:
        chunks = _split_into_subtitle_chunks(text)
        _generate_srt(chunks, srt_path)
        _scale_srt_timings(srt_path, audio_duration)

    # 4. Burn subtitles + audio into MP4 with ffmpeg
    print("  [VIDEO] Dang xuat video...")

    srt_path_escaped = srt_path.as_posix().replace(':', '\\:')
    
    if background_music and background_music.exists():
        # Mix nhạc nền với audio gốc
        if show_subtitles:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg_color}:s={resolution}:d={audio_duration}",
                "-i", str(mp3_path),
                "-i", str(background_music),
                "-filter_complex", f"[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2,volume={music_volume}[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-vf", f"subtitles='{srt_path_escaped}':force_style='FontSize={font_size},PrimaryColour=&HFFFFFF&'",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg_color}:s={resolution}:d={audio_duration}",
                "-i", str(mp3_path),
                "-i", str(background_music),
                "-filter_complex", f"[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=2,volume={music_volume}[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]
    else:
        # Không có nhạc nền
        if show_subtitles:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg_color}:s={resolution}:d={audio_duration}",
                "-i", str(mp3_path),
                "-vf", f"subtitles='{srt_path_escaped}':force_style='FontSize={font_size},PrimaryColour=&HFFFFFF&'",
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg_color}:s={resolution}:d={audio_duration}",
                "-i", str(mp3_path),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]

    subprocess.run(cmd, check=True)

    # Cleanup temp
    mp3_path.unlink(missing_ok=True)
    srt_path.unlink(missing_ok=True)

    print(f"  [OK] Video: {output_path}")
    return str(output_path)


def video_from_file(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    slow: bool = False,
    background_music: Optional[Path] = None,
    music_volume: float = 0.12,
    show_subtitles: bool = False,
    **kwargs,
) -> str:
    """Read a Vietnamese .txt file and convert to MP4 video."""
    input_path = Path(input_path)
    text = input_path.read_text(encoding="utf-8")
    if output_path is None:
        output_path = input_path.with_suffix(".mp4")
    return text_to_video(text, output_path, slow=slow, background_music=background_music, music_volume=music_volume, show_subtitles=show_subtitles, **kwargs)
