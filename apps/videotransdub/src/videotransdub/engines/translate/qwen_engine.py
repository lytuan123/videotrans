from __future__ import annotations

import logging
import re
from typing import Any

from ...models import SubtitleSegment
from ...settings import AppSettings
from .base import BaseTranslator

logger = logging.getLogger(__name__)


class QwenTranslator(BaseTranslator):
    """Translation engine using Alibaba Qwen/DashScope API.

    Supports:
    - qwen-mt-turbo (dedicated machine translation, fastest)
    - qwen-mt-plus (higher quality MT)
    - qwen-turbo / qwen-plus / qwen-max (general LLM, uses prompt-based translation)
    - qwen3-* models (latest generation)

    Free tier available at: https://bailian.console.aliyun.com/
    """

    # Language code mapping for qwen-mt models
    LANG_MAP = {
        "vi": "Vietnamese",
        "en": "English",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
        "th": "Thai",
        "id": "Indonesian",
        "pt": "Portuguese",
        "ar": "Arabic",
        "hi": "Hindi",
        "it": "Italian",
    }

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.api_key = settings.translation.qwen_api_key
        self.model = settings.translation.model
        self.batch_size = settings.translation.batch_size
        self.target_lang = settings.pipeline.target_language

        if not self.api_key:
            raise ValueError(
                "Qwen API key is required. Set translation.qwen_api_key in config "
                "or QWEN_API_KEY environment variable."
            )

    def translate(self, segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
        try:
            import dashscope
        except ImportError as exc:
            raise RuntimeError(
                "dashscope is not installed. Run: pip install dashscope"
            ) from exc

        target_name = self.LANG_MAP.get(self.target_lang, self.target_lang)
        logger.info(
            "Qwen translate: model=%s, target=%s, %d segments",
            self.model, target_name, len(segments),
        )

        translated: list[SubtitleSegment] = []
        # Process in batches
        for i in range(0, len(segments), self.batch_size):
            batch = segments[i:i + self.batch_size]
            texts = [seg.text for seg in batch]
            batch_text = "\n".join(texts)

            result_text = self._translate_batch(dashscope, batch_text, target_name)
            result_lines = result_text.strip().split("\n")

            for j, seg in enumerate(batch):
                trans_text = result_lines[j].strip() if j < len(result_lines) else seg.text
                translated.append(seg.model_copy(update={"translated_text": trans_text}))

            logger.info("  Translated batch %d-%d", i, min(i + self.batch_size, len(segments)))

        return translated

    def _translate_batch(self, dashscope: Any, text: str, target_name: str) -> str:
        """Translate a batch of text lines using Qwen API."""
        model = self.model
        if model == "qwen-turbo":
            model = "qwen-mt-turbo"

        if model.startswith("qwen-mt"):
            return self._translate_mt(dashscope, text, target_name, model)
        else:
            return self._translate_llm(dashscope, text, target_name, model)

    def _translate_mt(self, dashscope: Any, text: str, target_name: str, model: str) -> str:
        """Use dedicated qwen-mt models for translation."""
        translation_options: dict[str, Any] = {
            "source_lang": "auto",
            "target_lang": target_name,
        }

        glossary = self.settings.translation.glossary
        if glossary:
            terms = [{"source": k, "target": v} for k, v in glossary.items()]
            translation_options["terms"] = terms

        response = dashscope.Generation.call(
            api_key=self.api_key,
            model=model,
            messages=[{"role": "user", "content": text}],
            result_format="message",
            translation_options=translation_options,
        )

        if response.code or not response.output:
            raise RuntimeError(f"Qwen MT error: {getattr(response, 'message', 'unknown')}")

        return response.output.choices[0].message.content

    def _translate_llm(self, dashscope: Any, text: str, target_name: str, model: str) -> str:
        """Use general Qwen LLM models for translation via prompt."""
        prompt = (
            f"You are a professional subtitle translator. "
            f"Translate the following subtitle lines to {target_name}. "
            f"Keep the same number of lines. Output ONLY the translated text, "
            f"one line per input line. Do not add explanations.\n\n{text}"
        )

        response = dashscope.Generation.call(
            api_key=self.api_key,
            model=model,
            messages=[
                {"role": "system", "content": "You are a top-tier Subtitle Translation Engine."},
                {"role": "user", "content": prompt},
            ],
            result_format="message",
        )

        if response.code or not response.output:
            raise RuntimeError(f"Qwen LLM error: {getattr(response, 'message', 'unknown')}")

        content = response.output.choices[0].message.content
        # Try to extract from TRANSLATE_TEXT tags if present
        match = re.search(r"<TRANSLATE_TEXT>(.*?)</TRANSLATE_TEXT>", content, re.S)
        if match:
            return match.group(1).strip()
        return content.strip()
