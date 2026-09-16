from django.contrib import admin

from .models import SavingsContribution, SavingsGoal


class ReadOnlySavingsAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [
            field.name for field in self.model._meta.fields
        ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SavingsGoal)
class SavingsGoalAdmin(ReadOnlySavingsAdmin):
    list_display = [
        "id",
        "name",
        "user",
        "wallet",
        "target_amount",
        "deadline",
        "is_active",
    ]

    search_fields = ["name", "user__email"]
    list_filter = ["is_active"]
    list_select_related = ["user", "wallet"]


admin.site.register(SavingsContribution)
class SavingsContributionAdmin(ReadOnlySavingsAdmin):
    list_display = [
        "id",
        "goal",
        "entry_type",
        "amount",
        "created_at",
    ]

    list_filter = ["entry_type"]
    list_select_related = ["goal"]