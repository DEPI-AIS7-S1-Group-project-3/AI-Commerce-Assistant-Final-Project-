"""Section-level search over the current policies (retrieval for the Support Agent).

The four policies are small (about 30 numbered sections in total), so the search is a simple,
explainable keyword match, not embeddings:

- both the question and the sections go through ``normalize_ar``;
- a question word matches a section word when they are equal, when they have the same
  consonants (``ارجع`` / ``ارجاع``), when one is a prefix of the other, or when they share most
  of their letter triples;
- rarer words count more (a word found in every section says little);
- a hit in a section title or in the policy title counts extra.

``rank_sections`` is a pure function (easy to test). ``search_policies`` loads the current
policies and returns the best sections, each with ``slug``, ``version`` and section number so
the agent can cite where an answer came from.
"""

import math
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_commerce_marketplace.database.models.policy import Policy
from ai_commerce_marketplace.nlp.arabic import normalize_ar
from ai_commerce_marketplace.services.policies import split_sections

MIN_SCORE = 0.8  # below this the best section is not a real match
TITLE_BONUS = 0.5

# Question words that carry no topic (already normalized: no hamza, no taa marbuta).
_STOPWORDS = frozenset(
    """
    في من علي الي عن مع هل ما ماذا ايه ازاي كيف لو او ان انا انت هو هي ده دي دا كام
    اقدر ممكن عايز عاوز عايزه اريد يعني طيب لازم هيا هما كل اي بس لما ليه لماذا عند
    the a an is are of to for and or what how can i my
    """.split()
)

_WORD = re.compile(r"\w+")
_NO_VOWELS = str.maketrans("", "", "اوي")
_VERB_PREFIXES = frozenset("بتهنسم")
MATCH = 0.7  # a word counts as present when its similarity is at least this


@dataclass(frozen=True)
class SectionDoc:
    slug: str
    policy_title: str
    version: str
    no: int
    title: str
    body: str


@dataclass(frozen=True)
class PolicyHit:
    doc: SectionDoc
    score: float


def _strip_article(word: str) -> str:
    """Drop the Arabic definite article so ``الشحن`` and ``شحن`` match."""
    for prefix in ("وال", "بال", "لل", "ال"):
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            return word[len(prefix) :]
    return word


def tokens(text: str) -> list[str]:
    words = _WORD.findall(normalize_ar(text))
    return [_strip_article(w) for w in words if w not in _STOPWORDS and len(w) > 1]


def _roots(word: str) -> set[str]:
    """Consonant skeletons of a word, also without verb prefixes (colloquial ``بترجع``).

    ``ارجع``, ``ارجاع`` and ``بترجع`` all contain the skeleton ``رجع``.
    """
    skeleton = word.translate(_NO_VOWELS)
    roots = {skeleton}
    while len(skeleton) > 3 and skeleton[0] in _VERB_PREFIXES:
        skeleton = skeleton[1:]
        roots.add(skeleton)
    return roots


def _trigrams(word: str) -> set[str]:
    padded = f"  {word} "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def word_similarity(a: str, b: str) -> float:
    """0..1. 1 = same word; same consonants or a prefix scores high; otherwise letter triples."""
    if a == b:
        return 1.0
    if any(len(r) >= 3 for r in _roots(a) & _roots(b)):
        return 0.9
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 3 and long_.startswith(short):
        return 0.8
    ta, tb = _trigrams(a), _trigrams(b)
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard if jaccard >= 0.5 else 0.0


def _best(word: str, candidates: set[str]) -> float:
    return max((word_similarity(word, c) for c in candidates), default=0.0)


def rank_sections(query: str, docs: list[SectionDoc]) -> list[PolicyHit]:
    """Sections that match the question, best first. Empty list when nothing matches."""
    q_words = list(dict.fromkeys(tokens(query)))
    if not q_words or not docs:
        return []

    body_words = [set(tokens(f"{d.title} {d.body}")) for d in docs]
    head_words = [set(tokens(f"{d.policy_title} {d.title}")) for d in docs]

    # Rarer words weigh more: idf over the sections.
    idf = {}
    for w in q_words:
        df = sum(1 for words in body_words if _best(w, words) >= MATCH)
        idf[w] = math.log(1 + len(docs) / (1 + df)) + 0.5

    hits = []
    for doc, words, head in zip(docs, body_words, head_words, strict=True):
        score = 0.0
        for w in q_words:
            s = _best(w, words)
            if s >= MATCH:
                score += s * idf[w]
                if _best(w, head) >= MATCH:
                    score += TITLE_BONUS
        hits.append(PolicyHit(doc, round(score, 3)))

    hits = [h for h in hits if h.score >= MIN_SCORE]
    return sorted(hits, key=lambda h: (-h.score, h.doc.slug, h.doc.no))


def load_section_docs(session: Session) -> list[SectionDoc]:
    """Every numbered section of every current policy."""
    docs = []
    for p in session.scalars(select(Policy).where(Policy.is_current.is_(True))):
        for s in split_sections(p.body_md):
            docs.append(SectionDoc(p.slug, p.title_ar, p.version, s.no, s.title, s.body))
    return docs


def search_policies(session: Session, query: str, limit: int = 3) -> list[PolicyHit]:
    return rank_sections(query, load_section_docs(session))[:limit]
