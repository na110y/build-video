"""Simple quality checker for translated text."""
import re


class QCResult:
    def __init__(self):
        self.critical: list[str] = []
        self.warnings: list[str] = []

    @property
    def has_critical(self) -> bool:
        return bool(self.critical)


class QualityChecker:
    """Check translation quality by comparing original and translated text."""

    def check(self, original_zh: str, translated_vi: str, glossary: str = "") -> QCResult:
        result = QCResult()

        # Check for remaining Chinese characters outside quotes
        cleaned = re.sub(r'"[^"]*"', '', translated_vi)
        cleaned = re.sub(r"'[^']*'", '', cleaned)
        cjk_left = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', cleaned)
        if len(cjk_left) > 3:
            result.critical.append(f"Con {len(cjk_left)} ky tu Trung trong ban dich")

        # Check for empty translation
        if not translated_vi.strip():
            result.critical.append("Ban dich rong")

        # Check for excessive length difference (might indicate summarization)
        orig_len = len(original_zh)
        trans_len = len(translated_vi)
        if trans_len < orig_len * 0.3:
            result.critical.append("Ban dich qua ngan, co the da bi tom tat")

        # Check sentence count difference
        orig_sentences = len(re.split(r'[。！？.!?]', original_zh))
        trans_sentences = len(re.split(r'[.!?]', translated_vi))
        if abs(orig_sentences - trans_sentences) > max(2, orig_sentences * 0.3):
            result.warnings.append(f"So luong cau khac bieu: goc={orig_sentences}, dich={trans_sentences}")

        return result
