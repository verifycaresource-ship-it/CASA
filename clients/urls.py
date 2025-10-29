from django.urls import path
from . import views

app_name = "clients"

urlpatterns = [
    path('', views.client_list, name='client_list'),
    path('add/', views.add_client, name='add_client'),
    path('<int:pk>/edit/', views.edit_client, name='edit_client'),
    path('<int:pk>/detail/', views.client_detail, name='client_detail'),
]