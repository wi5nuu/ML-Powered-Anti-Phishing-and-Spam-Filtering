"""Outbound mail delivery helpers for CogniMail."""

from .direct_mx import DirectDeliveryError, deliver_direct_mx

__all__ = ["DirectDeliveryError", "deliver_direct_mx"]
