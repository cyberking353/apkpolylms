from django.urls import path
from . import views

app_name = 'exams'

urlpatterns = [
    path('<int:exam_id>/',         views.exam_detail, name='exam_detail'),
    path('<int:exam_id>/start/',   views.start_exam,  name='start_exam'),
    path('<int:exam_id>/submit/',  views.submit_exam, name='submit_exam'),
    path('<int:exam_id>/heartbeat/',     views.exam_heartbeat, name='exam_heartbeat'),
    path('<int:exam_id>/log-violation/', views.log_violation,  name='log_violation'),
    path('result/<int:attempt_id>/', views.exam_result, name='exam_result'),
]
