from rest_framework import viewsets, permissions
from .models import PopulationHealth
from .serializers import PopulationHealthSerializer

class PopulationHealthViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PopulationHealth.objects.all().order_by('-date')
    serializer_class = PopulationHealthSerializer
    permission_classes = [permissions.IsAuthenticated]
