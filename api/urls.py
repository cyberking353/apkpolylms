from django.urls import path

from .views import (
    SsoAuthView,
    SyncCourseView,
    SyncDepartmentView,
    SyncProgrammeView,
    SyncRegistrationView,
    SyncSessionView,
    SyncStudentView,
)

app_name = 'api'

urlpatterns = [
    path('v1/sync/students',      SyncStudentView.as_view(),       name='sync_students'),
    path('v1/sync/courses',       SyncCourseView.as_view(),        name='sync_courses'),
    path('v1/sync/departments',   SyncDepartmentView.as_view(),    name='sync_departments'),
    path('v1/sync/programmes',    SyncProgrammeView.as_view(),     name='sync_programmes'),
    path('v1/sync/sessions',      SyncSessionView.as_view(),       name='sync_sessions'),
    path('v1/sync/registrations', SyncRegistrationView.as_view(),  name='sync_registrations'),
    path('v1/auth/sso',           SsoAuthView.as_view(),           name='auth_sso'),
]
