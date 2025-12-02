from django import forms
from .models import Policy
import json

class PolicyForm(forms.ModelForm):
    coverage_details = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': '{"hospitalization":5000, "dental":2000}', 'rows':4}),
        help_text="Enter coverage in JSON format"
    )

    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    expiry_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Policy
        fields = [
            'client', 'policy_type', 'name', 'coverage_details',
            'premium', 'deductible', 'max_claim_limit', 'waiting_period_days',
            'start_date', 'expiry_date', 'is_active'
        ]

    def clean_coverage_details(self):
        data = self.cleaned_data['coverage_details']
        try:
            coverage = json.loads(data)
            if not isinstance(coverage, dict):
                raise forms.ValidationError("Coverage must be a valid JSON object.")
            return coverage
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for coverage details.")
