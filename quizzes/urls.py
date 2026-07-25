from django.urls import path
from . import views

app_name = 'quizzes'

urlpatterns = [
    path('<int:quiz_id>/',        views.quiz_detail,  name='quiz_detail'),
    path('<int:quiz_id>/submit/', views.submit_quiz,  name='submit_quiz'),
    path('result/<int:attempt_id>/', views.quiz_result, name='quiz_result'),
]
