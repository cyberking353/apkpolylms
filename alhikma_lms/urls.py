from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve as media_serve
from django.http import HttpResponse, JsonResponse
from django.db import connection
from django.views.decorators.http import require_GET
from api.views import SsoCallbackView


def service_worker(request):
    """Serve the PWA service worker from the root scope."""
    with open(settings.BASE_DIR / 'static' / 'sw.js') as f:
        return HttpResponse(f.read(), content_type='application/javascript',
                            headers={'Service-Worker-Allowed': '/'})


@require_GET
def healthz(request):
    """Lightweight liveness/readiness probe for the load balancer + uptime monitor."""
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    payload = {'status': 'ok' if db_ok else 'degraded', 'db': 'ok' if db_ok else 'down'}
    return JsonResponse(payload,
                        status=200 if db_ok else 503)


def offline_page(request):
    from django.shortcuts import render
    return render(request, 'offline.html')


urlpatterns = [
    path('portal-admin/',  admin.site.urls),
    path('healthz',        healthz, name='healthz'),
    path('sw.js',          service_worker),
    path('offline/',       offline_page),
    path('portal/',        include('portal.urls')),
    path('api/',           include('api.urls')),
    path('sso/callback',   SsoCallbackView.as_view(), name='sso_callback'),
    path('',               include('courses.urls')),
    path('accounts/',      include('accounts.urls')),
    path('quizzes/',       include('quizzes.urls')),
    path('exams/',         include('exams.urls')),
    path('results/',       include('results.urls')),
    # Media served by Django itself in all environments (Paas has no nginx).
    re_path(r'^media/(?P<path>.*)$', media_serve,
            {'document_root': settings.MEDIA_ROOT}),
]
