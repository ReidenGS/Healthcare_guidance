"""
redflag_rag.py  —  Red-Flag RAG Skill
======================================
Offline-first red-flag retrieval augmented generation.

Flow
----
1. At startup, load ``backend/data/redflags_offline.json`` and build an
   in-memory vector store:
   - **Primary path** (when OPENAI_API_KEY is set): embed every phrase with
     ``text-embedding-3-small`` and cache to disk so restarts are fast.
   - **Fallback path** (no API key): build a TF-IDF index using numpy only —
     zero external dependencies.

2. ``search(query)``
   - Returns matched (condition, phrase, similarity) triples where similarity
     exceeds the configured threshold.

3. ``search_with_online_fallback(query)``
   - First tries the offline vector store.
   - If no offline match is found, calls Tavily to search for red-flag context
     online (via ``web_search_skill.search_redflag_online``).
   - Always returns a structured result dict the caller can inject into prompts.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parents[3] / 'data'
_JSON_PATH = _DATA_DIR / 'redflags_offline.json'
_CACHE_PATH = _DATA_DIR / 'redflag_embeddings_cache.json'

# ---------------------------------------------------------------------------
# Similarity thresholds
# ---------------------------------------------------------------------------
OPENAI_EMBED_THRESHOLD = 0.72   # cosine similarity for dense embeddings
# TF-IDF uses a combined score: cosine * 0.6 + token_overlap * 0.4
# Both conditions must hold to avoid false positives on single shared terms.
TFIDF_COMBINED_THRESHOLD = 0.60   # combined score threshold
TFIDF_MIN_OVERLAP = 0.50          # phrase tokens that must appear in query

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return [t for t in text.split() if len(t) > 1]


_STOP_WORDS = {
    'a', 'an', 'the', 'or', 'and', 'in', 'at', 'to', 'of', 'with',
    'is', 'are', 'was', 'be', 'for', 'on', 'by', 'as', 'it', 'its',
    'this', 'that', 'from', 'not', 'but', 'have', 'has', 'had', 'no',
}


def _clean_tokens(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in _STOP_WORDS]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _json_hash(data: dict) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------------------
# TF-IDF index (numpy-free pure Python implementation)
# ---------------------------------------------------------------------------

class _TFIDFIndex:
    """Minimal TF-IDF retriever implemented in pure Python.

    Scoring: combined = cosine * 0.6 + token_overlap * 0.4
    where token_overlap = |phrase_tokens ∩ query_tokens| / |phrase_tokens|

    Using a combined score prevents false positives caused by a single
    high-IDF shared token (e.g. "chest" in both "silent chest" and
    "chest hurt" — their overlap fraction will be low for the query side).
    """

    def __init__(self, entries: list[dict[str, str]]) -> None:
        self._entries = entries
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._vecs: list[list[float]] = []
        self._doc_tokens: list[list[str]] = []
        self._build()

    def _build(self) -> None:
        docs = [_clean_tokens(_tokenize(e['phrase'])) for e in self._entries]
        self._doc_tokens = docs
        # Build vocabulary
        all_terms: set[str] = set()
        for d in docs:
            all_terms.update(d)
        self._vocab = {t: i for i, t in enumerate(sorted(all_terms))}
        V = len(self._vocab)
        N = len(docs)

        # IDF (smoothed)
        df = [0] * V
        for d in docs:
            for t in set(d):
                if t in self._vocab:
                    df[self._vocab[t]] += 1
        self._idf = [math.log((N + 1) / (df[i] + 1)) + 1.0 for i in range(V)]

        # TF-IDF vectors (L2-normalised)
        self._vecs = [self._make_vec(d) for d in docs]

    def _make_vec(self, tokens: list[str]) -> list[float]:
        V = len(self._vocab)
        vec = [0.0] * V
        if tokens:
            tf_raw: dict[str, float] = {}
            for t in tokens:
                tf_raw[t] = tf_raw.get(t, 0) + 1
            for t, cnt in tf_raw.items():
                if t in self._vocab:
                    vec[self._vocab[t]] = (cnt / len(tokens)) * self._idf[self._vocab[t]]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @staticmethod
    def _overlap(query_tokens: list[str], phrase_tokens: list[str]) -> float:
        """Fraction of *phrase* tokens present in the query."""
        if not phrase_tokens:
            return 0.0
        return len(set(query_tokens) & set(phrase_tokens)) / len(phrase_tokens)

    def search(
        self,
        query: str,
        top_k: int = 3,
        combined_threshold: float = TFIDF_COMBINED_THRESHOLD,
        min_overlap: float = TFIDF_MIN_OVERLAP,
    ) -> list[tuple[dict[str, str], float]]:
        """Return entries whose combined score ≥ combined_threshold AND
        whose phrase→query overlap ≥ min_overlap.

        Returns list of (entry, combined_score) sorted descending.
        """
        qtoks = _clean_tokens(_tokenize(query))
        qvec = self._make_vec(qtoks)

        scored: list[tuple[dict[str, str], float, float]] = []
        for entry, dvec, dtoks in zip(self._entries, self._vecs, self._doc_tokens):
            cos = _cosine(qvec, dvec)
            ov = self._overlap(qtoks, dtoks)
            combined = cos * 0.6 + ov * 0.4
            scored.append((entry, combined, ov))

        scored.sort(key=lambda x: -x[1])
        return [
            (entry, combined)
            for entry, combined, ov in scored[:top_k]
            if combined >= combined_threshold and ov >= min_overlap
        ]


# ---------------------------------------------------------------------------
# OpenAI dense-embedding index
# ---------------------------------------------------------------------------

class _OpenAIEmbedIndex:
    """Dense vector index backed by OpenAI text-embedding-3-small."""

    MODEL = 'text-embedding-3-small'

    def __init__(self, entries: list[dict[str, str]], api_key: str) -> None:
        self._entries = entries
        self._api_key = api_key
        self._vecs: list[list[float]] = []

    def _get_client(self):  # type: ignore[return]
        try:
            import openai
            return openai.OpenAI(api_key=self._api_key)
        except Exception:
            return None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        if client is None:
            return []
        try:
            resp = client.embeddings.create(model=self.MODEL, input=texts)
            return [item.embedding for item in resp.data]
        except Exception:
            return []

    def build_from_cache(self, cached_vecs: list[list[float]]) -> None:
        self._vecs = cached_vecs

    def build_fresh(self) -> bool:
        phrases = [e['phrase'] for e in self._entries]
        vecs = self._embed(phrases)
        if not vecs or len(vecs) != len(phrases):
            return False
        self._vecs = vecs
        return True

    def search(self, query: str, top_k: int = 3) -> list[tuple[dict, float]]:
        if not self._vecs:
            return []
        qvec = self._embed([query])
        if not qvec:
            return []
        q = qvec[0]
        scored = [
            (entry, _cosine(q, dvec))
            for entry, dvec in zip(self._entries, self._vecs)
        ]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Main RAG service
# ---------------------------------------------------------------------------

class RedFlagRAG:
    """
    Offline-first red-flag retrieval service.

    Priority:
    1. OpenAI dense embeddings  (if OPENAI_API_KEY configured)
    2. TF-IDF sparse index      (always available, zero extra deps)
    3. Online Tavily search      (if TAVILY_API_KEY configured, last resort)
    """

    def __init__(self) -> None:
        self._entries: list[dict[str, str]] = []
        self._tfidf: _TFIDFIndex | None = None
        self._openai: _OpenAIEmbedIndex | None = None
        self._use_dense = False
        self._ready = False
        self._load()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not _JSON_PATH.exists():
            return

        with open(_JSON_PATH, encoding='utf-8') as f:
            data: dict[str, list[str]] = json.load(f)

        # Flatten: {condition: [phrase1, phrase2, ...]} → list of dicts
        entries: list[dict[str, str]] = []
        for condition, phrases in data.items():
            for phrase in phrases:
                entries.append({'condition': condition, 'phrase': phrase})
        self._entries = entries

        # Always build TF-IDF (zero cost)
        self._tfidf = _TFIDFIndex(entries)

        # Attempt to build dense index
        from app.core.config import get_settings
        settings = get_settings()
        api_key = settings.openai_api_key
        if api_key:
            self._openai = _OpenAIEmbedIndex(entries, api_key)
            self._use_dense = self._try_load_or_build_dense(data, api_key)

        self._ready = True

    def _try_load_or_build_dense(self, raw_data: dict, api_key: str) -> bool:
        """Load cached embeddings from disk, or (re-)build and save them."""
        assert self._openai is not None
        current_hash = _json_hash(raw_data)

        # Try cache
        if _CACHE_PATH.exists():
            try:
                with open(_CACHE_PATH, encoding='utf-8') as f:
                    cache = json.load(f)
                if cache.get('hash') == current_hash and cache.get('embeddings'):
                    self._openai.build_from_cache(cache['embeddings'])
                    return True
            except Exception:
                pass

        # Build fresh (calls OpenAI API)
        ok = self._openai.build_fresh()
        if ok:
            try:
                _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(_CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(
                        {'hash': current_hash, 'embeddings': self._openai._vecs,
                         'built_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
                        f,
                    )
            except Exception:
                pass
        return ok

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 3,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search offline vector store.

        Returns a list of match dicts:
        ``{condition, phrase, similarity, source}``
        where ``source`` is ``'dense'`` or ``'tfidf'``.

        Dense index uses cosine similarity ≥ OPENAI_EMBED_THRESHOLD.
        TF-IDF uses combined score (cos*0.6 + overlap*0.4) ≥ TFIDF_COMBINED_THRESHOLD
        AND phrase→query overlap ≥ TFIDF_MIN_OVERLAP to suppress false positives.
        """
        if not self._ready or not query.strip():
            return []

        results: list[dict[str, Any]] = []

        # Primary: dense OpenAI embeddings
        if self._use_dense and self._openai:
            th = threshold if threshold is not None else OPENAI_EMBED_THRESHOLD
            hits = self._openai.search(query, top_k=top_k)
            for entry, sim in hits:
                if sim >= th:
                    results.append({**entry, 'similarity': round(sim, 4), 'source': 'dense'})

        # Fallback: TF-IDF with combined scoring + min-overlap guard
        if not results and self._tfidf:
            hits = self._tfidf.search(
                query,
                top_k=top_k,
                combined_threshold=TFIDF_COMBINED_THRESHOLD,
                min_overlap=TFIDF_MIN_OVERLAP,
            )
            for entry, sim in hits:
                results.append({**entry, 'similarity': round(sim, 4), 'source': 'tfidf'})

        return results

    # ------------------------------------------------------------------
    # RAG with online fallback
    # ------------------------------------------------------------------

    def search_with_online_fallback(
        self, query: str
    ) -> dict[str, Any]:
        """
        Full RAG pipeline:
        1. Offline vector search
        2. Online Tavily red-flag search (if offline found nothing)

        Returns:
        {
            "matched_offline": [list of offline hits],
            "online_context": str | None,   # Tavily snippets if used
            "is_redflag": bool,             # True if either path found evidence
            "conditions": [str],            # matched condition names
            "summary": str,                 # human-readable summary for prompt injection
        }
        """
        offline_hits = self.search(query)

        if offline_hits:
            conditions = list({h['condition'] for h in offline_hits})
            top_phrases = [h['phrase'] for h in offline_hits[:3]]
            summary = (
                f'RED FLAG MATCH (offline vector store): '
                f'Patient description matches known red-flag patterns for '
                f'{", ".join(conditions)}. '
                f'Matched phrases: {"; ".join(top_phrases)}.'
            )
            return {
                'matched_offline': offline_hits,
                'online_context': None,
                'is_redflag': True,
                'conditions': conditions,
                'summary': summary,
            }

        # No offline match — try online
        online_ctx = _search_redflag_online(query)
        if online_ctx:
            summary = f'RED FLAG CONTEXT (online search): {online_ctx[:400]}'
            return {
                'matched_offline': [],
                'online_context': online_ctx,
                'is_redflag': False,   # online context is advisory, not confirmed
                'conditions': [],
                'summary': summary,
            }

        return {
            'matched_offline': [],
            'online_context': None,
            'is_redflag': False,
            'conditions': [],
            'summary': '',
        }


# ---------------------------------------------------------------------------
# Online red-flag Tavily search (separate from department routing search)
# ---------------------------------------------------------------------------

def _search_redflag_online(symptoms: str) -> str:
    """
    Query Tavily specifically for red-flag / emergency context.

    Separate from the department-routing search in ``web_search_skill.py``;
    this one focuses on: "are these symptoms dangerous / red flags?"
    """
    try:
        from app.core.config import get_settings
        import requests as _req

        settings = get_settings()
        if not settings.tavily_api_key:
            return ''

        query = (
            f'{symptoms} red flag symptoms emergency warning signs '
            'when to go to emergency room immediately'
        )
        resp = _req.post(
            'https://api.tavily.com/search',
            json={
                'api_key': settings.tavily_api_key,
                'query': query,
                'search_depth': 'basic',
                'max_results': 3,
                'include_answer': False,
            },
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
        snippets = [
            item.get('content', '').replace('\n', ' ').strip()
            for item in data.get('results', [])[:3]
            if item.get('content', '').strip()
        ]
        return ' | '.join(snippets)
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# Module-level singleton (initialised once at import time)
# ---------------------------------------------------------------------------
redflag_rag = RedFlagRAG()
