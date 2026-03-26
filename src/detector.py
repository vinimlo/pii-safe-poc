"""PII detection engine backed by Microsoft Presidio + spaCy NER.

Detects PII entities in free text and structured JSON data.
Returns structured results with entity type, location, confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider


@dataclass
class PIIEntity:
    """A detected PII entity with its metadata."""

    entity_type: str
    text: str
    start: int
    end: int
    confidence: float

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class DetectionResult:
    """Result of PII detection on a single text input."""

    original_text: str
    entities: list[PIIEntity] = field(default_factory=list)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def has_pii(self) -> bool:
        return self.entity_count > 0

    def to_dict(self) -> dict:
        return {
            "original_text": self.original_text,
            "entity_count": self.entity_count,
            "has_pii": self.has_pii,
            "entities": [e.to_dict() for e in self.entities],
        }


class PIIDetector:
    """Detects PII in text using Presidio's AnalyzerEngine.

    Wraps presidio-analyzer to provide a clean interface for
    detecting PII entities across multiple languages and entity types.
    """

    def __init__(self, languages: list[str] | None = None, model: str = "en_core_web_sm"):
        self._languages = languages or ["en"]
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model}],
        })
        self._analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())

    def detect(self, text: str, language: str = "en") -> DetectionResult:
        """Detect PII entities in a text string."""
        results: list[RecognizerResult] = self._analyzer.analyze(
            text=text,
            language=language,
        )

        # Sort by start position, then by confidence descending
        sorted_results = sorted(results, key=lambda r: (r.start, -r.score))

        # Remove overlapping entities: keep higher-confidence one
        filtered: list[RecognizerResult] = []
        for r in sorted_results:
            if filtered and r.start < filtered[-1].end:
                # Overlap: keep the one with higher confidence
                if r.score > filtered[-1].score:
                    filtered[-1] = r
                continue
            filtered.append(r)

        entities = [
            PIIEntity(
                entity_type=r.entity_type,
                text=text[r.start : r.end],
                start=r.start,
                end=r.end,
                confidence=r.score,
            )
            for r in filtered
        ]

        return DetectionResult(original_text=text, entities=entities)

    def detect_in_dict(
        self, data: dict, language: str = "en"
    ) -> dict[str, DetectionResult]:
        """Detect PII in all string values of a dictionary (one level deep)."""
        results: dict[str, DetectionResult] = {}
        for key, value in data.items():
            if isinstance(value, str):
                result = self.detect(value, language)
                if result.has_pii:
                    results[key] = result
        return results
