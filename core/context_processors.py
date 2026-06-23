from django.conf import settings


def n8n_chat(request):
    return {
        "N8N_CHAT_WEBHOOK_URL": settings.N8N_CHAT_WEBHOOK_URL,
    }
