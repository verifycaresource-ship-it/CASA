from django.urls import path, include
from rest_framework import routers
from . import views
from django.conf import settings
from django.conf.urls.static import static
app_name = 'policies'

# DRF Router
router = routers.DefaultRouter()
router.register(r'policies', views.PolicyViewSet, basename='policy')

urlpatterns = [
    # Policy list & CRUD
    path('', views.policy_list, name='policy_list'),
    path('add/', views.policy_form, name='add_policy'),
    path('<int:pk>/edit/', views.policy_form, name='edit_policy'),
    path('<int:pk>/', views.policy_detail, name='policy_detail'),

    # Assign policy to hospital
    path('<int:pk>/assign-hospital/', views.assign_to_hospital, name='assign_to_hospital'),

    # Insured persons
    path('policy/<int:policy_id>/add-insured/', views.add_insured_person, name='add_insured_person'),
    path('insured/<int:person_id>/edit/', views.edit_insured_person, name='edit_insured_person'),
    path('insured/<int:person_id>/delete/', views.delete_insured_person, name='delete_insured_person'),

    # API routes
    path('api/', include(router.urls)),
    path('policy/<int:pk>/download/', views.download_policy_pdf, name='download_policy_pdf'),
    path('policy/<int:pk>/view/', views.view_policy_document, name='view_policy_document'),
    path('policy/<int:pk>/pdf/', views.view_policy_pdf, name='view_policy_pdf'),

]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
