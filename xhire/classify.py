"""Score a post on how likely it is a brand hiring a UGC creator.

The hard problem in this niche is direction, not topic. "UGC creator" appears
just as often in a creator's self-promo ("UGC creator, DM for rates") as in a
brand's open call ("looking for a UGC creator"). Both mention the same nouns, so
keyword matching alone returns a feed that is mostly other freelancers competing
with you. The scorer therefore weights *who is offering what*: first person
availability language is penalised hard, second person solicitation is rewarded.
"""

from __future__ import annotations

import re

# A brand asking for creators. These are the signal.
DEMAND_PATTERNS = [
    (r"\blooking for (?:a |an |some )?(?:ugc |content )?creators?\b", 4),
    (r"\b(?:we(?:'re| are)|i(?:'m| am)) (?:hiring|looking to hire)\b", 4),
    (r"\bneeds? (?:a |an |some )?(?:ugc |content )?creators?\b", 4),
    (r"\b(?:ugc )?creators? wanted\b", 4),
    (r"\bnow hiring\b", 3),
    (r"\bopen call\b", 3),
    (r"\baccepting applications\b", 3),
    (r"\bwant to work with\b", 3),
    (r"\blooking to work with\b", 3),
    (r"\bapply (?:here|below|now|via)\b", 2),
    (r"\b(?:send|drop) (?:me )?your portfolio\b", 2),
    (r"\bdm me if you(?:'re| are) (?:a|interested)\b", 2),
    (r"\bwe(?:'re| are) looking for\b", 2),
]

# A creator advertising themselves. These are the noise, and there is far more
# of it than signal, so the penalties outweigh any single demand match.
SUPPLY_PATTERNS = [
    (r"\bi(?:'m| am) a (?:ugc|content) creator\b", -6),
    (r"\b(?:my|dm for) rates\b", -5),
    (r"\b(?:available|open) for (?:work|hire|collabs?|brand deals?)\b", -5),
    (r"\bopen to work\b", -5),
    (r"\bhire me\b", -5),
    (r"\bmy portfolio\b", -4),
    (r"\blooking for (?:brands|clients|work|a job|opportunities)\b", -5),
    (r"\bi (?:do|make|create) ugc\b", -4),
    (r"\bwould love to work with\b", -3),
    (r"\blet(?:'s| us) collab\b", -2),
]

# Confirms the post is about UGC work at all, rather than the acronym in some
# unrelated sense. No topic term, no score.
TOPIC_PATTERNS = [
    r"\bugc\b",
    r"\buser[- ]generated content\b",
    r"\bcontent creators?\b",
    r"\bshort[- ]form (?:video|content)\b",
]

# Concrete signs of a real, funded brief.
QUALITY_PATTERNS = [
    (r"\bpaid\b", 2),
    (r"\b(?:budget|rate|compensation|per video|per deliverable)\b", 2),
    (r"\$\s?\d[\d,]*", 2),
    (r"\b(?:brand|company|agency|startup)\b", 1),
    (r"\b(?:tiktok|instagram|reels|shorts)\b", 1),
]

MIN_SCORE_LIKELY = 5
MIN_SCORE_MAYBE = 2


def _apply(patterns, text: str, reasons: list[str]) -> int:
    total = 0
    for pattern, weight in patterns:
        if re.search(pattern, text):
            total += weight
            match = re.search(pattern, text).group(0)
            reasons.append(f"{match!r} {weight:+d}")
    return total


def classify(text: str) -> tuple[int, str, str]:
    """Return (score, verdict, human-readable reasons) for a post's text."""
    lowered = text.lower()
    reasons: list[str] = []

    if not any(re.search(p, lowered) for p in TOPIC_PATTERNS):
        return 0, "off_topic", "no UGC/creator topic term"

    score = _apply(DEMAND_PATTERNS, lowered, reasons)
    supply = _apply(SUPPLY_PATTERNS, lowered, reasons)
    score += supply

    # Quality signals only sweeten a post that already reads as demand. Without
    # that gate, "paid" and a dollar figure would lift a creator's rate card.
    if score > 0:
        score += _apply(QUALITY_PATTERNS, lowered, reasons)

    score = max(score, 0)

    if score >= MIN_SCORE_LIKELY:
        verdict = "likely_hiring"
    elif score >= MIN_SCORE_MAYBE:
        verdict = "maybe_hiring"
    elif supply < 0:
        verdict = "creator_selling"
    else:
        verdict = "unclear"

    return score, verdict, "; ".join(reasons) or "no matches"
