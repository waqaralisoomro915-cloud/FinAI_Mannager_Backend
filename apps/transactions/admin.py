from django.contrib import admin

from .models import Transaction


admin.site.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "transaction_type",
        "wallet",
        "destination_wallet",
        "amount",
        "transaction_date",
        "is_void",
    ]

    list_filter = ["transaction_type", "is_void", "transaction_date"]
    search_fields = ["user__email", "description"]
    list_select_related = ["user", "wallet", "destination_wallet"]

    readonly_fields = [
        field.name for field in Transaction._meta.fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False