from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from api.views import SsoCallbackView


def service_worker(request):
    """Serve the PWA service worker from the root scope."""
    with open(settings.BASE_DIR / 'static' / 'sw.js') as f:
        return HttpResponse(f.read(), content_type='application/javascript',
                            headers={'Service-Worker-Allowed': '/'})


urlpatterns = [
    path('portal-admin/',  admin.site.urls),
    path('sw.js',          service_worker),
    path('portal/',        include('portal.urls')),
    path('api/',           include('api.urls')),
    path('sso/callback',   SsoCallbackView.as_view(), name='sso_callback'),
    path('',               include('courses.urls')),
    path('accounts/',      include('accounts.urls')),
    path('quizzes/',       include('quizzes.urls')),
    path('exams/',         include('exams.urls')),
    path('results/',       include('results.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
