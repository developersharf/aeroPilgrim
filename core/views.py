from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from datetime import timedelta, datetime

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

import json
import logging

from .models import (
    AsyncSearchJob,
    PaymentTransaction,
    QuotaExceeded,
    Search,
    SearchHistory,
    UserSubscription,
    Watchlist,
)
from .forms import SearchForm, RegistrationForm, LoginForm
from .services.flight_api import FlightAPIError, extract_flight_days, get_flight_data
from .services.ai_service import AI_ACTIONS, generate_ai_response
from .services.chat_service import build_trip_chat_context
from .services.n8n_chat_service import N8nChatError, send_n8n_message
from .services.rate_limit import (
    find_cached_search,
    ip_can_call_api,
    record_api_call,
)
from .services.search_orchestrator import (
    build_params,
    get_or_create_subscription,
    outcome_for_api,
    remaining_quota,
    run_search,
    top_results_from_outcome,
)
from .services.async_search import dispatch_async_search
from .services.payment_service import (
    PREMIUM_PRICE_USD,
    cancel_payment,
    confirm_payment,
    demo_gateway_url,
    init_payment,
    is_premium,
)

logger = logging.getLogger(__name__)


def _city_label(code):
    return dict(Search.CITY_CHOICES).get(code, code)


def _normalize_flight(day_obj):
    return {
        "flight_date": day_obj.get("day"),
        "price": day_obj.get("price"),
        "price_group": day_obj.get("group", "Standard"),
    }


def _get_flight_from_search(search, flight_date):
    days = extract_flight_days(search.api_response or {})
    for day in days:
        if day.get("day") == flight_date:
            return _normalize_flight(day)
    return None


def _build_trip_context(search, flight):
    return_date = None
    if flight["flight_date"]:
        depart = datetime.strptime(flight["flight_date"], "%Y-%m-%d").date()
        return_date = depart + timedelta(days=search.stay_days)

    return {
        "city_departure": search.city_departure,
        "city_arrival": search.city_arrival,
        "city_departure_label": _city_label(search.city_departure),
        "city_arrival_label": _city_label(search.city_arrival),
        "stay_days": search.stay_days,
        "timespan_to_search": search.timespan_to_search,
        "flight_date": flight["flight_date"],
        "price": flight["price"],
        "price_group": flight["price_group"],
        "return_date": str(return_date) if return_date else None,
    }


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def registerView(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            get_or_create_subscription(user)  # ensure Free sub exists from day 0
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('home')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RegistrationForm()

    return render(request, 'core/register.html', {'form': form})


def loginView(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Refresh premium flag so a user who upgraded in another session sees it
                is_premium(user)
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect('home')
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def logoutView(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')


# ---------------------------------------------------------------------------
# Home + search results
# ---------------------------------------------------------------------------
def searchView(request):
    """Display search form on home page"""
    form = SearchForm()
    quota = None
    if request.user.is_authenticated:
        sub, used, remaining = remaining_quota(request.user)
        quota = {
            "plan": sub.plan_label(),
            "is_premium": sub.is_premium,
            "daily_quota": sub.daily_quota,
            "used_today": used,
            "remaining": remaining,
            "price_usd": float(PREMIUM_PRICE_USD),
        }
    return render(request, "core/home.html", {"form": form, "quota": quota})


@login_required(login_url='login')
def searchResults(request):
    """Display search results - only accessible to logged-in users"""

    city_departure = request.GET.get("city_departure")
    city_arrival = request.GET.get("city_arrival")

    if not city_departure or not city_arrival:
        messages.error(request, "Please complete your search first.")
        return redirect("home")

    try:
        stay_days = int(request.GET.get("stay_days", 7))
        timespan = int(request.GET.get("timespan_to_search", 30))
    except (TypeError, ValueError):
        messages.error(request, "Invalid search parameters.")
        return redirect("home")

    flex_days = 0
    try:
        flex_days = int(request.GET.get("flex_days", 0) or 0)
    except (TypeError, ValueError):
        flex_days = 0
    stay_min = request.GET.get("stay_min")
    stay_max = request.GET.get("stay_max")

    params = build_params(city_departure, city_arrival, stay_days, timespan, flex_days)
    outcome = run_search(
        params,
        user=request.user,
        flex_days=flex_days,
        stay_min=stay_min,
        stay_max=stay_max,
    )

    if outcome.quota_exceeded:
        messages.warning(request, outcome.error)
        return redirect("pricing")

    if outcome.error and not outcome.candidates:
        messages.error(request, outcome.error)
        return redirect("home")

    top_results = [
        {
            "flight_date": c.departure_date,
            "price": c.price,
            "price_group": c.price_group,
            "stay_days": c.stay_days,
            "return_date": c.return_date,
        }
        for c in top_results_from_outcome(outcome, limit=5)
    ]

    # Reuse the *legacy* Search row (must exist for /search/flight/<id>/<date>/)
    try:
        legacy = Search.objects.filter(
            city_departure=city_departure,
            city_arrival=city_arrival,
            stay_days=stay_days,
            timespan_to_search=timespan,
        ).latest("created_at")
    except Search.DoesNotExist:
        legacy = None

    return render(request, "core/search_results.html", {
        "city_departure": _city_label(city_departure),
        "city_arrival": _city_label(city_arrival),
        "stay_days": stay_days,
        "results": top_results,
        "search": legacy,
        "cache_hit": outcome.cache_hit,
        "quota": outcome.quota,
        "cheapest": (
            {
                "flight_date": outcome.cheapest.departure_date,
                "price": outcome.cheapest.price,
                "price_group": outcome.cheapest.price_group,
                "return_date": outcome.cheapest.return_date,
            }
            if outcome.cheapest else None
        ),
    })


# ---------------------------------------------------------------------------
# AJAX / SPA endpoints (PHASE 10)
# ---------------------------------------------------------------------------
@login_required(login_url='login')
@require_POST
def api_search(request):
    """Run a search via fetch — returns JSON only."""
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = request.POST.dict()

    params = build_params(
        body.get("city_departure", "DAC"),
        body.get("city_arrival", "JED"),
        body.get("stay_days", 7),
        body.get("timespan_to_search", 30),
        body.get("flex_days", 0),
    )
    if not params["city_departure"] or not params["city_arrival"]:
        return JsonResponse({"error": "city_departure and city_arrival required"}, status=400)
    if params["city_departure"] == params["city_arrival"]:
        return JsonResponse({"error": "Departure and arrival must differ."}, status=400)

    outcome = run_search(
        params,
        user=request.user,
        flex_days=body.get("flex_days", 0),
        stay_min=body.get("stay_min"),
        stay_max=body.get("stay_max"),
    )
    payload = outcome_for_api(outcome)
    if outcome.cache_hit:
        legacy = (
            Search.objects.filter(
                city_departure=params["city_departure"],
                city_arrival=params["city_arrival"],
                stay_days=params["stay_days"],
                timespan_to_search=params["timespan_to_search"],
            )
            .order_by("-created_at")
            .first()
        )
        payload["legacy_search_id"] = legacy.id if legacy else None
    return JsonResponse(payload)


@login_required(login_url='login')
@require_POST
def api_search_async(request):
    """Dispatch the same search asynchronously (PHASE 8)."""
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = request.POST.dict()

    params = build_params(
        body.get("city_departure", "DAC"),
        body.get("city_arrival", "JED"),
        body.get("stay_days", 7),
        body.get("timespan_to_search", 30),
        body.get("flex_days", 0),
    )
    if not params["city_departure"] or not params["city_arrival"]:
        return JsonResponse({"error": "city_departure and city_arrival required"}, status=400)
    if params["city_departure"] == params["city_arrival"]:
        return JsonResponse({"error": "Departure and arrival must differ."}, status=400)
    try:
        job = dispatch_async_search(
            request.user,
            params,
            flex_days=body.get("flex_days", 0),
            stay_min=body.get("stay_min"),
            stay_max=body.get("stay_max"),
        )
    except QuotaExceeded as exc:
        return JsonResponse(
            {"error": str(exc), "quota_exceeded": True}, status=403
        )
    return JsonResponse({"job_id": job.job_id, "status": job.status})


@login_required(login_url='login')
@require_GET
def api_search_status(request, job_id):
    job = get_object_or_404(AsyncSearchJob, job_id=job_id, user=request.user)
    return JsonResponse({
        "job_id": job.job_id,
        "status": job.status,
        "result": job.result,
        "error": job.error,
    })


# ---------------------------------------------------------------------------
# Search history (PHASE 4)
# ---------------------------------------------------------------------------
@login_required(login_url='login')
@require_GET
def api_history(request):
    rows = SearchHistory.objects.filter(user=request.user)[:50]
    data = [
        {
            "id": r.id,
            "city_departure": r.city_departure,
            "city_arrival": r.city_arrival,
            "city_departure_label": _city_label(r.city_departure),
            "city_arrival_label": _city_label(r.city_arrival),
            "stay_days": r.stay_days,
            "timespan_to_search": r.timespan_to_search,
            "flex_days": r.flex_days,
            "total_results": r.total_results,
            "cheapest_price": float(r.cheapest_price) if r.cheapest_price else None,
            "cheapest_date": r.cheapest_date,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return JsonResponse({"history": data})


@login_required(login_url='login')
@require_POST
def api_history_rerun(request, history_id):
    history = get_object_or_404(SearchHistory, pk=history_id, user=request.user)
    params = build_params(
        history.city_departure,
        history.city_arrival,
        history.stay_days,
        history.timespan_to_search,
        history.flex_days,
    )
    outcome = run_search(params, user=request.user)
    return JsonResponse(outcome_for_api(outcome))


# ---------------------------------------------------------------------------
# Watchlists (PHASE 5)
# ---------------------------------------------------------------------------
def _serialize_watchlist(w):
    return {
        "id": w.id,
        "name": w.name,
        "origin": w.origin,
        "destination": w.destination,
        "origin_label": _city_label(w.origin),
        "destination_label": _city_label(w.destination),
        "budget_usd": w.budget_usd,
        "stay_min_days": w.stay_min_days,
        "stay_max_days": w.stay_max_days,
        "target_departure": (
            w.target_departure.isoformat() if w.target_departure else None
        ),
        "notify_ready": w.notify_ready,
        "updated_at": w.updated_at.isoformat(),
    }


@login_required(login_url='login')
@require_GET
def api_watchlist_list(request):
    rows = Watchlist.objects.filter(user=request.user)
    return JsonResponse({"watchlists": [_serialize_watchlist(w) for w in rows]})


@login_required(login_url='login')
@require_POST
def api_watchlist_create(request):
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = request.POST.dict()

    origin = body.get("origin")
    destination = body.get("destination")
    if not origin or not destination or origin == destination:
        return JsonResponse({"error": "origin and destination must differ."}, status=400)

    w = Watchlist.objects.create(
        user=request.user,
        name=body.get("name") or f"{_city_label(origin)} → {_city_label(destination)}",
        origin=origin,
        destination=destination,
        budget_usd=body.get("budget_usd") or None,
        stay_min_days=int(body.get("stay_min_days") or 7),
        stay_max_days=int(body.get("stay_max_days") or 15),
        target_departure=body.get("target_departure") or None,
        notify_ready=bool(body.get("notify_ready")),
    )
    return JsonResponse({"watchlist": _serialize_watchlist(w)})


@login_required(login_url='login')
@require_POST
def api_watchlist_update(request, pk):
    w = get_object_or_404(Watchlist, pk=pk, user=request.user)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = request.POST.dict()

    for field in (
        "name", "origin", "destination", "budget_usd",
        "stay_min_days", "stay_max_days", "target_departure", "notify_ready",
    ):
        if field in body:
            setattr(w, field, body[field])
    w.save()
    return JsonResponse({"watchlist": _serialize_watchlist(w)})


@login_required(login_url='login')
@require_POST
def api_watchlist_delete(request, pk):
    w = get_object_or_404(Watchlist, pk=pk, user=request.user)
    w.delete()
    return JsonResponse({"deleted": pk})


# ---------------------------------------------------------------------------
# Subscription / pricing / payment (PHASE 3)
# ---------------------------------------------------------------------------
@login_required(login_url='login')
def pricing(request):
    sub, used, remaining = remaining_quota(request.user)
    context = {
        "plan": sub.plan_label(),
        "is_premium": sub.is_premium,
        "daily_quota": sub.daily_quota,
        "used_today": used,
        "remaining": remaining,
        "price_usd": float(PREMIUM_PRICE_USD),
    }
    return render(request, "core/pricing.html", context)


@login_required(login_url='login')
@require_POST
def upgrade_start(request):
    pt = init_payment(request.user)
    return redirect(demo_gateway_url(pt.tran_id))


@login_required(login_url='login')
def payment_demo(request, tran_id):
    """A fully-contained demo payment page (no external gateway required)."""
    pt = get_object_or_404(PaymentTransaction, tran_id=tran_id, user=request.user)
    if pt.status != PaymentTransaction.STATUS_PENDING:
        return redirect("payment_result", tran_id=pt.tran_id)
    return render(request, "core/payment_demo.html", {"pt": pt})


@login_required(login_url='login')
@require_POST
def payment_demo_callback(request, tran_id):
    """Demo 'gateway callback' — the user clicked Pay or Cancel."""
    action = request.POST.get("action", "cancel")
    if action == "pay":
        confirm_payment(
            tran_id,
            gateway_payload={"demo": True, "ip": request.META.get("REMOTE_ADDR", "")},
        )
        messages.success(request, "Welcome to Premium! Your quota has been bumped to 5 searches/day.")
    elif action == "cancel":
        cancel_payment(tran_id, gateway_payload={"demo": True})
        messages.info(request, "Payment cancelled. No charges were made.")
    else:
        fail_payment(tran_id, gateway_payload={"demo": True, "reason": action})
        messages.error(request, "Payment could not be completed.")
    return redirect("payment_result", tran_id=tran_id)


@login_required(login_url='login')
def payment_result(request, tran_id):
    pt = get_object_or_404(PaymentTransaction, tran_id=tran_id, user=request.user)
    sub, used, remaining = remaining_quota(request.user)
    context = {
        "pt": pt,
        "plan": sub.plan_label(),
        "is_premium": sub.is_premium,
        "daily_quota": sub.daily_quota,
        "used_today": used,
        "remaining": remaining,
    }
    return render(request, "core/payment_result.html", context)


# ---------------------------------------------------------------------------
# Dashboard (PHASE 10)
# ---------------------------------------------------------------------------
@login_required(login_url='login')
def dashboard(request):
    history = SearchHistory.objects.filter(user=request.user)[:20]
    watchlists = Watchlist.objects.filter(user=request.user)[:20]
    sub, used, remaining = remaining_quota(request.user)
    return render(
        request,
        "core/dashboard.html",
        {
            "history": history,
            "watchlists": watchlists,
            "plan": sub.plan_label(),
            "is_premium": sub.is_premium,
            "daily_quota": sub.daily_quota,
            "quota_used": used,
            "quota_total": sub.daily_quota,
            "used_today": used,
            "remaining": remaining,
            "price_usd": float(PREMIUM_PRICE_USD),
        },
    )


# ---------------------------------------------------------------------------
# Flight detail / chat / AI  (unchanged behavior)
# ---------------------------------------------------------------------------
@login_required(login_url='login')
def flightDetail(request, search_id, flight_date):
    """Show full details for a selected flight date"""
    search = get_object_or_404(Search, pk=search_id)
    flight = _get_flight_from_search(search, flight_date)

    if not flight:
        messages.error(request, "This flight option is no longer available.")
        return redirect(
            f"/search/?city_departure={search.city_departure}"
            f"&city_arrival={search.city_arrival}"
            f"&stay_days={search.stay_days}"
            f"&timespan_to_search={search.timespan_to_search}"
        )

    trip = _build_trip_context(search, flight)

    return render(request, "core/flight_detail.html", {
        "search": search,
        "flight": flight,
        "trip": trip,
        "ai_actions": AI_ACTIONS,
        "city_departure": trip["city_departure_label"],
        "city_arrival": trip["city_arrival_label"],
    })


@login_required(login_url='login')
@require_POST
def aiAction(request, search_id, flight_date):
    """Generate AI response for a trip action button"""
    search = get_object_or_404(Search, pk=search_id)
    flight = _get_flight_from_search(search, flight_date)

    if not flight:
        return JsonResponse({"success": False, "error": "Flight not found."}, status=404)

    try:
        body = json.loads(request.body)
        action = body.get("action")
    except json.JSONDecodeError:
        action = request.POST.get("action")

    if action not in AI_ACTIONS:
        return JsonResponse({"success": False, "error": "Invalid action."}, status=400)

    context = _build_trip_context(search, flight)
    content = generate_ai_response(action, context)

    return JsonResponse({
        "success": True,
        "action": action,
        "label": AI_ACTIONS[action]["label"],
        "content": content,
    })


@login_required(login_url='login')
@require_POST
def tripChat(request, search_id, flight_date):
    """Proxy chat messages to n8n with this trip's database context attached."""
    search = get_object_or_404(Search, pk=search_id)
    flight = _get_flight_from_search(search, flight_date)

    if not flight:
        return JsonResponse({"success": False, "error": "Flight not found."}, status=404)

    try:
        body = json.loads(request.body)
        message = (body.get("message") or "").strip()
        session_id = body.get("session_id") or (
            f"trip-{search_id}-{flight_date}-u{request.user.id}"
        )
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid request."}, status=400)

    if not message:
        return JsonResponse({"success": False, "error": "Message is required."}, status=400)

    trip_context = build_trip_chat_context(search, flight)

    try:
        content = send_n8n_message(message, session_id, trip_context)
    except N8nChatError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=502)

    return JsonResponse({
        "success": True,
        "content": content,
        "session_id": session_id,
    })


# ---------------------------------------------------------------------------
# Bot endpoints  (legacy — kept identical behavior)
# ---------------------------------------------------------------------------
@csrf_exempt
@require_GET
def botTripContext(request):
    if not _check_bot_api_key(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        search_id = int(request.GET.get("search_id", ""))
    except (TypeError, ValueError):
        return JsonResponse({"error": "search_id is required"}, status=400)

    flight_date = request.GET.get("flight_date")
    if not flight_date:
        return JsonResponse({"error": "flight_date is required"}, status=400)

    search = get_object_or_404(Search, pk=search_id)
    flight = _get_flight_from_search(search, flight_date)
    if not flight:
        return JsonResponse({"error": "Flight not found for this search."}, status=404)

    return JsonResponse(build_trip_chat_context(search, flight))


def _check_bot_api_key(request):
    sent_key = request.headers.get("X-Bot-Api-Key")
    return sent_key and sent_key == settings.BOT_API_KEY


@csrf_exempt
@require_GET
def botSearch(request):
    if not _check_bot_api_key(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    city_departure = request.GET.get("from_city")
    city_arrival = request.GET.get("to_city")
    if not city_departure or not city_arrival:
        return JsonResponse({"error": "from_city and to_city are required"}, status=400)
    try:
        stay_days = int(request.GET.get("stay_days", 7))
        timespan = int(request.GET.get("timespan_to_search", 30))
    except (TypeError, ValueError):
        return JsonResponse({"error": "stay_days and timespan_to_search must be integers"}, status=400)

    # Bots are rate-limited via IP (legacy behavior)
    if not ip_can_call_api(request):
        return JsonResponse({
            "error": "rate_limit_exceeded",
            "message": "Search limit reached for this route. Try again later.",
        }, status=429)

    params = build_params(city_departure, city_arrival, stay_days, timespan)
    try:
        data = get_flight_data(city_departure, city_arrival, timespan)
    except FlightAPIError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    # Persist into legacy Search + SearchCache so subsequent bot calls get the cache.
    Search.objects.filter(
        city_departure=city_departure,
        city_arrival=city_arrival,
        stay_days=stay_days,
        timespan_to_search=timespan,
    ).delete()
    search = Search.objects.create(
        city_departure=city_departure,
        city_arrival=city_arrival,
        stay_days=stay_days,
        timespan_to_search=timespan,
        api_response=data,
    )
    record_api_call(request)

    from core.models import SearchCache
    canonical = {
        "city_departure": city_departure,
        "city_arrival": city_arrival,
        "stay_days": stay_days,
        "timespan_to_search": timespan,
        "flex_days": 0,
    }
    qhash = SearchCache.build_query_hash(canonical)
    SearchCache.objects.update_or_create(
        query_hash=qhash,
        defaults={
            "city_departure": city_departure,
            "city_arrival": city_arrival,
            "stay_days": stay_days,
            "timespan_to_search": timespan,
            "flex_days": 0,
            "search_params": canonical,
            "api_response": data,
            "last_fetched": timezone_now_safe(),
        },
    )

    days = extract_flight_days(data)
    priced = [d for d in days if d.get("price") is not None]
    top = sorted(priced, key=lambda x: x["price"])[:5]

    results = []
    for flight in top:
        depart = datetime.strptime(flight["day"], "%Y-%m-%d").date()
        results.append({
            "date": flight["day"],
            "price": flight["price"],
            "currency": "USD",
            "return_date": str(depart + timedelta(days=stay_days)),
        })

    return JsonResponse({
        "search_id": search.id,
        "from_city": _city_label(city_departure),
        "to_city": _city_label(city_arrival),
        "stay_days": stay_days,
        "results": results,
    })


def timezone_now_safe():
    from django.utils import timezone
    return timezone.now()