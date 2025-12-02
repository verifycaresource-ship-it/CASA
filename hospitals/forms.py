from django import forms
from .models import Hospital

class HospitalForm(forms.ModelForm):
    class Meta:
        model = Hospital
        fields = [
            'name', 'owner_first_name', 'owner_last_name', 'email',
            'currency', 'mobile', 'phone', 'address', 'city', 'country',
            'language', 'image', 'verified'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'owner_first_name': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'owner_last_name': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'email': forms.EmailInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'currency': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'mobile': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'phone': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'address': forms.Textarea(attrs={'class': 'w-full border px-3 py-2 rounded', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'country': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'language': forms.TextInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'image': forms.ClearableFileInput(attrs={'class': 'w-full border px-3 py-2 rounded'}),
            'verified': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }
