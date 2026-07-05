# Custom en input formats so the Wagtail admin accepts AM/PM times.
# With USE_L10N always on (Django 5+), TIME/DATETIME_INPUT_FORMATS set in
# settings are ignored; Django reads them from the active locale's format
# module, so they must be overridden here via FORMAT_MODULE_PATH.

TIME_INPUT_FORMATS = [
    '%I:%M %p',  # 3:45 PM
    '%I:%M%p',  # 3:45PM
    '%H:%M:%S',
    '%H:%M:%S.%f',
    '%H:%M',
]

DATETIME_INPUT_FORMATS = [
    '%Y-%m-%d %I:%M %p',  # 2006-10-25 3:45 PM
    '%Y-%m-%d %I:%M%p',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d',
]
