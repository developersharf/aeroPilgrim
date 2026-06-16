from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Search


GLASS_INPUT = 'glass-input w-full'


class SearchForm(forms.ModelForm):

    class Meta:
        model = Search

        fields = [
            'city_departure',
            'city_arrival',
            'stay_days',
            'timespan_to_search',
        ]

        widgets = {
            'city_departure': forms.Select(attrs={'class': GLASS_INPUT}),
            'city_arrival': forms.Select(attrs={'class': GLASS_INPUT}),
            'stay_days': forms.Select(attrs={'class': GLASS_INPUT}),
            'timespan_to_search': forms.Select(attrs={'class': GLASS_INPUT}),
        }


class RegistrationForm(UserCreationForm):
    """Custom registration form extending Django's UserCreationForm"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': GLASS_INPUT,
            'placeholder': 'Email',
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add glass UI classes to form fields
        self.fields['username'].widget.attrs.update({
            'class': GLASS_INPUT,
            'placeholder': 'Username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': GLASS_INPUT,
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': GLASS_INPUT,
            'placeholder': 'Confirm Password'
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    """Custom login form"""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': GLASS_INPUT,
            'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': GLASS_INPUT,
            'placeholder': 'Password'
        })
    )
