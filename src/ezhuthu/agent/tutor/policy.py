"""Pedagogy policy: advance, repeat or hint, chosen by Strands Decider with rule guardrails."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decider import Decider, DeciderUnavailable

ACTIONS = {
    "advance": "move on to the next item",
    "repeat": "show the answer and ask the learner to try this item again later",
    "hint": "give a hint and let the learner try this item again now",
}
INSTRUCTIONS = (
    "You are the pedagogy policy of a Tamil inscription reading tutor. Given the learner state after an "
    "answer, choose the next teaching action that maximises learning without frustrating the learner."
)
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class PolicyDecision:
    """``confidence`` is None whenever the rules chose (``source == "rules"``): there is no decider number, and
    the app must show no confidence rather than 0% (issue #22)."""

    action: str
    confidence: float | None
    source: str  # decider model name, or "rules"
    overridden: bool = False
    backend: str = "rules"  # hosted | local | rules


def rules(correct: bool, attempts: int, hint_given: bool) -> str:
    if correct:
        return "advance"
    if attempts >= MAX_ATTEMPTS:
        return "advance"
    return "repeat" if hint_given else "hint"


def decide(decider: Decider, state: dict[str, Any]) -> PolicyDecision:
    correct, attempts, hint_given = state["correct"], state["attempts_on_item"], state["hint_already_given"]
    try:
        res = decider.choice(state, INSTRUCTIONS, ACTIONS, name="pedagogy")
    except DeciderUnavailable:
        return PolicyDecision(rules(correct, attempts, hint_given), None, "rules")
    if res.choice not in ACTIONS:  # unusable answer: the rules decide, so there is no decider confidence
        return PolicyDecision(rules(correct, attempts, hint_given), None, "rules")
    action = res.choice
    # Guardrails: never drill an item the learner just read correctly; never loop past MAX_ATTEMPTS.
    overridden = False
    if action != "advance" and (correct or attempts >= MAX_ATTEMPTS):
        action, overridden = "advance", True
    return PolicyDecision(action, round(res.probabilities.get(action, res.confidence), 4), res.model, overridden,
                          res.source)
