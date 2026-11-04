"""Language-aware text utilities used by the RNU validators."""
from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any, Iterable

CITATION_RE = re.compile(r"\[@([^\]]+)\]")
CITATION_KEY_RE = re.compile(r"@?([\w][\w:\-\.]*)")

_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "et al", "fig", "figs", "no", "nr", "vs", "cf", "approx", "dr", "prof",
    "mr", "mrs", "ms", "jr", "sr", "st", "vol", "pp", "p", "ed", "eds", "inc", "ltd", "co",
    "u.s", "u.k", "eu", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec", "т.е", "т.д", "т.п", "др", "рис", "см", "г", "гг", "стр", "проф",
    "piem", "u.c", "t.sk", "sk", "lpp", "att", "masalan", "va h.k", "z.b", "bzw", "usw", "ca",
}

_SENT_END = re.compile(r"([.!?…]+)(['\"”»)\]]*)(\s+)")


def strip_citations(text: str) -> str:
    return CITATION_RE.sub("", text or "")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences; robust to abbreviations, decimals, initials
    and citation markers. Works for Latin and Cyrillic scripts."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    sentences: list[str] = []
    start = 0
    for m in _SENT_END.finditer(text):
        end = m.end(2)
        before = text[start:m.start(1)]
        nxt = text[m.end():m.end() + 1]
        last_word = re.split(r"[\s(]", before)[-1].lower() if before else ""
        last_word = last_word.strip("'\"«“(")
        if m.group(1) == "." and (
            last_word in _ABBREVIATIONS
            or (len(last_word) == 1 and last_word.isalpha())      # initials "J. Smith"
        ):
            continue
        if nxt and not (nxt.isupper() or nxt.isdigit() or nxt in "\"'«“([" or not nxt.isalpha()):
            # next token starts lowercase -> not a sentence boundary
            continue
        sentence = text[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def count_sentences(text: str) -> int:
    return len(split_sentences(text))


WORD_RE = re.compile(r"[^\W\d_][\w'’\-]*", re.UNICODE)


def words(text: str) -> list[str]:
    return WORD_RE.findall(strip_citations(text or ""))


def word_count(text: str) -> int:
    return len(words(text))


NUMBER_RE = re.compile(r"(?<![\w.])[-−]?\d+(?:[.,]\d+)?(?:\s?%|\s?(?:percent|процент|procent|foiz))?", re.IGNORECASE)


def numbers_in(text: str) -> list[str]:
    return [m.group(0) for m in NUMBER_RE.finditer(strip_citations(text or ""))]


def has_statistic(text: str) -> bool:
    """True if text contains a quantitative fact: a percentage, a number with
    two or more digits, or a decimal (a single small digit alone does not count)."""
    for n in numbers_in(text):
        digits = re.sub(r"\D", "", n)
        if "%" in n or "per" in n.lower() or len(digits) >= 2 or re.search(r"[.,]\d", n):
            return True
    return False


def citation_keys(text: str) -> list[str]:
    keys: list[str] = []
    for m in CITATION_RE.finditer(text or ""):
        for part in re.split(r"[;,]", m.group(1)):
            km = CITATION_KEY_RE.search(part.strip())
            if km:
                keys.append(km.group(1))
    return keys


# ── key-term extraction (for the "terms must not change" rule) ────────────
STOPWORDS = set("""
a an the and or of to in on for with by from at as is are was were be been being has have had this that these those it its
which who whom whose into via using use used based new own their our we they such than then also more most can may will
offered modified suggested offer modify suggest system systems approach method methods model models
и в во на с со по для из от до о об что это как также который которая которые при или а но не
предложен модифицирован рекомендован система метод
un ir ar par no uz kas ka arī vai bet tas tā šis šī tiek tika piedāvāts modificēts ieteikts
va bilan uchun bu shu ham yoki lekin qilingan etilgan taklif modifikatsiya tavsiya tizim usul asosida orqali
""".split())


def stem(word: str, n: int = 6) -> str:
    return word.lower()[:n]


def key_terms(text: str, limit: int = 6, skip: Iterable[str] = ()) -> list[str]:
    skip_set = {s.lower() for s in skip}
    terms: "OrderedDict[str, None]" = OrderedDict()
    for w in words(text):
        lw = w.lower().strip("-'’")
        if len(lw) < 5 or lw in STOPWORDS or lw in skip_set:
            continue
        terms.setdefault(lw, None)
        if len(terms) >= limit:
            break
    return list(terms)


def term_overlap(terms: list[str], text: str) -> tuple[float, list[str]]:
    """Share of ``terms`` whose 6-char stem occurs in ``text``; returns
    (ratio, missing terms)."""
    if not terms:
        return 1.0, []
    stems_in_text = {stem(w) for w in words(text)}
    missing = [t for t in terms if stem(t) not in stems_in_text]
    return (len(terms) - len(missing)) / len(terms), missing


def flatten_text(value: Any) -> str:
    """Concatenate every string inside a nested structure."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(flatten_text(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(flatten_text(v) for v in value)
    return ""
