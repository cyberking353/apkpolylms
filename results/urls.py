from django.urls import path
from . import views
app_name = 'results'
urlpatterns = [
    path('my-results/', views.my_results, name='my_results'),
]
