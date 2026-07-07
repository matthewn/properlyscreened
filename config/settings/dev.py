from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-21m78*qzv03i3xps*g-acibhqta+^h4$3d=mxdcc=(jyw1znev'

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ['*']

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Live-reload the browser on template/static/Python changes (dev only). The
# middleware auto-injects its script into HTML responses while DEBUG is on.
INSTALLED_APPS += ['django_browser_reload']  # noqa: F405
MIDDLEWARE += ['django_browser_reload.middleware.BrowserReloadMiddleware']  # noqa: F405
