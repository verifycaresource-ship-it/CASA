from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "assigned_to", "status", "due_date", "week"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "class": "border rounded px-3 py-2 w-full"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "border rounded px-3 py-2 w-full"}),
            "title": forms.TextInput(attrs={"class": "border rounded px-3 py-2 w-full"}),
            "week": forms.NumberInput(attrs={"class": "border rounded px-3 py-2 w-full", "min": 1}),
        }
