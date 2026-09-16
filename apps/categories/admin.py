from django.contrib import admin

from .models import Category


admin.site.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "user",
        "category_type",
        "is_active",
    ]

    list_filter = ["category_type", "is_active"]
    search_fields = ["name", "user__email"]
    list_select_related = ["user"]

    readonly_fields = [
        "user",
        "name",
        "category_type",
        "description",
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