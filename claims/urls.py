from django.urls import path
from . import views

app_name = "claims"

urlpatterns = [
    path('', views.claim_list, name='claim_list'),
    path('add/', views.add_claim, name='add_claim'),
    path('hospital-dashboard/', views.hospital_claim_dashboard, name='hospital_claim_dashboard'),
    path('<int:pk>/', views.claim_detail, name='claim_detail'),
    path('<int:pk>/edit/', views.edit_claim, name='edit_claim'),
    path('<int:pk>/approve/', views.approve_claim, name='approve_claim'),
    path('<int:pk>/reject/', views.reject_claim, name='reject_claim'),
    path('<int:pk>/reimburse/', views.reimburse_claim, name='reimburse_claim'),
    path("submit/assignment/<int:assignment_id>/", views.submit_claim_for_assignment, name="submit_claim_for_assignment"),

]
