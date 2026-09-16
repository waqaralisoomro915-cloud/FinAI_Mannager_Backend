from django.contrib import admin

from .models import Wallet


admin.site.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "user",
        "wallet_type",
        "currency",
        "opening_balance",
        "is_active",
    ]

    list_filter = ["wallet_type", "currency", "is_active"]
    search_fields = ["name", "user__email"]
    list_select_related = ["user"]

    readonly_fields = [
        "user",
        "name",
        "wallet_type",
        "currency",
        "opening_balance",
        "is_active",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False