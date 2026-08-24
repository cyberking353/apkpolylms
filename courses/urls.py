from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    path('',                                    views.landing,       name='landing'),
    path('dashboard/',                          views.dashboard,     name='dashboard'),
    path('courses/',                            views.course_list,   name='course_list'),
    path('courses/<slug:slug>/',                views.course_detail, name='course_detail'),
    path('courses/<slug:course_slug>/lecture/<int:lecture_id>/', views.lecture_view, name='lecture'),

    # --- Course Messages (student ↔ lecturer support threads) ---
    path('messages/',                       views.message_list,           name='message_list'),
    path('courses/<slug:slug>/message/',    views.message_new,            name='message_new'),
    path('messages/<int:pk>/',              views.message_thread,         name='message_thread'),
    path('lecturer/messages/',              views.lecturer_message_list,  name='lecturer_message_list'),

    # --- Lecturer ---
    path('lecturer/',                                    views.lecturer_dashboard,      name='lecturer_dashboard'),
    path('lecturer/course/new/',                         views.lecturer_course_create,  name='lecturer_course_create'),
    path('lecturer/course/<slug:slug>/edit/',            views.lecturer_course_edit,    name='lecturer_course_edit'),
    path('lecturer/course/<slug:slug>/submit/',          views.lecturer_course_submit,  name='lecturer_course_submit'),
    path('lecturer/course/<slug:slug>/module/add/',      views.lecturer_module_create,  name='lecturer_module_create'),
    path('lecturer/course/<slug:slug>/module/<int:module_id>/edit/',    views.lecturer_module_edit,    name='lecturer_module_edit'),
    path('lecturer/course/<slug:slug>/module/<int:module_id>/delete/',  views.lecturer_module_delete,  name='lecturer_module_delete'),
    path('lecturer/course/<slug:slug>/module/<int:module_id>/lecture/add/', views.lecturer_lecture_create, name='lecturer_lecture_create'),
    path('lecturer/course/<slug:slug>/lecture/<int:lecture_id>/edit/',   views.lecturer_lecture_edit,   name='lecturer_lecture_edit'),
    path('lecturer/course/<slug:slug>/lecture/<int:lecture_id>/delete/', views.lecturer_lecture_delete, name='lecturer_lecture_delete'),
    path('lecturer/course/<slug:slug>/module/<int:module_id>/quiz/',        views.lecturer_quiz_create,   name='lecturer_quiz_create'),
    path('lecturer/course/<slug:slug>/quiz/<int:quiz_id>/manage/',          views.lecturer_quiz_manage,   name='lecturer_quiz_manage'),
    path('lecturer/course/<slug:slug>/quiz/<int:quiz_id>/question/add/',    views.lecturer_quiz_question_add,    name='lecturer_quiz_question_add'),
    path('lecturer/course/<slug:slug>/quiz/<int:quiz_id>/question/<int:question_id>/edit/',   views.lecturer_quiz_question_edit,   name='lecturer_quiz_question_edit'),
    path('lecturer/course/<slug:slug>/quiz/<int:quiz_id>/question/<int:question_id>/delete/', views.lecturer_quiz_question_delete, name='lecturer_quiz_question_delete'),
    path('lecturer/course/<slug:slug>/exam/',                               views.lecturer_exam_create,   name='lecturer_exam_create'),
    path('lecturer/course/<slug:slug>/exam/manage/',                        views.lecturer_exam_manage,   name='lecturer_exam_manage'),
    path('lecturer/course/<slug:slug>/preview/',                            views.lecturer_course_preview, name='lecturer_course_preview'),
    path('lecturer/course/<slug:slug>/preview/lecture/<int:lecture_id>/',   views.lecturer_lecture_preview, name='lecturer_lecture_preview'),
    path('lecturer/course/<slug:slug>/results/',                            views.lecturer_course_results, name='lecturer_course_results'),
    path('lecturer/course/<slug:slug>/progress/',                           views.lecturer_course_progress,     name='lecturer_course_progress'),
    path('lecturer/course/<slug:slug>/progress/nudge/<int:student_id>/',    views.lecturer_nudge_student,       name='lecturer_nudge_student'),
    path('lecturer/course/<slug:slug>/progress/nudge-all/',                 views.lecturer_nudge_all,           name='lecturer_nudge_all'),
    path('lecturer/course/<slug:slug>/progress/export/',                    views.lecturer_progress_export,     name='lecturer_progress_export'),
    path('lecturer/course/<slug:slug>/progress/<int:student_id>/',          views.lecturer_student_progress,    name='lecturer_student_progress'),
    path('lecturer/notifications/',                                          views.lecturer_notifications, name='lecturer_notifications'),
]
