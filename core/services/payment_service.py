"""
PHASE 3 — Demo SSLCommerz payment service.

This service emulates the SSLCommerz payment-gateway flow:

  1. Frontend calls ``init_payment(user)`` — we create a PaymentTransaction,
     return a URL the user should be redirected to (our own demo page).
  2. The demo gateway page shows a "Pay" / "Cancel" UI (no real card form
     required). On click it POSTs to our server.
  3. Server validates ``tran_id`` + ``status`` and either marks the
     transaction successful or cancelled. On success the user's
     UserSubscription is upgraded *immediately* (no expiry for demo
     purposes — Premium stays active).

We deliberately keep this module agnostic to the gateway: swapping
``init_payment`` for a real SSLCommerz POST only means changing the URL
builder. The internal state machine is what production code needs.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from core.models import PaymentTransaction, UserSubscription

logger = logging.getLogger(__name__)

PREMIUM_PRICE_USD = 5.00
PREMIUM_DURATION_DAYS = 30


def _new_tran_id():
    return f"UF-{secrets.token_hex(6).upper()}"


def init_payment(user: User, request=None) -> PaymentTransaction:
    """Create a PaymentTransaction for the user and return it.

    The caller is expected to redirect to ``reverse('payment_demo',
        args=[transaction.tran_id])`` which renders our fake gateway page.
    """
    tran_id = _new_tran_id()
    return PaymentTransaction.objects.create(
        user=user,
        tran_id=tran_id,
        amount_usd=PREMIUM_PRICE_USD,
        status=PaymentTransaction.STATUS_PENDING,
    )


def demo_gateway_url(tran_id, request=None):
    """Return the URL for the user to 'enter the gateway'."""
    return reverse("payment_demo", args=[tran_id])


def confirm_payment(tran_id, gateway_payload=None) -> PaymentTransaction:
    """Mark the transaction as SUCCESS and upgrade the user to Premium."""
    return _finalise(tran_id, PaymentTransaction.STATUS_SUCCESS, gateway_payload or {})


def cancel_payment(tran_id, gateway_payload=None) -> PaymentTransaction:
    return _finalise(tran_id, PaymentTransaction.STATUS_CANCELLED, gateway_payload or {})


def fail_payment(tran_id, gateway_payload=None) -> PaymentTransaction:
    return _finalise(tran_id, PaymentTransaction.STATUS_FAILED, gateway_payload or {})


def _finalise(tran_id, status, gateway_payload):
    from django.db import transaction as db_tx

    with db_tx.atomic():
        try:
            pt = PaymentTransaction.objects.select_for_update().get(tran_id=tran_id)
        except PaymentTransaction.DoesNotExist as exc:
            raise ValueError(f"Unknown transaction {tran_id}") from exc

        if pt.status == PaymentTransaction.STATUS_SUCCESS:
            return pt

        pt.status = status
        pt.gateway_payload = gateway_payload
        pt.completed_at = timezone.now()
        pt.save(update_fields=["status", "gateway_payload", "completed_at"])

        if status == PaymentTransaction.STATUS_SUCCESS:
            sub, _ = UserSubscription.objects.get_or_create(user=pt.user)
            sub.is_premium = True
            sub.plan = UserSubscription.PLAN_PREMIUM
            sub.upgraded_at = timezone.now()
            sub.expires_at = timezone.now() + timedelta(days=PREMIUM_DURATION_DAYS)
            sub.last_payment_id = pt.tran_id
            sub.save()
            logger.info("User %s upgraded to premium via %s", pt.user.username, tran_id)

        return pt


def is_premium(user):
    if not user or not user.is_authenticated:
        return False
    try:
        sub = user.subscription
    except UserSubscription.DoesNotExist:
        return False
    if not sub.is_premium:
        return False
    if sub.expires_at and sub.expires_at < timezone.now():
        sub.is_premium = False
        sub.plan = UserSubscription.PLAN_FREE
        sub.save(update_fields=["is_premium", "plan"])
        return False
    return True
