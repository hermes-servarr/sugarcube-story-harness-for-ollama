from pathlib import Path

import pytest

from model_benchmark.capability_card import issue_mechanical_card
from model_benchmark.narrative_review import NarrativeReviewError


ROOT = Path(__file__).resolve().parents[2]


def test_issuer_refuses_to_relabel_v1_evidence_after_compiler_changed():
    with pytest.raises(NarrativeReviewError, match="source changed after evidence run started"):
        issue_mechanical_card(
            ROOT,
            ROOT / "benchmark_outputs" / "promotion_confirmation_ten_seed_v1.json",
            card_id="must_not_launder_v1",
        )
