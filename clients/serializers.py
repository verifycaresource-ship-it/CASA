from rest_framework import serializers
from .models import Client

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "id", "first_name", "last_name", "phone", "email", "dob", "gender",
            "address", "photo", "fingerprint_verified", "status",
            "nric_or_passport", "registered_by", "agent", "created_at", "updated_at"
        ]
        read_only_fields = ["fingerprint_verified", "status", "created_at", "updated_at"]
