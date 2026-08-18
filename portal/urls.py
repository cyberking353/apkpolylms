from django.urls import path
from . import views
app_name = 'portal'
urlpatterns = [
    path('',                        views.dashboard,         name='dashboard'),
    path('login/',                  views.portal_login,      name='login'),
    path('logout/',                 views.portal_logout,     name='logout'),
    # Students
    path('students/',               views.student_list,      name='student_list'),
    path('students/export/',         views.student_export,       name='student_export'),
    path('students/new/',           views.student_create,       name='student_create'),
    path('students/bulk-upload/',   views.student_bulk_upload,  name='student_bulk_upload'),
    path('students/<int:pk>/edit/', views.student_edit,      name='student_edit'),
    path('students/<int:pk>/promote/', views.student_promote, name='student_promote'),
    path('students/<int:pk>/reset-password/', views.student_reset_password, name='student_reset_password'),
    # Lecturers
    path('lecturers/',              views.lecturer_list,     name='lecturer_list'),
    path('lecturers/new/',          views.lecturer_create,   name='lecturer_create'),
    path('lecturers/<int:pk>/edit/', views.lecturer_edit,    name='lecturer_edit'),
    path('lecturers/<int:pk>/delete/', views.lecturer_delete, name='lecturer_delete'),
    path('lecturers/<int:pk>/reset-password/', views.lecturer_reset_password, name='lecturer_reset_password'),
    # Courses
    path('courses/',                views.course_list,       name='course_list'),
    path('courses/new/',            views.course_create,     name='course_create'),
    path('courses/<int:pk>/edit/',  views.course_edit,       name='course_edit'),
    path('courses/<int:pk>/review/', views.course_review,   name='course_review'),
    path('courses/<int:pk>/delete/', views.course_delete,   name='course_delete'),
    path('course-messages/',        views.course_message_list, name='course_message_list'),
    # Exams
    path('exams/',                  views.exam_list,         name='exam_list'),
    path('exams/<int:pk>/review/',  views.exam_review,              name='exam_review'),
    path('exams/<int:exam_pk>/reschedule/',        views.exam_reschedule_list,   name='exam_reschedule_list'),
    path('exams/<int:exam_pk>/reschedule/new/',    views.exam_reschedule_create, name='exam_reschedule_create'),
    path('exams/reschedule/<int:pk>/delete/',      views.exam_reschedule_delete, name='exam_reschedule_delete'),
    # Results
    path('results/',                views.result_list,       name='result_list'),
    path('results/export/',          views.result_export,        name='result_export'),
    path('results/<int:pk>/edit/',  views.result_edit,       name='result_edit'),
    path('results/sync/',           views.result_sync_all,   name='result_sync'),
    # Settings
    path('settings/',               views.academic_settings,     name='academic_settings'),
    # Departments
    path('departments/',               views.department_list,   name='department_list'),
    path('departments/new/',           views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_edit,   name='department_edit'),
    # Announcements
    path('announcements/',                    views.announcement_list,   name='announcement_list'),
    path('announcements/new/',                views.announcement_create, name='announcement_create'),
    path('announcements/<int:pk>/delete/',    views.announcement_delete, name='announcement_delete'),
    path('announcements/<int:pk>/toggle/',    views.announcement_toggle, name='announcement_toggle'),
]
