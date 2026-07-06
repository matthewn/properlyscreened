from .base import *

DEBUG = False

WAGTAILADMIN_BASE_URL = 'https://properlyscreened.com'

# Hand outgoing mail to the local msmtp binary, sendmail-style.
EMAIL_BACKEND = 'properlyscreened.mail.MsmtpEmailBackend'
DEFAULT_FROM_EMAIL = 'bot@properlyscreened.com'
SERVER_EMAIL = 'bot@properlyscreened.com'

# ManifestStaticFilesStorage is recommended in production, to prevent
# outdated JavaScript / CSS assets being served from cache
# (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/6.0/ref/contrib/staticfiles/#manifeststaticfilesstorage
STORAGES["staticfiles"][
    "BACKEND"
] = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# Log request errors (500s) to stderr so they reach the gunicorn error log.
# Django's default console handler is gated by DEBUG=True, so without this
# production tracebacks are silently swallowed.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR"},
    },
}

try:
    from .local import *
except ImportError:
    pass
