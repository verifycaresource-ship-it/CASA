from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "assigned_to",
            "priority",
            "status",
            "week",
            "due_date",
        ]

        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }
