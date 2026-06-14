"""Gemini API client with key rotation and local fallback."""
import json
import re
import time
import logging
from typing import Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2


class UsageStats:
    """Simple token usage tracker."""

    def __init__(self):
        self._data: dict[str, dict[str, int]] = {}

    def add(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        if model not in self._data:
            self._data[model] = {"prompt": 0, "completion": 0}
        self._data[model]["prompt"] += prompt_tokens
        self._data[model]["completion"] += completion_tokens

    @property
    def total_prompt(self) -> int:
        return sum(v["prompt"] for v in self._data.values())

    @property
    def total_completion(self) -> int:
        return sum(v["completion"] for v in self._data.values())


class GeminiClient:
    """
    Supports multiple API keys.
    Fallback order: key1 → key2 → ... → local (Groq/Ollama).
    """

    def __init__(self, api_keys: list[str] | str, local_fallback=None) -> None:
        if isinstance(api_keys, str):
            api_keys = [api_keys]
        seen = set()
        self._keys: list[str] = []
        for k in api_keys:
            if k and k not in seen:
                seen.add(k)
                self._keys.append(k)

        self._key_idx = 0
        self._client = genai.Client(api_key=self._keys[0]) if self._keys and genai else None
        self._exhausted: set[str] = set()
        self.usage = UsageStats()
        self._local = local_fallback

    def _next_key(self) -> bool:
        """Switch to next key. Returns False if exhausted."""
        while self._key_idx + 1 < len(self._keys):
            self._key_idx += 1
            k = self._keys[self._key_idx]
            if k not in self._exhausted:
                self._client = genai.Client(api_key=k)
                print(f"  [KEY] Chuyen sang API key {self._key_idx + 1}/{len(self._keys)}", flush=True)
                return True
        return False

    @property
    def all_keys_exhausted(self) -> bool:
        return len(self._exhausted) >= len(self._keys)

    # ── Low-level call ────────────────────────────────────────────────────────

    @staticmethod
    def _is_key_exhausted(error_msg: str) -> bool:
        """Detect quota/billing/invalid key errors."""
        msg = error_msg.lower()
        patterns = [
            "resource_exhausted", "quota", "billing", "payment_required",
            "permission_denied", "unauthenticated", "invalid api key",
            "api key not valid", "forbidden", "disabled", "revoked",
            "user_rate_limit", "rate_limit_exceeded", "exceeded",
        ]
        return any(p in msg for p in patterns)

    @staticmethod
    def _parse_retry_delay(error_msg: str) -> int | None:
        m = re.search(r"retry.*?after\s*(\d+)\s*s", error_msg, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _call(self, model_name: str, prompt: str, temperature: float = 0.3) -> str:
        if self.all_keys_exhausted:
            if self._local and self._local.is_available():
                return self._local._call(prompt, temperature)
            raise RuntimeError("Tat ca API key het quota va khong co local fallback")

        config = types.GenerateContentConfig(temperature=temperature)

        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if resp.usage_metadata:
                    self.usage.add(
                        model_name,
                        resp.usage_metadata.prompt_token_count or 0,
                        resp.usage_metadata.candidates_token_count or 0,
                    )
                return resp.text or ""
            except Exception as exc:
                err = str(exc)
                is_exhausted = self._is_key_exhausted(err)
                if is_exhausted:
                    current_key = self._keys[self._key_idx]
                    self._exhausted.add(current_key)
                    print(f"  [KEY] Key {self._key_idx + 1} het quota/bi khoa.", flush=True)
                    if self._next_key():
                        return self._call(model_name, prompt, temperature)
                    print("  [LOCAL] Tat ca Gemini key het quota → chuyen sang local...", flush=True)
                    if self._local and self._local.is_available():
                        return self._local._call(prompt, temperature)
                    raise RuntimeError("Tat ca API key het quota. Can them key hoac cai Ollama/Groq.")
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = self._parse_retry_delay(err) or (RETRY_BASE_DELAY ** (attempt + 1))
                print(f"  [WAIT] Rate limit - cho {delay}s...", flush=True)
                time.sleep(delay)
        return ""

    # ── JSON parsing ──────────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if m:
            text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            starts = [s for s in (text.find("{"), text.find("[")) if s != -1]
            if starts:
                start = min(starts)
                brace = 0
                in_string = False
                escaped = False
                end = start
                for i, c in enumerate(text[start:], start):
                    if escaped:
                        escaped = False
                        continue
                    if c == "\\":
                        escaped = True
                        continue
                    if c == '"':
                        in_string = not in_string
                        continue
                    if not in_string:
                        if c in "{[":
                            brace += 1
                        elif c in "}]":
                            brace -= 1
                            if brace == 0:
                                end = i + 1
                                break
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Khong the parse JSON: {text[:300]}")

    # ── High-level translation ─────────────────────────────────────────────────

    def translate_literal(self, text_zh: str, glossary: str, context: str = "") -> str:
        # If all Gemini keys exhausted, delegate directly to local client
        if self.all_keys_exhausted and self._local and self._local.is_available():
            return self._local.translate_literal(text_zh, glossary, context)
        prompt = f"""NHIEM VU: Dich tieu thuyet Trung Quoc sang tieng Viet van hoc co dien.

QUY TAC BAT BUOC:
1. Dung nghia 100%, khong them khong bot noi dung
2. Van phong co dien truoc 1975: pham la, boi vay, dai khai, boi le, hoac la...hoac la, vi the
3. Xuong dong rieng moi doan

THUAT NGU BAT BUOC:
- 你道 / 看官道 = "Nguoi hoi rang" (KHONG dich la "nguoi dao rang")
- 看官 = "Doc gia" (KHONG la "khan quan")
- 和尚 = "hoa thuong" (KHONG la "nha su")
- 某生/某子/某道人 = "mo sinh"/"mo tu"/"mo dao nhan"
- 未央 = "Vi Uong" (Han Viet)
- 夜未央 = "Da vi uong"
- 诗经 = "Kinh Thi"
- 士人 = "si nhan"
- 书生 = "thu sinh"
- 大约 = "dai khai"
- 凡是 = "pham la"
- 故/因此 = "boi vay"

XUNG HO: han, nang, ta, nguoi, lao (KHONG dung anh/em/toi/ban)

Glossary:
{glossary}

Context:
{context}

Van ban:
{text_zh}

Ban dich tieng Viet:"""
        return self._call("gemini-2.0-flash", prompt, temperature=0.1)

    def translate_edit(self, draft_vi: str, genre: str = "") -> str:
        # If all Gemini keys exhausted, delegate directly to local client
        if self.all_keys_exhausted and self._local and self._local.is_available():
            return self._local.translate_edit(draft_vi, genre)
        prompt = f"""Chinh sua ban dich tho sau cho tu nhien, dung van phong tien hiep co dien.

Quy tac:
- Khong thay doi nghia, khong bo cau, khong hien dai hoa
- Giu: nguoi, han, ta, nang, dao huu, tien boi
- Chi sua dau cau, tu noi, ngu phap

Ban dich tho:
{draft_vi}

Ban dich hoan chinh:"""
        return self._call("gemini-2.5-pro", prompt, temperature=0.1)

    def analyze_novel(self, sample_text: str) -> dict:
        prompt = f"""Phân tích đoạn mở đầu tiểu thuyết Trung Quốc sau. Trả về JSON với các trường:
- title (tên truyện tiếng Việt)
- author (tác giả)
- genre (thể loại)
- characters (list các nhân vật chính với tên tiếng Trung và tiếng Việt)
- terms (list các thuật ngữ/tên địa danh với nghĩa tiếng Việt)

── Đoạn văn ────────────────────────────────────────
{sample_text[:5000]}
────────────────────────────────────────────────────

JSON:"""
        text = self._call("gemini-2.0-flash", prompt, temperature=0.2)
        return self._parse_json(text)

    def summarize_chapter(self, text_vi: str, chapter_num: int) -> str:
        prompt = f"Tóm tắt chương {chapter_num} trong 3-5 câu:\n{text_vi[:4000]}\n\nTóm tắt:"
        return self._call("gemini-2.0-flash", prompt, temperature=0.3)
