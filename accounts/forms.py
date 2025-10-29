# accounts/forms.py
from django import forms
from .models import User

# accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User


from django import forms
from .models import User

class AdminPasswordResetForm(forms.ModelForm):
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        label="New Password",
        help_text="Enter a strong password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput,
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = []  # we are not editing any model field directly

    def clean(self):
        cleaned_data = super().clean()
        pw1 = cleaned_data.get("new_password")
        pw2 = cleaned_data.get("confirm_password")
        if pw1 != pw2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class AgentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone = forms.CharField(max_length=20, required=True)
    dob = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    gender = forms.ChoiceField(choices=User._meta.get_field('gender').choices, required=True)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)
    daamiin = forms.CharField(max_length=150, required=True)
    profile_picture = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = [
            "username", "first_name", "last_name", "profile_picture",
            "phone", "dob", "gender", "address", "daamiin",
            "password1", "password2"
        ]

class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class':'input-field'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'password', 'phone', 'address', 'profile_picture']
        widgets = {
            'username': forms.TextInput(attrs={'class':'input-field'}),
            'email': forms.EmailInput(attrs={'class':'input-field'}),
            'role': forms.Select(attrs={'class':'input-field'}),
            'phone': forms.TextInput(attrs={'class':'input-field'}),
            'address': forms.Textarea(attrs={'class':'input-field', 'rows':3}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])  # hash password
        if commit:
            user.save()
        return user
