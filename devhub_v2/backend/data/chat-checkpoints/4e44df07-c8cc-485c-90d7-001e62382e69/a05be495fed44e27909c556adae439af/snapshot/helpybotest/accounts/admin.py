from django.contrib import admin
from .models import User, Chatbot, PDFStore, ChatHistory

admin.site.register(User)
admin.site.register(Chatbot)
admin.site.register(PDFStore)
admin.site.register(ChatHistory)