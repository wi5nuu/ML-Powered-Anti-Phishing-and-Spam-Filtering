"""
Router — menentukan ke mana email dikirim berdasarkan label dari decision engine.

Tindakan:
  - CLEAN: pass ke mailbox normal (tidak ada tindakan)
  - WARN: inject X-Spam-Reason header, pass ke mailbox
  - QUARANTINE: simpan ke database karantina + notifikasi
"""

import logging
from dataclasses import dataclass

from decision_engine.fusion import FusionResult
from classifier.features import EmailFeatures

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    action: str
    message: str


def route(fusion: FusionResult, features: EmailFeatures) -> RoutingDecision:
    if fusion.label == "CLEAN":
        return RoutingDecision(
            action="DELIVER",
            message="Email bersih, dikirim ke inbox tanpa modifikasi."
        )
    elif fusion.label == "WARN":
        return RoutingDecision(
            action="DELIVER_WITH_HEADER",
            message=(
                f"Email mencurigakan (skor {fusion.fused_score:.2f}). "
                "X-Spam-Reason header ditambahkan. Dikirim ke inbox."
            )
        )
    else:
        return RoutingDecision(
            action="QUARANTINE",
            message=(
                f"Email dikarantina (skor {fusion.fused_score:.2f}). "
                "Tinjau di dashboard admin."
            )
        )
