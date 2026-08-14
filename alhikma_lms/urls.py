from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from api.views import SsoCallbackView

urlpatterns = [
    path('portal-admin/',  admin.site.urls),
    path('portal/',        include('portal.urls')),
    path('api/',           include('api.urls')),
    path('sso/callback',   SsoCallbackView.as_view(), name='sso_callback'),
    path('',               include('courses.urls')),
    path('accounts/',      include('accounts.urls')),
    path('quizzes/',       include('quizzes.urls')),
    path('exams/',         include('exams.urls')),
    path('results/',       include('results.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
