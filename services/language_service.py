"""
Language detection service - lightweight detection, LLM handles translation.
Supports: Slovak (sk), Hungarian (hu), English (en)
"""
import logging
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["sk", "hu", "en"]

LANGUAGE_NAMES = {
    "sk": "Slovak (Slovencina)",
    "hu": "Hungarian (Magyar)",
    "en": "English",
}


class LanguageService:
    """Lightweight language detection."""

    def detect_language(self, text: str) -> str:
        """Detect language of text. Returns ISO code (sk, hu, en)."""
        if not text or len(text.strip()) < 10:
            return "en"

        try:
            detected = detect(text)
            if detected in SUPPORTED_LANGUAGES:
                return detected
            return "en"
        except LangDetectException:
            return "en"

    def is_supported_language(self, lang_code: str) -> bool:
        return lang_code in SUPPORTED_LANGUAGES

    def get_language_name(self, lang_code: str) -> str:
        return LANGUAGE_NAMES.get(lang_code, lang_code.upper())

