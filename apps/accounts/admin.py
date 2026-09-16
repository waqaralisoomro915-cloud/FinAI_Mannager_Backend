from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


admin.site.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = [
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
    ]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    readonly_fields = ["last_login", "date_joined", "updated_at"]

    fieldsets = (
        (None, {
            "fields": ("email", "password"),
        }),
        ("Personal information", {
            "fields": ("first_name", "last_name"),
        }),
        ("Permissions", {
            "fields": (
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            ),
        }),
        ("Dates", {
            "fields": ("last_login", "date_joined", "updated_at"),
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "first_name",
                "last_name",
                "password1",
                "password2",
            ),
        }),
    )