"""Live Bedrock wiring (``pytest -m live`` with EZHUTHU_LIVE=1). Excluded from ``make check``.

Uses the same prompt as ``python -m ezhuthu.eval.smoke`` so a warm ``.cache/llm`` replays it at no cost.
"""

import os

import pytest

from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.decider import NoDecider
from ezhuthu.agent.llm import BedrockLLM
from ezhuthu.agent.restorer import Restorer

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("EZHUTHU_LIVE") != "1", reason="needs EZHUTHU_LIVE=1")]


def test_sonnet_proposes_fills_via_strands():
    llm = BedrockLLM()
    g = Restorer(llm=llm, decider=NoDecider()).restore_gap(
        "mahādēvarkku nantā viḷakku ", " vaitta āṭu toṇṇūṟu", 7, router="sonnet")
    assert load_models_config().model_id("default") in g.models_used
    assert any("sonnet" in c.sources for c in g.candidates)
