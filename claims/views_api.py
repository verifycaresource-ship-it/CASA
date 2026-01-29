from rest_framework import viewsets, permissions
from .models import PopulationHealth
from .serializers import PopulationHealthSerializer

class PopulationHealthViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PopulationHealth.objects.all().order_by('-date')
    serializer_class = PopulationHealthSerializer
    permission_classes = [permissions.IsAuthenticated]

# claims/views_api.py
from rest_framework import viewsets, permissions
from .models import Claim
from .serializers import ClaimSerializer

class ClaimViewSet(viewsets.ModelViewSet):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]
