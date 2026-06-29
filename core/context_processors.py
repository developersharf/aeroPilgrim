from django.conf import settings

from .services.search_orchestrator import (
    get_or_create_subscription,
    remaining_quota,
)


def n8n_chat(request):
    return {
        "N8N_CHAT_WEBHOOK_URL": settings.N8N_CHAT_WEBHOOK_URL,
    }


def subscription(request):
    """Expose subscription + quota info to every template.

    Used by base.html nav badge and any page that wants to know
    whether the current user is on the premium plan.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    sub, used, remaining = remaining_quota(request.user)
    return {
        "subscription": sub,
        "is_premium_user": sub.is_premium,
        "quota_used": used,
        "quota_total": sub.daily_quota,
        "plan_label": sub.plan_label(),
    }
