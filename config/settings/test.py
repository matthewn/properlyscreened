from .base import *  # noqa: F401,F403

SECRET_KEY = 'django-insecure-test-key-not-for-production'
ALLOWED_HOSTS = ['*']

# Fast, isolated defaults for the test run.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
