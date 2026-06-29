from django.contrib import admin
from .models import (
    AsyncSearchJob,
    PaymentTransaction,
    Search,
    SearchCache,
    SearchHistory,
    SearchRateLimit,
    SearchUsage,
    UserSubscription,
    Watchlist,
)

admin.site.register(Search)
admin.site.register(SearchRateLimit)
admin.site.register(SearchCache)
admin.site.register(UserSubscription)
admin.site.register(SearchUsage)
admin.site.register(Watchlist)
admin.site.register(PaymentTransaction)
admin.site.register(AsyncSearchJob)
admin.site.register(SearchHistory)