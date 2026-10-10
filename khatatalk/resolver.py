"""Customer name resolution using rapidfuzz and Urdu honorific stripping."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from rapidfuzz import fuzz

from khatatalk.config import FUZZY_AMBIGUITY_MARGIN, FUZZY_MATCH_THRESHOLD
from khatatalk.db import list_customers


# Common Urdu and Pakistani titles/honorifics to strip for name matching
HONORIFICS = [
    # Roman Urdu / English
    "bhaijaan", "bhaijan", "bhaiya", "bhai",
    "sahib", "sahab", "saheb", "sb",
    "baji", "bajji", "aapa", "apa",
    "uncle", "chachi", "chacha",
    "malik", "choudhary", "chaudhry", "sheikh",
    # Urdu script
    "بھائی", "صاحب", "باجی", "آپا", "چاچا", "انکل", "شیخ", "ملک", "چوہدری",
]

# Common Urdu postpositions/clitics that might stick to a name
CLITICS = ["ko", "ne", "ka", "ki", "ke", "se", "say", "کو", "نے", "کا", "کی", "کے", "سے"]


def clean_customer_name(raw_name: str) -> str:
    """Strips honorifics, titles, punctuation, and clitics from spoken customer name."""
    name = raw_name.strip()
    if not name:
        return ""

    # Remove trailing/leading punctuation
    name = re.sub(r"[^\w\s\u0600-\u06FF]", " ", name)

    tokens = [t for t in name.split() if t]
    filtered_tokens = []

    for t in tokens:
        t_lower = t.lower()
        if t_lower in HONORIFICS:
            continue
        if t_lower in CLITICS:
            continue
        filtered_tokens.append(t)

    cleaned = " ".join(filtered_tokens).strip()
    return cleaned if cleaned else name.strip()


@dataclass
class ResolutionResult:
    status: str  # "matched", "ambiguous", "new_customer"
    resolved_name: str
    customer_id: Optional[int] = None
    confidence: float = 0.0
    candidates: Optional[List[Dict[str, Any]]] = None
    clarification_question: Optional[str] = None
    message: Optional[str] = None


def resolve_customer(
    raw_name: str,
    db_path: Optional[Union[str, Path]] = None,
    threshold: float = FUZZY_MATCH_THRESHOLD,
    ambiguity_margin: float = FUZZY_AMBIGUITY_MARGIN,
) -> ResolutionResult:
    """Matches the spoken customer name against existing records in SQLite.

    Outcomes:
    - exact / high confidence match -> status: 'matched'
    - multiple close candidates -> status: 'ambiguous', asks clarification
    - no candidates found -> status: 'new_customer', proposes creation
    """
    clean_target = clean_customer_name(raw_name)
    if not clean_target:
        clean_target = raw_name.strip()

    if not clean_target:
        return ResolutionResult(
            status="new_customer",
            resolved_name="",
            message="No customer name provided.",
        )

    existing_customers = list_customers(db_path=db_path)
    if not existing_customers:
        # No customers in database yet -> new customer
        return ResolutionResult(
            status="new_customer",
            resolved_name=clean_target.title(),
            message=f"No existing customers. Propose creating '{clean_target.title()}'.",
        )

    # 1. Check exact match (case-insensitive)
    for cust in existing_customers:
        if cust["name"].strip().lower() == clean_target.lower():
            return ResolutionResult(
                status="matched",
                resolved_name=cust["name"],
                customer_id=cust["id"],
                confidence=100.0,
                message=f"Exact match found: '{cust['name']}'.",
            )

    # 2. Fuzzy match using rapidfuzz token_sort_ratio and WRatio
    scored_candidates = []
    for cust in existing_customers:
        db_name_cleaned = clean_customer_name(cust["name"])
        score1 = fuzz.token_sort_ratio(clean_target.lower(), db_name_cleaned.lower())
        score2 = fuzz.WRatio(clean_target.lower(), db_name_cleaned.lower())
        score = max(score1, score2)
        if score >= threshold:
            scored_candidates.append({
                "id": cust["id"],
                "name": cust["name"],
                "balance": cust.get("balance", 0),
                "score": score,
            })

    scored_candidates.sort(key=lambda x: x["score"], reverse=True)

    if not scored_candidates:
        # No match meeting threshold -> propose new customer
        return ResolutionResult(
            status="new_customer",
            resolved_name=clean_target.title(),
            confidence=0.0,
            message=f"Customer '{clean_target.title()}' not found. Add as new customer?",
        )

    # Check for ambiguity among top candidates
    top = scored_candidates[0]
    if len(scored_candidates) > 1:
        runner_up = scored_candidates[1]
        if (top["score"] - runner_up["score"]) <= ambiguity_margin:
            # Ambiguous!
            names = [f"'{c['name']}'" for c in scored_candidates[:3]]
            question = f"Multiple matches found ({', '.join(names)}). Which customer did you mean?"
            return ResolutionResult(
                status="ambiguous",
                resolved_name=top["name"],
                confidence=top["score"],
                candidates=scored_candidates[:3],
                clarification_question=question,
                message=question,
            )

    # Strong single match
    return ResolutionResult(
        status="matched",
        resolved_name=top["name"],
        customer_id=top["id"],
        confidence=top["score"],
        message=f"Matched '{top['name']}' (confidence: {top['score']:.1f}%).",
    )
