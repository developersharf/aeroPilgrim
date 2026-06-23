import json
from datetime import datetime, timedelta

import requests
from django.conf import settings

from core.services.flight_api import extract_flight_days
from core.models import Search


def _city_label(code):
    return dict(Search.CITY_CHOICES).get(code, code)


def build_trip_chat_context(search, flight):
    days = extract_flight_days(search.api_response or {})
    priced = [d for d in days if d.get("price") is not None]
    alternatives = sorted(priced, key=lambda x: x["price"])[:8]

    return_date = None
    if flight.get("flight_date"):
        depart = datetime.strptime(flight["flight_date"], "%Y-%m-%d").date()
        return_date = str(depart + timedelta(days=search.stay_days))

    return {
        "search_id": search.id,
        "route": f"{search.city_departure} → {search.city_arrival}",
        "city_departure": _city_label(search.city_departure),
        "city_arrival": _city_label(search.city_arrival),
        "city_departure_code": search.city_departure,
        "city_arrival_code": search.city_arrival,
        "selected_departure_date": flight["flight_date"],
        "selected_price_usd": flight["price"],
        "price_category": flight.get("price_group", "Standard"),
        "stay_days": search.stay_days,
        "search_window_days": search.timespan_to_search,
        "return_date": return_date,
        "calendar_dates_available": len(priced),
        "cheaper_alternative_dates": [
            {
                "date": d.get("day"),
                "price_usd": d.get("price"),
                "category": d.get("group", "Standard"),
            }
            for d in alternatives
            if d.get("day") != flight["flight_date"]
        ],
        "search_saved_at": search.created_at.isoformat() if search.created_at else None,
    }


def _mock_chat_response(message, context):
    lower = message.lower()
    route = context["route"]
    date = context["selected_departure_date"]
    price = context["selected_price_usd"]
    stay = context["stay_days"]
    arrival = context["city_arrival"]

    if any(w in lower for w in ("price", "cost", "cheap", "fare")):
        alts = context["cheaper_alternative_dates"][:3]
        alt_lines = "\n".join(
            f"- **{a['date']}** — ${a['price_usd']} ({a['category']})"
            for a in alts
        ) or "_No cheaper dates found in this saved search._"
        return (
            f"Your selected departure on **{date}** is **${price}** ({context['price_category']} fare) "
            f"for {route} with a **{stay}-day** stay.\n\n"
            f"Other dates in our database for this search:\n{alt_lines}\n\n"
            f"We have **{context['calendar_dates_available']}** priced dates saved for this route."
        )

    if any(w in lower for w in ("hotel", "stay", "accommodation")):
        return (
            f"For your **{stay}-day** trip to **{arrival}** arriving **{date}**, "
            f"look for hotels within 10 minutes of the Haram. Budget options often run "
            f"**$40–70/night**; mid-range **$70–120/night**. Book early and check shuttle service to the mosque."
        )

    if any(w in lower for w in ("visa", "passport", "document")):
        return (
            "Bangladeshi pilgrims typically need an Umrah visa through an approved Saudi agent, "
            "a passport valid 6+ months, photos, vaccination proof, and confirmed return tickets. "
            "Processing usually takes **3–7 business days**."
        )

    if any(w in lower for w in ("itinerary", "plan", "schedule", "day")):
        return (
            f"**{stay}-day outline** for {route}, departing **{date}**:\n\n"
            f"1. **Day 1** — Arrive, hotel check-in, perform Umrah if ready\n"
            f"2. **Days 2–{max(stay - 2, 2)}** — Prayers at the Haram, rest, ziyarat, optional Madinah visit\n"
            f"3. **Day {stay - 1}** — Farewell Tawaf and packing\n"
            f"4. **Day {stay}** — Return flight (~{context.get('return_date', 'TBD')})"
        )

    return (
        f"I'm your UmrahFly assistant for this saved trip: **{route}**, departing **{date}** "
        f"at **${price}** for a **{stay}-day** stay.\n\n"
        f"Ask me about **prices**, **cheaper dates**, **hotels**, **visa**, **itinerary**, or **budget** — "
        f"I can use the flight data stored for this search (ID {context['search_id']})."
    )


def _call_openai_chat(message, context, history):
    system_prompt = (
        "You are UmrahFly's AI travel assistant on a trip details page for Bangladeshi Umrah pilgrims. "
        "You have read-only access to this saved search from the application database. "
        "Use ONLY the trip data below when answering. Be practical, warm, and concise. "
        "Use markdown for lists and emphasis when helpful.\n\n"
        f"TRIP DATABASE RECORD:\n{json.dumps(context, indent=2)}"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for item in history[-8:]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.AI_MODEL,
            "messages": messages,
            "max_tokens": 900,
            "temperature": 0.6,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def generate_chat_response(message, context, history=None):
    history = history or []
    message = (message or "").strip()
    if not message:
        raise ValueError("Message is required")

    if settings.OPENAI_API_KEY:
        try:
            return _call_openai_chat(message, context, history)
        except Exception:
            return _mock_chat_response(message, context)

    return _mock_chat_response(message, context)
