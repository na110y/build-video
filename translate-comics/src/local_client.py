"""Local fallback clients: Groq, OpenAI, and Ollama. Priority: Groq → OpenAI → Ollama."""
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Shared prompt templates
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Bạn là dịch giả tiểu thuyết Trung Quốc hàng đầu Việt Nam, "
    "chuyên dịch theo phong cách văn học tiếng Việt trước năm 1975 — "
    "trau chuốt, có hồn, đúng nghĩa, tự nhiên."
)

_ONEPASS_TEMPLATE = """\
You are an expert translator specializing in classical Chinese novels (Ming/Qing dynasty) into literary Vietnamese.

CRITICAL RULES:
1. Translate ONLY the provided text. Do NOT add any sentences, paragraphs, explanations, or commentary that are not in the original.
2. Translate 100% of the original — do not skip or omit anything.
3. Use pre-1975 Vietnamese literary style.
4. Each sentence/clause that forms a natural paragraph break should be on its own line.
5. Output full Vietnamese with diacritics (not ASCII romanization).

TERM MAPPING (apply these exactly, with proper diacritics):
- 你道 / 看官道 => "Ngươi hỏi rằng" (NEVER "ngươi đạo rằng")
- 看官 => "Độc giả" (NEVER "khán quan", NEVER "bạn đọc")
- 和尚 => "hòa thượng" (NEVER "nhà sư")
- 某生 => "mỗ sinh", 某子 => "mỗ tử", 某道人 => "mỗ đạo nhân"
- 未央 => "Vị Ương" (Han Viet, do NOT translate the meaning)
- 夜未央 => "Dạ vị ương"
- 诗经 => "Kinh Thi"
- 士人 => "sĩ nhân"
- 书生 => "thư sinh"
- 表德 => "biểu đức"
- 大约 => "đại khái" (NEVER just "đại")
- 凡是 => "phàm là"
- 故此 / 因此 / 故 => "bởi vậy"

PRONOUNS: hắn, nàng, ta, ngươi, lão (NEVER anh/em/tôi/bạn/mình)
{glossary_block}{context_block}
ORIGINAL TEXT:
{text}

VIETNAMESE TRANSLATION (translate ONLY the above, nothing more):"""

_ANALYZE_TEMPLATE = """\
Phân tích đoạn mở đầu tiểu thuyết Trung Quốc sau. Trả về JSON hợp lệ với các trường:
- title (tên truyện tiếng Việt)
- author (tác giả)
- genre (thể loại: Tiên hiệp/Huyền huyễn/Tu chân/Võ hiệp/Lịch sử/Cổ đại/Đô thị/Ngôn tình)
- characters (list nhân vật chính: [{{"name_zh": "...", "name_vi": "..."}}])
- terms (list thuật ngữ/địa danh: [{{"term_zh": "...", "term_vi": "..."}}])

Chỉ trả về JSON thuần túy, không có text nào khác.

Đoạn văn:
{text}

JSON:"""


def _build_onepass_prompt(text_zh: str, glossary: str, context: str) -> str:
    g = f"\nBANG THUAT NGU:\n{glossary}\n" if glossary.strip() else ""
    c = f"\nNGU CANH CHUONG TRUOC:\n{context}\n" if context.strip() else ""
    return _ONEPASS_TEMPLATE.format(glossary_block=g, context_block=c, text=text_zh)


# Common mistranslation fixes (applied after LLM output)
_POSTPROCESS_RULES = [
    # 你道 — narrative device "you might wonder why..."
    (r'\bNgươi đạo rằng\b', 'Ngươi hỏi rằng'),
    (r'\bngươi đạo rằng\b', 'ngươi hỏi rằng'),
    (r'\bngươi đạo\b', 'ngươi nói'),
    # 看官 — reader address
    (r'\bKhán quan\b', 'Độc giả'),
    (r'\bkhán quan\b', 'độc giả'),
    (r'\bKhán giả\b', 'Độc giả'),
    (r'\bkhán giả\b', 'độc giả'),
    (r'\bĐọc giả\b', 'Độc giả'),
    # 和尚 — monk
    (r'\bnhà sư\b', 'hòa thượng'),
    (r'\bsư sãi\b', 'hòa thượng'),
    # 大约 truncation (model sometimes cuts off "khái")
    (r'\bĐại,\b', 'Đại khái,'),
    (r'\bđại,\b', 'đại khái,'),
    # Pronouns — third person
    (r'\banh ta\b', 'hắn'),
    (r'\banh ấy\b', 'hắn'),
    (r'\bông ta\b', 'hắn'),
    (r'\bcô ta\b', 'nàng'),
    (r'\bcô ấy\b', 'nàng'),
]


def _postprocess_translation(text: str) -> str:
    """Fix common mistranslations from LLM output."""
    for pattern, replacement in _POSTPROCESS_RULES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _parse_json_text(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Base class for OpenAI-compatible APIs (Groq + OpenAI share same SDK style)
# ──────────────────────────────────────────────────────────────────────────────

class _OpenAICompatClient:
    """Base for Groq and OpenAI — both use openai-style chat completions."""

    _SDK_MODULE: str = ""   # "groq" or "openai"
    _SDK_CLASS: str = ""    # "Groq" or "OpenAI"
    MODEL: str = ""

    def __init__(self, api_key: str) -> None:
        self._key = api_key
        self._client = None
        if not api_key:
            return
        try:
            mod = __import__(self._SDK_MODULE)
            cls = getattr(mod, self._SDK_CLASS)
            self._client = cls(api_key=api_key)
        except Exception as e:
            logger.warning("%s init failed: %s", self._SDK_CLASS, e)

    def is_available(self) -> bool:
        return self._client is not None and bool(self._key)

    def _call(self, prompt: str, temperature: float = 0.2) -> str:
        if not self._client:
            raise RuntimeError(f"{self._SDK_CLASS} client not initialized")
        resp = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=8192,
        )
        return resp.choices[0].message.content or ""

    # ── Translation interface ─────────────────────────────────────────────────

    def translate_literal(self, text_zh: str, glossary: str, context: str = "") -> str:
        """One-pass literary translation (no separate edit step needed)."""
        result = self._call(_build_onepass_prompt(text_zh, glossary, context), temperature=0.2)
        return _postprocess_translation(result)

    def translate_edit(self, draft_vi: str, genre: str = "") -> str:
        """No-op: translate_literal already produces polished output."""
        return draft_vi

    def analyze_novel(self, sample_text: str) -> dict:
        prompt = _ANALYZE_TEMPLATE.format(text=sample_text[:3000])
        text = self._call(prompt, temperature=0.1)
        return _parse_json_text(text)

    def summarize_chapter(self, text_vi: str, chapter_num: int) -> str:
        prompt = f"Tóm tắt chương {chapter_num} trong 3-5 câu:\n{text_vi[:4000]}\n\nTóm tắt:"
        return self._call(prompt, temperature=0.3)


# ──────────────────────────────────────────────────────────────────────────────
# Groq Client  (priority 1 — free tier, llama-3.3-70b)
# ──────────────────────────────────────────────────────────────────────────────

class GroqClient(_OpenAICompatClient):
    _SDK_MODULE = "groq"
    _SDK_CLASS = "Groq"
    MODEL = "llama-3.3-70b-versatile"


# ──────────────────────────────────────────────────────────────────────────────
# OpenAI Client  (priority 2 — gpt-4o-mini)
# ──────────────────────────────────────────────────────────────────────────────

class OpenAIClient(_OpenAICompatClient):
    _SDK_MODULE = "openai"
    _SDK_CLASS = "OpenAI"
    MODEL = "gpt-4o-mini"


# ──────────────────────────────────────────────────────────────────────────────
# Ollama Client  (priority 4 — local, no API key)
# ──────────────────────────────────────────────────────────────────────────────

class OllamaClient:
    MODEL = "qwen2.5:7b"

    def __init__(self, model: str = MODEL, host: str = "http://localhost:11434") -> None:
        self._model = model
        self._host = host
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import ollama
            client = ollama.Client(host=self._host)
            models = client.list()
            names = [m.model for m in models.models]
            self._available = any(self._model.split(":")[0] in n for n in names)
            if not self._available:
                logger.warning("Ollama: model '%s' chua co. Chay: ollama pull %s", self._model, self._model)
        except Exception as e:
            self._available = False
            logger.warning("Ollama server chua chay: %s", e)
        return self._available

    def _call(self, prompt: str, temperature: float = 0.2) -> str:
        import ollama
        client = ollama.Client(host=self._host)
        resp = client.generate(
            model=self._model,
            prompt=prompt,
            options={"temperature": temperature, "num_ctx": 4096, "top_p": 0.9},
        )
        return resp.response or ""

    def translate_literal(self, text_zh: str, glossary: str, context: str = "") -> str:
        raw = self._call(_build_onepass_prompt(text_zh, glossary, context), temperature=0.2)
        return _clean_ollama_output(raw)

    def translate_edit(self, draft_vi: str, genre: str = "") -> str:
        return draft_vi

    def analyze_novel(self, sample_text: str) -> dict:
        prompt = _ANALYZE_TEMPLATE.format(text=sample_text[:2000])
        text = self._call(prompt, temperature=0.1)
        return _parse_json_text(text)

    def summarize_chapter(self, text_vi: str, chapter_num: int) -> str:
        return self._call(
            f"Tóm tắt chương {chapter_num} trong 3-5 câu:\n{text_vi[:4000]}\n\nTóm tắt:",
            temperature=0.3,
        )


def _clean_ollama_output(text: str) -> str:
    """Strip model commentary and wrapper text from Ollama output."""
    quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    if quoted:
        longest = max(quoted, key=len)
        if len(longest) > 50:
            return longest.strip().strip('"').strip()

    for marker in ["Bản dịch hoàn chỉnh", "Bản dịch chỉnh sửa", "Bản dịch tiếng Việt"]:
        idx = text.find(marker)
        if idx != -1:
            after = text[idx + len(marker):]
            after = re.sub(r'^[：:\s]*[\n\r]*(?:─+\s*)?[\n\r]*', '', after)
            end_idx = after.find('── Kết thúc')
            if end_idx != -1:
                after = after[:end_idx]
            note_m = re.search(r'\n\s*(?:Lưu ý|Note):', after, re.I)
            if note_m:
                after = after[:note_m.start()]
            lines = [
                l.strip() for l in after.splitlines()
                if l.strip() and not re.match(
                    r"^(bạn yêu cầu|tuy nhiên|dưới đây là|here is|note|lưu ý|tôi có thể|translation|below is)",
                    l.strip(), re.I,
                )
                and not l.strip().startswith(("─", "*", "["))
            ]
            joined = "\n".join(lines).strip().strip('"').strip()
            if len(joined) > 20:
                return joined

    lines = text.splitlines()
    cleaned = [
        l.strip() for l in lines
        if l.strip() and not re.match(
            r"^(bạn yêu cầu|tuy nhiên|dưới đây là|here is|below is|translation|note|lưu ý"
            r"|bản dịch (chỉnh sửa|hoàn chỉnh)[:：]|kết thúc|─+|\*+|\[.*\])",
            l.strip(), re.I,
        )
    ]
    return "\n".join(cleaned).strip().strip('"').strip()


# ──────────────────────────────────────────────────────────────────────────────
# FallbackChain — Groq → OpenAI → Ollama  (Plan V4 priority)
# ──────────────────────────────────────────────────────────────────────────────

class FallbackChain:
    """Try clients in order: Groq → OpenAI → Ollama."""

    def __init__(
        self,
        groq_key: str = "",
        openai_key: str = "",
        ollama_model: str = OllamaClient.MODEL,
    ) -> None:
        self._groq = GroqClient(groq_key) if groq_key else None
        self._openai = OpenAIClient(openai_key) if openai_key else None
        self._ollama = OllamaClient(ollama_model)
        self._active = None

    def is_available(self) -> bool:
        if self._groq and self._groq.is_available():
            self._active = self._groq
            print("  [GROQ] Dung Groq (llama-3.3-70b)", flush=True)
            return True
        if self._openai and self._openai.is_available():
            self._active = self._openai
            print("  [OPENAI] Dung OpenAI (gpt-4o-mini)", flush=True)
            return True
        if self._ollama.is_available():
            self._active = self._ollama
            print("  [OLLAMA] Dung Ollama local", flush=True)
            return True
        self._active = None
        return False

    def _call(self, prompt: str, temperature: float = 0.2) -> str:
        if not self._active:
            raise RuntimeError("Khong co fallback kha dung")
        return self._active._call(prompt, temperature)

    def translate_literal(self, text_zh: str, glossary: str, context: str = "") -> str:
        if not self._active:
            raise RuntimeError("Khong co fallback kha dung")
        return self._active.translate_literal(text_zh, glossary, context)

    def translate_edit(self, draft_vi: str, genre: str = "") -> str:
        if not self._active:
            return draft_vi
        return self._active.translate_edit(draft_vi, genre)

    def analyze_novel(self, sample_text: str) -> dict:
        if not self._active:
            raise RuntimeError("Khong co fallback kha dung")
        return self._active.analyze_novel(sample_text)

    def summarize_chapter(self, text_vi: str, chapter_num: int) -> str:
        if not self._active:
            return ""
        return self._active.summarize_chapter(text_vi, chapter_num)
