from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Chatbot, PDFStore
from django.forms import formset_factory

class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={"class": "form-control"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control"}))

class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'is_admin', 'is_user')

class ChatbotForm(forms.ModelForm):
    lead_mails = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter lead emails'})
    )

    class Meta:
        model = Chatbot
        fields = (
            'name', 'chatbot_tone', 'role_behavior', 'fallback_message', 
            'header_color', 'send_button_color', 'header_text', 'welcome_message', 
            'logo', 'conversation_behavior','business_info','faq'
        )
        widgets = {
            'header_color': forms.TextInput(attrs={'type': 'color'}),
            'send_button_color': forms.TextInput(attrs={'type': 'color'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['header_color'].required = False
        self.fields['send_button_color'].required = False
        self.fields['header_text'].required = False
        self.fields['welcome_message'].required = False
        self.fields['conversation_behavior'].required = False
        self.fields['logo'].required = False
        self.fields['business_info'].required = False
        self.fields['faq'].required= False

class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = PDFStore
        fields = ('documents',)

PDFUploadFormSet = formset_factory(PDFUploadForm, extra=1)

class ChatbotCustomizationForm(forms.ModelForm):
    class Meta:
        model = Chatbot
        fields = ('header_color', 'send_button_color', 'header_text', 'welcome_message', 'logo','we_are_here_image','chat_toggle_image','business_info','faq')
        widgets = {
            'header_color': forms.TextInput(attrs={'type': 'color'}),
            'send_button_color': forms.TextInput(attrs={'type': 'color'}),
        }





from django import forms
from .models import Category, Product

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'image', 'category', 'price', 'discount', 'video', 'useful_link']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)