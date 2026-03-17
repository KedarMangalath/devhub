from django.urls import path
from .views import calculate

urlpatterns = [
    path('api/calculate', calculate, name='calculate'),
]