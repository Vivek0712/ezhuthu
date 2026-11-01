"""Strands tools over the restoration engine, and the agentic Restorer agent.

The API uses ``Restorer.restore`` (a fixed pipeline). ``build_restorer_agent`` gives the same steps to a
Strands ``Agent`` as tools, for conversational use ("why did you choose this fill?") and for the tutor.
"""

from __future__ import annotations

from typing import Any

from strands import Agent, tool

from .prompts import RESTORER_SYSTEM
from .restorer import Candidate, Restorer


def make_tools(restorer: Restorer) -> list[Any]:
    @tool
    def retrieve_parallels(left: str, right: str, gap_chars: int = 0, k: int = 5) -> list[dict[str, Any]]:
        """Find parallel passages in other inscriptions for a gap (BM25 + fuzzy match over the train corpus).

        Args:
            left: ISO-15919 text immediately before the gap.
            right: ISO-15919 text immediately after the gap.
            gap_chars: approximate gap length in characters (0 if unknown).
            k: number of parallels to return.
        """
        ps = restorer.retrieve_parallels(left, right, gap_chars or None, k=k)
        return [{**p.to_api(), "aligned_fill": p.fill, "score": p.score} for p in ps]

    @tool
    def propose_fills(left: str, right: str, gap_chars: int = 0, k: int = 5, escalate: bool = False) -> list[dict]:
        """Ask the restoration LLM (Sonnet 4.6, or Opus 4.6 when escalate=true) for top-k candidate fills.

        Args:
            left: ISO-15919 text before the gap.
            right: ISO-15919 text after the gap.
            gap_chars: approximate gap length (0 if unknown).
            k: number of candidates.
            escalate: use the escalation model from config/models.yaml.
        """
        pars = restorer.retrieve_parallels(left, right, gap_chars or None, k=5)
        hints = restorer.ontology.hints_for_gap(left, right)
        props = restorer.propose_fills("escalate" if escalate else "default", left, right, gap_chars or None,
                                       pars, hints, k)
        return [{"text": t, "confidence": c} for t, c in props]

    @tool
    def check_constraints(candidates: list[str], gap_chars: int, dynasty: str = "") -> list[dict[str, Any]]:
        """Check candidate fills against the gap length and era-valid letters.

        Args:
            candidates: candidate fills (ISO-15919).
            gap_chars: expected gap length in characters.
            dynasty: dynasty/era of the inscription, if known.
        """
        cs = [Candidate(c) for c in candidates]
        kept = {c.text for c in restorer.check_constraints(cs, gap_chars, explicit_length=True,
                                                           dynasty=dynasty or None)}
        return [{"text": c.text, "length_ok": c.length_ok, "letters_ok": c.letters_ok, "kept": c.text in kept}
                for c in cs]

    @tool
    def rank_and_decide(left: str, right: str, gap_chars: int = 0, max_candidates: int = 5) -> dict[str, Any]:
        """Run the full pipeline for one gap: parallels, fills, constraints, then Strands Decider ranking with
        abstention. Returns the decision (fill or abstain), ranked candidates and confidence source.

        Args:
            left: ISO-15919 text before the gap.
            right: ISO-15919 text after the gap.
            gap_chars: approximate gap length (0 if unknown).
            max_candidates: how many ranked candidates to return.
        """
        return restorer.restore_gap(left, right, gap_chars or None, max_candidates=max_candidates).to_api()

    @tool
    def ontology_hints(text: str) -> list[dict[str, str]]:
        """Look up rulers, titles, places, grants and formulae mentioned in ISO-15919 text.

        Args:
            text: ISO-15919 text.
        """
        return [h.to_api() for h in restorer.ontology.find_entities(text)]

    return [retrieve_parallels, propose_fills, check_constraints, rank_and_decide, ontology_hints]


def build_restorer_agent(restorer: Restorer, model: Any) -> Agent:
    """A Strands Agent that restores gaps by calling the tools above. ``model`` is a Strands model."""
    return Agent(
        name="restorer", model=model, tools=make_tools(restorer), callback_handler=None,
        system_prompt=RESTORER_SYSTEM.replace("Answer with JSON only.", "")
        + " Use the tools: find parallels, propose fills, check constraints, then rank_and_decide. "
        "Report abstentions as 'experts are unsure'.",
    )
