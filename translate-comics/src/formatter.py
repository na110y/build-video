"""Text formatting pipeline for translated novels."""
import re


def normalize_punctuation(text: str) -> str:
    """Standardize punctuation while preserving original double quotes."""
    # Normalize ellipsis
    text = text.replace("…", "...")
    text = re.sub(r"\.{3,}", "...", text)
    # Fix multiple spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize dashes
    text = text.replace("—", "-").replace("–", "-")
    # Ensure proper spacing after sentence-ending punctuation
    text = re.sub(r"([.!?])([^ \n\"'])", r"\1 \2", text)
    return text.strip()


def split_dialogue(text: str) -> str:
    """Split dialogue lines onto separate lines."""
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        # If a line contains quoted speech mixed with narration, try to split
        # But keep it simple: if the whole line is dialogue, leave as is
        stripped = line.strip()
        if not stripped:
            out.append("")
            continue
        out.append(stripped)
    return "\n".join(out)


def split_long_paragraphs(text: str, max_sentences: int = 6) -> str:
    """Split long paragraphs into smaller chunks."""
    paragraphs = text.split("\n\n")
    out: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        sentences = re.split(r'(?<=[.!?。！？])\s+', para)
        if len(sentences) <= max_sentences:
            out.append(para)
            continue
        chunk: list[str] = []
        count = 0
        for sent in sentences:
            chunk.append(sent)
            count += 1
            if count >= max_sentences:
                out.append(" ".join(chunk))
                chunk = []
                count = 0
        if chunk:
            out.append(" ".join(chunk))
    return "\n\n".join(out)


def _remove_stray_cjk(text: str) -> str:
    """Remove stray Chinese characters (CJK) mixed into Vietnamese text.
    Keeps characters inside quotation marks (names/terms on purpose).
    """
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if re.match(r"^[\u4e00-\u9fff\u3400-\u4dbf\s]+$", line.strip()):
            continue
        cleaned = ""
        in_quotes = False
        quote_char = None
        for ch in line:
            if ch in '"\'':
                if not in_quotes:
                    in_quotes = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quotes = False
                    quote_char = None
                cleaned += ch
                continue
            if in_quotes:
                cleaned += ch
                continue
            if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
                continue
            cleaned += ch
        out.append(cleaned)
    return "\n".join(out)


def format_novel_text(text: str) -> str:
    """Complete formatting pipeline for novel translations."""
    text = normalize_punctuation(text)
    text = split_dialogue(text)
    text = split_long_paragraphs(text, max_sentences=6)
    text = _remove_stray_cjk(text)
    return text
