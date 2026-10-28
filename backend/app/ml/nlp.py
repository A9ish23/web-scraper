"""Lightweight text analysis plus optional embedding-based retrieval."""

from __future__ import annotations

import re
import hashlib
from collections import Counter
from functools import lru_cache
from math import sqrt

STOPWORDS = set("a an and are as at be been being by for from had has have he her hers him his i in is it its of on or our she that the their them they this to was we were will with you your not but about after before into over under than then also can could would should may might page home read more share comment article".split())
POSITIVE = set("good great excellent amazing love loved useful helpful success successful best beautiful easy clear enjoy enjoyed positive win improve improvement".split())
NEGATIVE = set("bad poor terrible awful hate hated difficult issue problem fail failed failure negative worst wrong misleading broken".split())
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
WORD_RE = re.compile(r"[\w'-]+", re.UNICODE)
_DOCUMENT_VECTORS: dict[str, object] = {}


def analyze_text(paragraphs: list[str], title: str = "") -> dict:
    """Return transparent, extractive NLP signals without changing source text."""
    paragraphs = [paragraph for paragraph in paragraphs if isinstance(paragraph, str)]
    text = " ".join([title, *paragraphs]).strip()
    sentences = [part.strip() for part in SENTENCE_RE.split(text) if len(part.strip()) > 35]
    terms = [w.lower() for w in WORD_RE.findall(text) if len(w) > 2 and w.lower() not in STOPWORDS]
    frequencies = Counter(terms)
    ranked = []
    for index, sentence in enumerate(sentences):
        tokens = [w.lower() for w in WORD_RE.findall(sentence) if len(w) > 2 and w.lower() not in STOPWORDS]
        score = sum(frequencies[w] for w in tokens) / sqrt(max(len(tokens), 1))
        ranked.append((score, index, sentence))
    summary = " ".join(item[2] for item in sorted(sorted(ranked, reverse=True)[:3], key=lambda item: item[1]))

    # Heuristic named-entity candidates; these are surfaced as candidates, not verified NER.
    entities = []
    patterns = {
        "person_or_organization": r"\b(?:[A-Z][a-z]+(?:\s+(?:of|and|[A-Z][a-z]+)){1,4})\b",
        "date": r"\b(?:\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
        "money": r"(?:₹|\$|€|£|INR|USD)\s?\d[\d,.]*",
    }
    seen = set()
    for kind, pattern in patterns.items():
        for match in re.findall(pattern, text):
            normalized = match.strip()
            if normalized.lower() not in STOPWORDS and normalized not in seen:
                entities.append({"text": normalized, "type": kind, "method": "pattern"})
                seen.add(normalized)
    entities = entities[:30]

    positive = sum(frequencies[word] for word in POSITIVE)
    negative = sum(frequencies[word] for word in NEGATIVE)
    total = positive + negative
    sentiment = {
        "label": "positive" if positive > negative else "negative" if negative > positive else "neutral",
        "score": round((positive - negative) / total, 3) if total else 0.0,
        "method": "lexicon estimate",
    }
    return {
        "summary": summary or (text[:350] + ("…" if len(text) > 350 else "")),
        "topics": [word for word, _ in frequencies.most_common(8)],
        "entities": entities,
        "sentiment": sentiment,
        "analysis_note": "Summary, topics, entities, and sentiment are automated estimates; entity candidates use patterns.",
    }


@lru_cache(maxsize=1)
def _embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Semantic search requires the sentence-transformers package. Install backend requirements and restart the API.") from exc
    return SentenceTransformer("all-MiniLM-L6-v2")


def rank_semantically(rows: list[dict], query: str) -> list[dict]:
    """Rank result rows by cosine similarity of sentence-transformer embeddings."""
    documents = []
    for row in rows:
        try:
            data = __import__("json").loads(row.get("data") or "{}")
        except (TypeError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        paragraphs = data.get("paragraphs") or []
        body = " ".join(paragraph for paragraph in paragraphs if isinstance(paragraph, str)) if isinstance(paragraphs, list) else ""
        documents.append(" ".join(filter(None, [row.get("title"), row.get("description"), body]))[:5000])
    model = _embedding_model()
    vectors = [None] * len(rows)
    missing = []
    missing_keys = []
    missing_indices = []
    keys = [row.get("content_hash") or hashlib.sha256(text.encode()).hexdigest() for row, text in zip(rows, documents)]
    for index, (key, text) in enumerate(zip(keys, documents)):
        if key in _DOCUMENT_VECTORS:
            vectors[index] = _DOCUMENT_VECTORS[key]
        else:
            missing.append(text)
            missing_keys.append(key)
            missing_indices.append(index)
    if missing:
        encoded = model.encode(missing, normalize_embeddings=True, show_progress_bar=False)
        for index, key, vector in zip(missing_indices, missing_keys, encoded):
            _DOCUMENT_VECTORS[key] = vector
            vectors[index] = vector
    query_vector = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    for row, vector in zip(rows, vectors):
        row["similarity"] = round(float(vector @ query_vector), 4)
    return sorted(rows, key=lambda row: row["similarity"], reverse=True)


def evaluate_search_ranking(ranked_rows: list[dict], judgments: list[dict], k: int = 10) -> dict:
    """Compute standard ranking metrics from human relevance grades (0–3)."""
    grades = {int(item["result_id"]): int(item["relevance"]) for item in judgments}
    top = ranked_rows[:k]
    relevant_ids = {result_id for result_id, grade in grades.items() if grade >= 2}
    retrieved_relevant = [row for row in top if grades.get(int(row["id"]), 0) >= 2]
    reciprocal_rank = next((1 / rank for rank, row in enumerate(top, 1)
                            if grades.get(int(row["id"]), 0) >= 2), 0.0)

    def dcg(values):
        return sum((2 ** grade - 1) / __import__("math").log2(index + 2)
                   for index, grade in enumerate(values))

    actual = [grades.get(int(row["id"]), 0) for row in top]
    ideal = sorted(grades.values(), reverse=True)[:k]
    ideal_dcg = dcg(ideal)
    return {
        "judged_results": len(judgments),
        "relevant_judgments": len(relevant_ids),
        "k": k,
        "precision_at_k": round(len(retrieved_relevant) / k, 3),
        "recall_at_k": round(len(retrieved_relevant) / len(relevant_ids), 3) if relevant_ids else None,
        "mrr_at_k": round(reciprocal_rank, 3),
        "ndcg_at_k": round(dcg(actual) / ideal_dcg, 3) if ideal_dcg else None,
        "relevance_threshold": "Grades 2–3 count as relevant for precision, recall, and reciprocal rank.",
    }
