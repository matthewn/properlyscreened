from django.core.exceptions import PermissionDenied
from django.shortcuts import render


def handler500(request):
    # Render with the request so context processors (e.g. newsletter_page)
    # and request-dependent tags in base.html work, unlike Django's default.
    return render(request, '500.html', status=500)


def force403(request):
    raise PermissionDenied


def force500(request):
    raise Exception('Forced 500 for testing.')
