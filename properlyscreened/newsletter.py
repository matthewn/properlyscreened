"""
Newsletter signup that enrolls contacts in Brevo via double opt-in.

NewsletterPage.serve() calls process_signup() on POST; it hands the email to
Brevo's doubleOptinConfirmation endpoint. Brevo sends the confirmation email,
and on click enrolls the contact in the list and redirects them to
BREVO_DOI_REDIRECT_URL (our 'subscribed' page).
"""
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.template.response import TemplateResponse

from properlyscreened.models import HomePage

import requests

BREVO_DOI_URL = 'https://api.brevo.com/v3/contacts/doubleOptinConfirmation'

# lenient per-IP cap; the honeypot is the main bot defense
THROTTLE_LIMIT = 5
THROTTLE_WINDOW = 3600


def _hero():
    home = HomePage.objects.live().public().first()
    return home.hero if home else None


def _throttled(request):
    key = 'newsletter-throttle:' + request.META.get('REMOTE_ADDR', '')
    count = cache.get(key, 0)
    if count >= THROTTLE_LIMIT:
        return True
    cache.set(key, count + 1, THROTTLE_WINDOW)
    return False


def _subscribe(email):
    """
    Ask Brevo to start double opt-in; return 'ok', 'exists', or 'error'.
    """
    if not settings.BREVO_API_KEY:
        return 'error'
    try:
        response = requests.post(
            BREVO_DOI_URL,
            headers={'api-key': settings.BREVO_API_KEY, 'accept': 'application/json'},
            json={
                'email': email,
                'includeListIds': [settings.BREVO_LIST_ID],
                'templateId': settings.BREVO_DOI_TEMPLATE_ID,
                'redirectionUrl': settings.BREVO_DOI_REDIRECT_URL,
            },
            timeout=10,
        )
    except requests.RequestException:
        return 'error'
    if 200 <= response.status_code < 300:
        return 'ok'
    try:
        code = response.json().get('code')
    except ValueError:
        code = None
    if response.status_code == 400 and code == 'duplicate_parameter':
        return 'exists'
    return 'error'


def process_signup(request):
    """
    Handle a signup POST. Return 'ok', 'exists', or an error message string.
    """
    # honeypot: bots fill hidden fields; silently accept without subscribing
    if request.POST.get('website'):
        return 'ok'
    email = (request.POST.get('email') or '').strip()
    try:
        validate_email(email)
    except ValidationError:
        return 'Please enter a valid email address.'
    if _throttled(request):
        return 'Too many attempts. Please try again later.'
    result = _subscribe(email)
    if result in ('ok', 'exists'):
        return result
    return 'Sorry, something went wrong. Please try again later.'


def check_inbox(request):
    return TemplateResponse(
        request,
        'properlyscreened/newsletter/check_inbox.html',
        {'hero': _hero()},
    )


def subscribed(request):
    return TemplateResponse(
        request,
        'properlyscreened/newsletter/subscribed.html',
        {'hero': _hero()},
    )
