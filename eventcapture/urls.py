from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('event/', views.event, name='event'),
]
