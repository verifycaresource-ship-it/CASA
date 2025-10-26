from django.urls import path, include
from rest_framework import routers
from . import views

app_name = 'policies'

router = routers.DefaultRouter()
router.register(r'policies', views.PolicyViewSet, basename='policy')

urlpatterns = [
    path('', views.policy_list, name='policy_list'),
    path('add/', views.policy_form, name='add_policy'),
    path('<int:pk>/edit/', views.policy_form, name='edit_policy'),
    path('<int:pk>/', views.policy_detail, name='policy_detail'),
    path('<int:pk>/assign-hospital/', views.assign_to_hospital, name='assign_to_hospital'),
    path('api/', include(router.urls)),
    
]
