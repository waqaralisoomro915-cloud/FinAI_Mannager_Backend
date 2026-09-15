from django.shortcuts import render

from django.http import HttpResponse
def common(request):
    return HttpResponse("Hello World this is common.py")
# Create your views here.
