"""
Research Signals

Purpose
-------
Central place for research-oriented vocabulary used by Nexus OS.

Why This Exists
---------------
Academic research evolves.

Keeping research vocabulary in one location makes Nexus OS easier to:

- Maintain
- Audit
- Extend

without modifying scoring logic.
"""


# Strong research indicators

RESEARCH_TERMS = {

    # Core research language

    "study": 3,

    "evaluation": 3,

    "review": 3,

    "analysis": 2,

    "evidence": 3,

    "investigation": 3,

    "experiment": 3,

    "randomized": 4,

    "systematic": 4,

    # Financial services domain

    "financial inclusion": 3,

    "mobile money": 3,

    "loan": 2,

    "repayment": 2,

    "credit": 2,

    # Development economics

    "risk sharing": 2,

    "transaction costs": 2,

    "microlenders": 2,

    "consumption": 1
}


# Signals that usually indicate weak evidence quality.

LOW_AUTHORITY_TERMS = {

    "blog": -5,

    "brochure": -5,

    "marketing": -5,

    "top 10": -5,

    "my thoughts": -5,

    "why i love": -5
}