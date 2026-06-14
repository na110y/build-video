"""Text-to-Speech engine using edge-tts (free, no API key, high quality Vietnamese voice)."""
import asyncio
import re
from pathlib import Path
from typing import Optional

try:
    import edge_tts
except ImportError:
    edge_tts = None  # type: ignore

# Vietnamese voices from Microsoft Edge TTS
VI_VOICES = [
    "vi-VN-HoaiMyNeural",      # Female, warm, natural  ← RECOMMENDED
    "vi-VN-NamMinhNeural",      # Male, clear
]

DEFAULT_VOICE = VI_VOICES[0]


def _clean_text_for_tts(text: str) -> str:
    """Remove markdown, excessive whitespace, and normalize for reading."""
    # Remove citation markers like [1], [2]
    text = re.sub(r"\[\d+\]", "", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove markdown formatting
    text = re.sub(r"[#*_~`>|-]", "", text)
    # Remove HTML-like tags
    text = re.sub(r"<[^>]+>", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    # Break extremely long lines for better pacing
    text = text.replace("。", "。\n").replace("．", "．\n")
    text = text.replace("!", "!\n").replace("?", "?\n")
    return text.strip()


def _split_into_chunks(text: str, max_chars: int = 3000) -> list[str]:
    """Split long text into chunks that edge-tts can handle comfortably."""
    paragraphs = text.split("\n")
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = current + "\n" + para if current else para
    if current:
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chars]]


async def _generate_chunk(text: str, voice: str, output_path: str, rate: str = "+0%") -> None:
    """Generate a single audio chunk."""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


async def text_to_speech(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    volume: str = "+0%",
) -> str:
    """Convert Vietnamese text to MP3 audio.

    Args:
        text: Vietnamese text to read.
        output_path: Where to save the .mp3 file.
        voice: Edge TTS voice ID. Default is vi-VN-HoaiMyNeural (warm female).
        rate: Speed, e.g. "+0%", "-10%" (slower), "+10%" (faster).
        volume: Volume adjustment, e.g. "+0%", "+10%".

    Returns:
        Absolute path to the generated MP3 file.
    """
    if edge_tts is None:
        raise ImportError("edge-tts chua duoc cai. Chay: pip install edge-tts")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = _clean_text_for_tts(text)
    chunks = _split_into_chunks(text, max_chars=3000)

    if len(chunks) == 1:
        # Single chunk — generate directly
        communicate = edge_tts.Communicate(chunks[0], voice, rate=rate, volume=volume)
        await communicate.save(str(output_path))
    else:
        # Multiple chunks — generate temp files then concatenate via ffmpeg
        import tempfile
        temp_files: list[Path] = []
        try:
            for i, chunk in enumerate(chunks):
                tmp = Path(tempfile.gettempdir()) / f"tts_chunk_{i:04d}.mp3"
                communicate = edge_tts.Communicate(chunk, voice, rate=rate, volume=volume)
                await communicate.save(str(tmp))
                temp_files.append(tmp)

            # Concatenate with ffmpeg
            concat_list = Path(tempfile.gettempdir()) / "tts_concat.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for tmp in temp_files:
                    f.write(f"file '{tmp.as_posix()}'\n")

            import subprocess
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list),
                    "-acodec", "copy",
                    str(output_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        finally:
            # Cleanup temp files
            for tmp in temp_files:
                tmp.unlink(missing_ok=True)
            concat_list.unlink(missing_ok=True)

    return str(output_path)


def tts_sync(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> str:
    """Synchronous wrapper for text_to_speech."""
    return asyncio.run(text_to_speech(text, output_path, voice, rate))


def tts_from_file(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    voice: str = DEFAULT_VOICE,
    rate: str = "-5%",  # Slightly slower for novel reading
) -> str:
    """Read a text file and convert to MP3.

    Args:
        input_path: Path to .txt file (Vietnamese).
        output_path: Path to save .mp3. If None, saves next to input file.
        voice: TTS voice.
        rate: Speed. Default -5% for comfortable novel listening.

    Returns:
        Path to generated MP3.
    """
    input_path = Path(input_path)
    text = input_path.read_text(encoding="utf-8")
    if output_path is None:
        output_path = input_path.with_suffix(".mp3")
    return tts_sync(text, output_path, voice, rate)
