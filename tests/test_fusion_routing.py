import unittest
from unittest.mock import patch

from decision_engine import fusion


class FusionRoutingTests(unittest.TestCase):
    def test_decisive_ml_quarantines_without_second_hard_signal(self):
        with patch.multiple(
            fusion,
            ML_HARD_LIMIT=0.995,
            ML_DECISIVE_LIMIT=0.995,
            QUARANTINE_EVIDENCE_GATED=True,
            QUARANTINE_MIN_EVIDENCE=2,
        ):
            result = fusion.fuse(5.5, 0.9985, 0.62)

        self.assertEqual(result.label, "QUARANTINE")
        self.assertEqual(result.fused_score, 1.0)

    def test_strong_but_not_decisive_ml_is_held_for_quarantine_review(self):
        with patch.multiple(
            fusion,
            ML_WEIGHT=0.60,
            SA_WEIGHT=0.25,
            ANOMALY_WEIGHT=0.15,
            THRESH_CLEAN=0.65,
            THRESH_WARN=0.85,
            ML_HARD_LIMIT=0.995,
            ML_DECISIVE_LIMIT=0.995,
            ML_REVIEW_LIMIT=0.97,
            WARN_EVIDENCE_GATED=True,
            WARN_MIN_EVIDENCE=3,
            QUARANTINE_EVIDENCE_GATED=True,
            QUARANTINE_MIN_EVIDENCE=2,
        ):
            result = fusion.fuse(5.5, 0.9830, 0.6402)

        self.assertEqual(result.label, "QUARANTINE")
        self.assertIn("routed as QUARANTINE", result.routing_reason)

    def test_low_risk_message_stays_clean(self):
        with patch.multiple(
            fusion,
            ML_WEIGHT=0.60,
            SA_WEIGHT=0.25,
            ANOMALY_WEIGHT=0.15,
            THRESH_CLEAN=0.65,
            THRESH_WARN=0.85,
            ML_REVIEW_LIMIT=0.97,
        ):
            result = fusion.fuse(1.0, 0.10, 0.20, True, True, True)

        self.assertEqual(result.label, "CLEAN")

    def test_uncertain_warning_band_is_never_released_as_clean(self):
        with patch.multiple(
            fusion,
            ML_WEIGHT=0.60,
            SA_WEIGHT=0.25,
            ANOMALY_WEIGHT=0.15,
            THRESH_CLEAN=0.65,
            THRESH_WARN=0.85,
            WARN_EVIDENCE_GATED=True,
            WARN_MIN_EVIDENCE=3,
            ML_REVIEW_LIMIT=0.97,
            WARN_ML_EVIDENCE_THRESHOLD=0.85,
            WARN_SA_EVIDENCE_THRESHOLD=10.0,
            WARN_ANOMALY_EVIDENCE_THRESHOLD=0.85,
        ):
            result = fusion.fuse(5.5, 0.8004, 0.6934)

        self.assertEqual(result.label, "WARN")
        self.assertIn("routed as WARN", result.routing_reason)


if __name__ == "__main__":
    unittest.main()
