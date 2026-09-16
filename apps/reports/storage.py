from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_report_storage():
    return FileSystemStorage(
        location=settings.BASE_DIR / "private_reports"
    )