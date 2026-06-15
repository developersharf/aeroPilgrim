import requests
from django.conf import settings


AI_ACTIONS = {
    "book_plan": {
        "label": "Book the Plan for Me",
        "icon": "ph-calendar-check",
        "description": "Get a step-by-step booking guide for this Umrah trip",
    },
    "cheapest_hotel": {
        "label": "Find the Cheapest Hotel",
        "icon": "ph-buildings",
        "description": "AI-recommended budget hotels near the Haram",
    },
    "itinerary": {
        "label": "Plan My Umrah Itinerary",
        "icon": "ph-map-trifold",
        "description": "Day-by-day Umrah schedule tailored to your stay",
    },
    "budget_breakdown": {
        "label": "Full Budget Breakdown",
        "icon": "ph-currency-dollar",
        "description": "Estimated total cost including flight, hotel, and transport",
    },
}


def _build_prompt(action, context):
    departure = context["city_departure_label"]
    arrival = context["city_arrival_label"]
    flight_date = context["flight_date"]
    price = context["price"]
    stay_days = context["stay_days"]
    return_date = context.get("return_date", "N/A")
    price_group = context.get("price_group", "Standard")

    prompts = {
        "book_plan": (
            f"You are an Umrah travel assistant. A pilgrim wants to book an Umrah trip "
            f"from {departure} to {arrival}, departing on {flight_date}, staying {stay_days} days "
            f"(return around {return_date}), with a flight priced at ${price} ({price_group} fare). "
            f"Provide a clear, actionable booking plan with numbered steps covering: "
            f"flight booking, visa requirements for Bangladeshi pilgrims, hotel selection, "
            f"ground transport in Saudi Arabia, and important deadlines. Be practical and concise."
        ),
        "cheapest_hotel": (
            f"You are an Umrah travel assistant. Recommend budget-friendly hotels for a "
            f"{stay_days}-day Umrah stay in {arrival} (pilgrim flying from {departure} on {flight_date}). "
            f"List 4-5 hotel options with estimated nightly rates in USD, distance to the Haram, "
            f"star rating, and one pro/con each. Focus on value for Bangladeshi pilgrims."
        ),
        "itinerary": (
            f"You are an Umrah travel assistant. Create a detailed {stay_days}-day Umrah itinerary "
            f"for a pilgrim traveling from {departure} to {arrival}, arriving {flight_date}. "
            f"Include daily activities: Umrah rituals, prayers, ziyarat in Makkah and Madinah "
            f"(if applicable), rest periods, and meal suggestions. Use day numbers and times."
        ),
        "budget_breakdown": (
            f"You are an Umrah travel assistant. Provide a realistic total trip budget breakdown "
            f"for a {stay_days}-day Umrah from {departure} to {arrival}, departing {flight_date}. "
            f"The selected flight costs ${price}. Break down: flights (round-trip estimate), "
            f"visa fees, hotels, food, local transport, shopping/misc, and a total range "
            f"(budget vs comfortable). Use USD and show approximate amounts."
        ),
    }
    return prompts.get(action, prompts["book_plan"])


def _mock_response(action, context):
    departure = context["city_departure_label"]
    arrival = context["city_arrival_label"]
    flight_date = context["flight_date"]
    price = context["price"]
    stay_days = context["stay_days"]
    return_date = context.get("return_date", "N/A")

    mocks = {
        "book_plan": f"""## Your Umrah Booking Plan

**Route:** {departure} → {arrival} | **Depart:** {flight_date} | **Stay:** {stay_days} days | **Return:** ~{return_date}

### Step 1 — Secure Your Flight (${price})
Book this fare quickly — {context.get('price_group', 'current')} prices change often. Use the airline's official site or a trusted OTA. Confirm baggage allowance (usually 30–46 kg for Umrah routes).

### Step 2 — Umrah Visa
Apply through an approved Saudi Umrah agent in Bangladesh. You'll need: valid passport (6+ months), passport photos, vaccination certificate, and confirmed return ticket. Processing takes 3–7 business days.

### Step 3 — Hotel Near the Haram
Book early for proximity to Masjid al-Haram or Masjid an-Nabawi. Budget: $40–80/night (economy), $80–150/night (mid-range). Look for hotels with shuttle service to the Haram.

### Step 4 — Ground Transport
- Airport → Hotel: Pre-book a taxi or use official airport taxis (~$25–40)
- Makkah ↔ Madinah: SAPTCO bus (~$15) or private car (~$80–120)
- Local: Walking + hotel shuttles

### Step 5 — Before You Fly
- Travel insurance
- Saudi SIM card or international roaming
- Download Nusuk app for permits
- Pack ihram, comfortable sandals, prayer mat

*Click "Find the Cheapest Hotel" or "Full Budget Breakdown" for more AI-powered details.*""",

        "cheapest_hotel": f"""## Budget Hotels Near {arrival}

*For your {stay_days}-day stay (arriving {flight_date})*

| Hotel | Est. Rate/Night | Distance to Haram | Notes |
|-------|----------------|-------------------|-------|
| **Dar Al Eiman Grand** | ~$45–55 | 5 min walk | Popular with Bangladeshi groups, basic but clean |
| **Elaf Ajyad Hotel** | ~$50–65 | 8 min walk | Good value, breakfast included |
| **Makkah Hotel** | ~$55–70 | 10 min walk | Renovated rooms, shuttle available |
| **Anjum Hotel** | ~$60–75 | 3 min walk | Excellent location, book early |
| **Al Kiswah Towers** | ~$40–50 | 15 min walk | Budget option, metro access nearby |

### Tips for Saving
- Book 4–6 weeks ahead for best rates
- Weekday stays are often cheaper than weekends
- Consider hotels slightly farther with free shuttle (saves 20–30%)
- Group bookings through agents can reduce cost to ~$35/night

*Estimated hotel total for {stay_days} nights: **${40 * stay_days}–${75 * stay_days}***""",

        "itinerary": f"""## {stay_days}-Day Umrah Itinerary

**{departure} → {arrival}** | Arrive: {flight_date}

### Day 1 — Arrival & Umrah
- Land at airport, clear immigration
- Transfer to hotel, rest and freshen up
- Enter Masjid al-Haram, perform **Umrah** (Tawaf + Sa'i + Halq/Taqsir)
- Pray at the Haram, light dinner

### Day 2 — Worship & Rest
- Fajr at the Haram
- Morning rest (avoid peak heat 11am–3pm)
- Dhuhr & Asr at the Haram
- Evening Tawaf (less crowded)
- Shop for dates and gifts on Suq al-Lail

### Day 3 — Ziyarat in Makkah
- Visit: Cave of Hira, Jabal al-Nour, Mina, Muzdalifah area
- Jummah prayer at the Haram if applicable
- Evening: personal du'a time at the Kaaba

### Days 4–{stay_days - 2} — Deepen Your Worship
- Daily prayers at the Haram
- Optional: day trip to Taif or Madinah (if in your plan)
- Multiple Tawafs, Quran reading, dhikr
- Rest days as needed — don't overexert

### Day {stay_days - 1} — Farewell
- **Farewell Tawaf** (Tawaf al-Wada')
- Pack, settle hotel bills
- Final shopping if needed

### Day {stay_days} — Return ({return_date})
- Transfer to airport
- Flight back to {departure}

*Adjust based on whether you're visiting Madinah — add 2–3 days there between Makkah stays.*""",

        "budget_breakdown": f"""## Total Trip Budget Estimate

**{departure} → {arrival}** | {stay_days} days | Depart: {flight_date}

| Category | Budget | Comfortable |
|----------|--------|-------------|
| **Round-trip flights** | ${price} | ${float(price) * 1.2:.0f} |
| **Umrah visa** | $120 | $150 |
| **Hotel ({stay_days} nights)** | ${35 * stay_days} | ${70 * stay_days} |
| **Food & drinks** | ${15 * stay_days} | ${30 * stay_days} |
| **Local transport** | $80 | $150 |
| **SIM + misc** | $30 | $50 |
| **Shopping & gifts** | $50 | $150 |
| **TOTAL** | **~${float(price) + 120 + 35 * stay_days + 15 * stay_days + 80 + 30 + 50:.0f}** | **~${float(price) * 1.2 + 150 + 70 * stay_days + 30 * stay_days + 150 + 50 + 150:.0f}** |

### What's Included
- Flight fare shown is one-way calendar price; round-trip may differ
- Visa via approved agent
- Hotels within 15 min of Haram
- Basic meals (street food / hotel breakfast)

### Ways to Save
- Travel in off-peak months (after Ramadan, before Hajj)
- Share hotel rooms with family
- Use SAPTCO buses instead of private cars
- Book flights 6–8 weeks ahead""",
    }
    return mocks.get(action, mocks["book_plan"])


def _call_openai(prompt):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful Umrah travel assistant for pilgrims from Bangladesh. "
                        "Give practical, well-structured advice using markdown formatting."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1200,
            "temperature": 0.7,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def generate_ai_response(action, context):
    if action not in AI_ACTIONS:
        raise ValueError(f"Unknown action: {action}")

    if settings.OPENAI_API_KEY:
        try:
            prompt = _build_prompt(action, context)
            return _call_openai(prompt)
        except Exception:
            return _mock_response(action, context)

    return _mock_response(action, context)
