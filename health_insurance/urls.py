from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from accounts.views import dashboard  # main dashboard

# =========================
# 🌐 DRF Routers
# =========================
router = routers.DefaultRouter()

# Import ViewSets
from clients.views import ClientViewSet
from policies.views import PolicyViewSet
from claims.views import ClaimViewSet
from hospitals.views import HospitalViewSet

# Register ViewSets for API
router.register(r'clients', ClientViewSet)
router.register(r'policies', PolicyViewSet)
router.register(r'claims', ClaimViewSet)
router.register(r'hospitals', HospitalViewSet)

# =========================
# 🌍 URL Patterns
# =========================
urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # Main dashboard
    path('', dashboard, name='main_dashboard'),       # root
    path('dashboard/', dashboard, name='dashboard'),  # /dashboard/

    # App URLs with namespaces
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('hospitals/', include(('hospitals.urls', 'hospitals'), namespace='hospitals')),
    path('clients/', include(('clients.urls', 'clients'), namespace='clients')),
    path('policies/', include(('policies.urls', 'policies'), namespace='policies')),
    path('claims/', include(('claims.urls', 'claims'), namespace='claims')),

    # REST API
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path("tasks/", include("tasks.urls")),

]

# =========================
# ⚙️ Serve Media in DEBUG
# =========================
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
