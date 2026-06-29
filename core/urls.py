from django.urls import path
from . import views


urlpatterns = [
    # Home page
    path('', views.searchView, name='home'),

    # Authentication
    path('register/', views.registerView, name='register'),
    path('login/', views.loginView, name='login'),
    path('logout/', views.logoutView, name='logout'),

    # Search functionality
    path('search/', views.searchResults, name='search_results'),
    path(
        'search/flight/<int:search_id>/<str:flight_date>/',
        views.flightDetail,
        name='flight_detail',
    ),
    path("api/bot-search/", views.botSearch, name="bot_search"),
    path("api/bot-trip-context/", views.botTripContext, name="bot_trip_context"),
    path(
        'search/flight/<int:search_id>/<str:flight_date>/ai/',
        views.aiAction,
        name='ai_action',
    ),
    path(
        'search/flight/<int:search_id>/<str:flight_date>/chat/',
        views.tripChat,
        name='trip_chat',
    ),

    # ------------------------------------------------------------------
    # PHASE 10 — SPA / AJAX endpoints + dashboard
    # ------------------------------------------------------------------
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/search/', views.api_search, name='api_search'),
    path('api/search/async/', views.api_search_async, name='api_search_async'),
    path(
        'api/search/status/<str:job_id>/',
        views.api_search_status,
        name='api_search_status',
    ),

    # PHASE 4 — history
    path('api/history/', views.api_history, name='api_history'),
    path(
        'api/history/<int:history_id>/rerun/',
        views.api_history_rerun,
        name='api_history_rerun',
    ),

    # PHASE 5 — watchlists
    path('api/watchlists/', views.api_watchlist_list, name='api_watchlist_list'),
    path(
        'api/watchlists/create/',
        views.api_watchlist_create,
        name='api_watchlist_create',
    ),
    path(
        'api/watchlists/<int:pk>/update/',
        views.api_watchlist_update,
        name='api_watchlist_update',
    ),
    path(
        'api/watchlists/<int:pk>/delete/',
        views.api_watchlist_delete,
        name='api_watchlist_delete',
    ),

    # PHASE 3 — pricing + demo payment
    path('pricing/', views.pricing, name='pricing'),
    path('pricing/upgrade/', views.upgrade_start, name='upgrade_start'),
    path(
        'payment/demo/<str:tran_id>/',
        views.payment_demo,
        name='payment_demo',
    ),
    path(
        'payment/demo/<str:tran_id>/callback/',
        views.payment_demo_callback,
        name='payment_demo_callback',
    ),
    path(
        'payment/result/<str:tran_id>/',
        views.payment_result,
        name='payment_result',
    ),
]
