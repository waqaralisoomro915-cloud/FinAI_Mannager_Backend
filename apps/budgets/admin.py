from django.contrib import admin

from .models import Budget


admin.site.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "category",
        "amount",
        "start_date",
        "end_date",
    ]

    search_fields = ["user__email", "category__name"]
    list_select_related = ["user", "category"]

    readonly_fields = [
        "user",
        "category",
        "amount",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False