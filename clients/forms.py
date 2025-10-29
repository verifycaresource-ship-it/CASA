from django import forms
from .models import Client

class ClientForm(forms.ModelForm):
    # Optional file input for web upload
    fingerprint_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".bin,.fpt"})
    )

    class Meta:
        model = Client
        fields = [
            "first_name",
            "last_name",
            "phone",
            "email",
            "dob",
            "gender",
            "address",
            "photo",
            # fingerprint_file is handled separately
        ]
        widgets = {
            "dob": forms.DateInput(attrs={"type": "date"}),
        }

    def save(self, commit=True):
        """Override save to handle fingerprint_file."""
        client = super().save(commit=False)
        fingerprint_file = self.cleaned_data.get("fingerprint_file")
        if fingerprint_file:
            client.fingerprint_data = fingerprint_file.read()
            client.fingerprint_verified = True  # placeholder
            client.status = "verified"
        else:
            if not client.status:
                client.status = "pending"
        if commit:
            client.save()
        return client