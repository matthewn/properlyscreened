from django.conf import settings
from django.urls import include, path
from django.contrib import admin
from django.views.generic import TemplateView

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from wagtailautocomplete.urls.admin import urlpatterns as autocomplete_admin_urls

from search import views as search_views

urlpatterns = [
    path('dja/', admin.site.urls),
    # Must precede the `cms/` Wagtail admin include below. The autocomplete
    # widget derives its API base from `wagtailadmin_home` (here `/cms/`),
    # so its endpoints have to live under that same prefix.
    path('cms/autocomplete/', include(autocomplete_admin_urls)),
    path('cms/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),
    path('search/', search_views.search, name='search'),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt', content_type='text/plain')),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
