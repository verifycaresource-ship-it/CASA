from django import forms
from .models import Client

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "first_name","last_name","phone","email","dob",
            "gender","address","photo"
        ]
        widgets = {
            "dob": forms.DateInput(attrs={"type":"date"})
        }
