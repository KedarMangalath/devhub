from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import JSONField
class User(AbstractUser):
    is_admin = models.BooleanField('Is admin', default=False)
    is_user = models.BooleanField('Is user', default=False)
    widget_script_url = models.CharField(max_length=255, blank=True, null=True)
    sample_html_url = models.CharField(max_length=255, blank=True, null=True)
    openai_api_key = models.CharField(max_length=255, blank=True, null=True)
    translation_enabled = models.BooleanField('Translation enabled', default=False)
    leads_enabled = models.BooleanField('Leads enabled', default=False)
    whatsapp_license_number = models.CharField(max_length=255, blank=True, null=True)
    whatsapp_api_key = models.CharField(max_length=255, blank=True, null=True)
    telegram_bot_token = models.CharField(max_length=255, blank=True, null=True)
    lead_mails = models.EmailField('Lead Mails', blank=True, null=True)
    
    whatsapp_appkey = models.CharField(max_length=255, blank=True, null=True)
    whatsapp_authkey = models.CharField(max_length=255, blank=True, null=True)
    
    
    def __str__(self):
        return self.username


from django.db import models

class Chatbot(models.Model):
    ROLE_BEHAVIOR_CHOICES = [
        ('friendly', 'Friendly'),
        ('professional', 'Professional'),
        ('customer_support', 'Customer Support'),
        ('Proactive Property Market Advisor - Matching Clients with Ideal Real Estate Solutions','Real Estate Professional'),
    ]
    
    TONE_CHOICES = [
        ('helpful chatbot', 'Helpful chatbot'),
        ('customer support agent', 'Customer Support Agent'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    custom_rules = models.TextField(blank=True, default="")
    chatbot_tone = models.CharField(max_length=100, choices=TONE_CHOICES, default='friendly')
    role_behavior = models.CharField(max_length=200, choices=ROLE_BEHAVIOR_CHOICES, default='friendly')
    web_app_info = models.TextField()
    conversation_behavior = models.TextField()
    fallback_message = models.TextField()
    header_color = models.CharField(max_length=7, default='#0b3d2c')
    send_button_color = models.CharField(max_length=7, default='#0b3d2c')
    header_text = models.CharField(max_length=100, default='Name')
    welcome_message = models.TextField(default="Welcome! How may I help you?")
    logo = models.ImageField(upload_to='chatbot_logos/', null=True, blank=True)
    we_are_here_image = models.ImageField(upload_to='chatbot_we_are_here/', null=True, blank=True)
    chat_toggle_image = models.ImageField(upload_to='chatbot_toggle_images/', null=True, blank=True)
    business_info = models.TextField(default="Business Information")
    faq = models.TextField(default="FAQ")
    
    def __str__(self):
        return f"{self.user.username}'s Chatbot"

class PDFStore(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE)
    documents = models.FileField(upload_to='pdfs/')
    
class ChatHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    content = models.JSONField()
    lead_name = models.CharField(max_length=255, blank=True, null=True)
    lead_phone = models.CharField(max_length=20, blank=True, null=True)
    lead_email = models.EmailField(blank=True, null=True)  # New field
    is_lead = models.BooleanField(default=False)
    chat_summary = models.TextField(blank=True, null=True)  
    property_selection = models.CharField(max_length=255, blank=True, null=True)
    budget_range = models.CharField(max_length=255, blank=True, null=True)  # New field for budget range
    # In models.py, add to ChatHistory
    user_selections = models.JSONField(null=True, blank=True)

    
    def __str__(self):
        if self.is_lead:
            return f"Lead: {self.lead_name} ({self.session_id})"
        return f"Chat History: {self.session_id}"
    
    class Meta:
        verbose_name_plural = "Chat Histories"
    
    
class WhatsAppConfig(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='whatsapp_config')
    license_number = models.CharField(max_length=255)
    api_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"WhatsApp Config for {self.user.username}"

class TelegramConfig(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='telegram_config')
    bot_token = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Telegram Config for {self.user.username}"
    
    

    
class Category(models.Model):
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Link to the user who created the category

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='products/')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # New field
    discount = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # New field
    video = models.URLField(null=True, blank=True)  # New field
    useful_link = models.URLField(null=True, blank=True)  # New field

    def __str__(self):
        return self.name
    

class ChatFlow(models.Model):
    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name='flows')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.chatbot.name}"
    
class FlowStep(models.Model):
    STEP_TYPES = [
        ('message', 'Bot Message'),
        ('buttons', 'Buttons')
    ]
    
    flow = models.ForeignKey(ChatFlow, on_delete=models.CASCADE, related_name='steps')
    step_type = models.CharField(max_length=20, choices=STEP_TYPES)
    message = models.TextField()
    order = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Step {self.order}: {self.step_type}"

class FlowButton(models.Model):
    step = models.ForeignKey(FlowStep, on_delete=models.CASCADE, related_name='buttons')
    label = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['order']
        
    def __str__(self):
        return self.label