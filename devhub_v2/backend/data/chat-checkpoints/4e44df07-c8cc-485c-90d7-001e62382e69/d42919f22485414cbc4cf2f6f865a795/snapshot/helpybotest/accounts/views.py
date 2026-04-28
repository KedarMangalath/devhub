import os
import json
import re
import uuid
import time
import logging
import shutil
from datetime import datetime

from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from django.utils import timezone


from django.http import Http404, JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

import PyPDF2
from dotenv import load_dotenv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.template.loader import render_to_string
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from django.urls import reverse
from django.contrib import messages

from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from requests import session
import requests

from django.db.models.functions import TruncDate, ExtractHour
from .models import TelegramConfig, User, Chatbot, PDFStore, ChatHistory, WhatsAppConfig
from .forms import PDFUploadFormSet,SignUpForm,LoginForm,ChatbotForm,PDFUploadForm,ChatbotCustomizationForm
from .chatbot_logic import process_query, rag_agent, RAGAgent
from .chatbot_logic import generate_chat_summary


logger = logging.getLogger(__name__)

CHAT_HISTORY_DIR = 'chat_histories'

if not os.path.exists(CHAT_HISTORY_DIR):
    os.makedirs(CHAT_HISTORY_DIR)
    
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")   

def generate_session_id():
    return str(uuid.uuid4())

def load_chat_history(user_id, session_id):
    file_path = os.path.join(CHAT_HISTORY_DIR, f'user_{user_id}_{session_id}.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return []

def save_chat_history(user_id, session_id, chat_history):
    file_path = os.path.join(CHAT_HISTORY_DIR, f'user_{user_id}_{session_id}.json')
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(chat_history, f)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def index(request):
    return render(request, 'index.html')






def generate_chat_widget(request, user):
    try:
        chatbot = Chatbot.objects.get(user=user)
    except Chatbot.DoesNotExist:
        chatbot = Chatbot.objects.create(
            user=user,
            name=f"{user.username}'s Chatbot",
            chatbot_tone='helpful chatbot',
            role_behavior='friendly',
            web_app_info='Default web app info',
            fallback_message="I'm sorry, I don't have an answer for that.",
            header_color='#0b3d2c',
            send_button_color='#0b3d2c',
            header_text='Chat',
            faq = 'FAQ',
            business_info='Business Information',
            welcome_message="Welcome! How may I help you?"
        )

    # Force HTTPS for media URLs only
    def make_https(url):
        return url.replace('http://', 'https://', 1) if url else ''

    logo_url = make_https(request.build_absolute_uri(chatbot.logo.url)) if chatbot.logo else ''
    chat_toggle_image_url = make_https(request.build_absolute_uri(chatbot.chat_toggle_image.url)) if chatbot.chat_toggle_image else ''
    we_are_here_url = make_https(request.build_absolute_uri(chatbot.we_are_here_image.url)) if chatbot.we_are_here_image else ''

    # Keep original chat response URL construction
    chat_response_url = f"https://{request.get_host()}{reverse('chat_response', args=[user.id])}"

    script_content = render_to_string('chat_widget_template.js', {
        'user_id': user.id,
        'chatbot_id': chatbot.id,
        'header_color': chatbot.header_color,
        'send_button_color': chatbot.send_button_color,
        'header_text': chatbot.header_text,
        'business_info': chatbot.business_info,
        'faq' : chatbot.faq,
        'welcome_message': chatbot.welcome_message,
        'logo_url': logo_url,
        'we_are_here_url': we_are_here_url,
        'chat_toggle_image_url': chat_toggle_image_url,
        'chat_response_url': chat_response_url,
        'translation_enabled': user.translation_enabled,
        'leads_enabled': user.leads_enabled
    })

    script_path = os.path.join(settings.MEDIA_ROOT, f'chat_widgets/user_{user.id}_widget.js')
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, 'w') as f:
        f.write(script_content)

    timestamp = int(datetime.now().timestamp())
    return f'/media/chat_widgets/user_{user.id}_widget.js?v={timestamp}'

# def generate_chat_widget(request, user):
#     try:
#         chatbot = Chatbot.objects.get(user=user)
#     except Chatbot.DoesNotExist:
#         # Create a new chatbot with default values if one doesn't exist
#         chatbot = Chatbot.objects.create(
#             user=user,
#             name=f"{user.username}'s Chatbot",
#             chatbot_tone='helpful chatbot',
#             role_behavior='friendly',
#             web_app_info='Default web app info',
#             fallback_message="I'm sorry, I don't have an answer for that.",
#             header_color='#0b3d2c',
#             send_button_color='#0b3d2c',
#             header_text='Chat',
#             faq = 'FAQ',
#             business_info='Business Information',
#             welcome_message="Welcome! How may I help you?"
#         )

#     logo_url = request.build_absolute_uri(chatbot.logo.url) if chatbot.logo else ''
#     we_are_here_url = request.build_absolute_uri(chatbot.we_are_here_image.url) if chatbot.we_are_here_image else ''
#     chat_toggle_image_url = request.build_absolute_uri(chatbot.chat_toggle_image.url) if chatbot.chat_toggle_image else ''
#     chat_response_url = request.build_absolute_uri(reverse('chat_response', args=[user.id]))
#     # chat_response_url = request.build_absolute_uri(reverse('chat_response', args=[user.id])).replace("http://", "https://")


#     script_content = render_to_string('chat_widget_template.js', {
#         'user_id': user.id,
#         'chatbot_id': chatbot.id,  # Add this line
#         'header_color': chatbot.header_color,
#         'send_button_color': chatbot.send_button_color,
#         'header_text': chatbot.header_text,
#         'business_info': chatbot.business_info,
#         'faq' : chatbot.faq,
#         'welcome_message': chatbot.welcome_message,
#         'logo_url': logo_url,
#         'we_are_here_url': we_are_here_url,
#         'chat_toggle_image_url': chat_toggle_image_url,
#         'chat_response_url': chat_response_url,
#         'translation_enabled': user.translation_enabled,
#         'leads_enabled': user.leads_enabled
        
        
        
#     })
    
#     script_path = os.path.join(settings.MEDIA_ROOT, f'chat_widgets/user_{user.id}_widget.js')
#     os.makedirs(os.path.dirname(script_path), exist_ok=True)
#     with open(script_path, 'w') as f:
#         f.write(script_content)

#     timestamp = int(datetime.now().timestamp())
#     return f'/media/chat_widgets/user_{user.id}_widget.js?v={timestamp}'



def generate_sample_html(user):
    html_content = render_to_string('sample_widget_page.html', {'user_id': user.id})
    html_path = os.path.join(settings.MEDIA_ROOT, f'sample_pages/user_{user.id}_sample.html')
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(html_content)
    return f'/media/sample_pages/user_{user.id}_sample.html'


# views.py

@login_required
@user_passes_test(lambda u: u.is_user)
def customize_chatbot(request):
    chatbot = get_object_or_404(Chatbot, user=request.user)
    if request.method == 'POST':
        form = ChatbotCustomizationForm(request.POST, request.FILES, instance=chatbot)
        if form.is_valid():
            chatbot = form.save(commit=False)
            
            # Handle logo upload
            if 'logo' in request.FILES:
                logo_file = request.FILES['logo']
                logger.info(f"Uploading logo: {logo_file.name}")
                logo_dir = os.path.join(settings.MEDIA_ROOT, 'chatbot_logos')
                os.makedirs(logo_dir, exist_ok=True)
                chatbot.logo = logo_file

            # Handle we_are_here_image upload
            if 'we_are_here_image' in request.FILES:
                image_file = request.FILES['we_are_here_image']
                logger.info(f"Uploading we_are_here_image: {image_file.name}")
                image_dir = os.path.join(settings.MEDIA_ROOT, 'chatbot_we_are_here')
                os.makedirs(image_dir, exist_ok=True)
                chatbot.we_are_here_image = image_file

            # Handle chat_toggle_image upload
            if 'chat_toggle_image' in request.FILES:
                toggle_image_file = request.FILES['chat_toggle_image']
                logger.info(f"Uploading chat_toggle_image: {toggle_image_file.name}")
                toggle_image_dir = os.path.join(settings.MEDIA_ROOT, 'chatbot_toggle_images')
                os.makedirs(toggle_image_dir, exist_ok=True)
                chatbot.chat_toggle_image = toggle_image_file

            chatbot.save()
            logger.info(f"Saved chatbot with logo path: {chatbot.logo.path if chatbot.logo else 'No logo'}")
            logger.info(f"Saved chatbot with image path: {chatbot.we_are_here_image.path if chatbot.we_are_here_image else 'No image'}")
            logger.info(f"Saved chatbot with toggle image path: {chatbot.chat_toggle_image.path if chatbot.chat_toggle_image else 'No toggle image'}")
            
            messages.success(request, 'Chatbot customization saved successfully.')
            return redirect('user_dashboard')
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ChatbotCustomizationForm(instance=chatbot)
    
    return render(request, 'customize_chatbot.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_user)
def register(request):
    msg = None
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.is_user:  # Only generate widget for regular users
                widget_script_url = generate_chat_widget(request, user)  # Pass both request and user
                sample_html_url = generate_sample_html(user)
                user.widget_script_url = widget_script_url
                user.sample_html_url = sample_html_url
                user.save()
            msg = 'user created'
            return redirect('login_view')
        else:
            msg = 'form is not valid'
    else:
        form = SignUpForm()
    return render(request, 'register.html', {'form': form, 'msg': msg})




@login_required
@user_passes_test(lambda u: u.is_user)
def userregister(request):
    msg = None
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.is_user:  # Only generate widget for regular users
                widget_script_url = generate_chat_widget(user)
                sample_html_url = generate_sample_html(user)
                user.widget_script_url = widget_script_url
                user.sample_html_url = sample_html_url
                user.save()
            msg = 'user created'
            return redirect('login_view')
        else:
            msg = 'form is not valid'
    else:
        form = SignUpForm()
    return render(request, 'registeruser.html', {'form': form, 'msg': msg})



def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None
    if request.method == 'POST':
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if user.is_admin:
                    return redirect('admin_dashboard')
                elif user.is_user:
                    return redirect('user_dashboard')
            else:
                msg = 'invalid credentials'
        else:
            msg = 'error validating form'
    return render(request, 'login.html', {'form': form, 'msg': msg})

@login_required
@user_passes_test(lambda u: u.is_admin)
def admin_dashboard(request):
    users = User.objects.filter(is_user=True).select_related()
    return render(request, 'admin_dashboard.html', {
        'users': users,
    })

@login_required
@user_passes_test(lambda u: u.is_user)
def user_dashboard(request):
    try:
        chatbot = Chatbot.objects.get(user=request.user)
        
        # Calculate date range for filtering
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get all chat histories for this user's chatbot
        chat_histories = ChatHistory.objects.filter(
            user=request.user,
            chatbot=chatbot,
            timestamp__gte=thirty_days_ago
        )

        # Calculate basic statistics
        # Get unique session IDs
        unique_sessions = chat_histories.values('session_id').distinct()
        total_sessions = unique_sessions.count()
        
        # Calculate total messages by session
        total_messages = 0
        processed_sessions = set()  # Keep track of processed sessions
        
        for session in unique_sessions:
            session_id = session['session_id']
            if session_id in processed_sessions:
                continue
                
            # Get the latest chat history for this session
            latest_chat = chat_histories.filter(
                session_id=session_id
            ).latest('timestamp')
            
            try:
                content = json.loads(latest_chat.content) if isinstance(latest_chat.content, str) else latest_chat.content
                message_count = sum(1 for msg in content 
                                  if isinstance(msg, dict) and 
                                  msg.get('role') in ['human', 'ai'])
                total_messages += message_count
                processed_sessions.add(session_id)
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                logger.error(f"Error processing chat history for session {session_id}: {str(e)}")
                continue

        # Calculate average messages per session
        avg_messages_per_session = round(total_messages / total_sessions if total_sessions > 0 else 0, 2)

        # Get daily chat statistics
        daily_chats = chat_histories.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('session_id', distinct=True)
        ).order_by('date')

        # Fill in missing dates with zero counts
        date_counts = {item['date']: item['count'] for item in daily_chats}
        all_dates = []
        current_date = thirty_days_ago.date()
        end_date = timezone.now().date()
        
        while current_date <= end_date:
            all_dates.append({
                'date': current_date.isoformat(),
                'count': date_counts.get(current_date, 0)
            })
            current_date += timedelta(days=1)

        # Get hourly distribution
        hourly_distribution = chat_histories.annotate(
            hour=ExtractHour('timestamp')
        ).values('hour').annotate(
            count=Count('session_id', distinct=True)  # Count distinct sessions per hour
        ).order_by('hour')

        # Fill in missing hours with zero counts
        hour_counts = {item['hour']: item['count'] for item in hourly_distribution}
        all_hours = [{'hour': hour, 'count': hour_counts.get(hour, 0)} for hour in range(24)]

        # Generate widget script tag and sample page URL
        timestamp = int(datetime.now().timestamp())
        widget_url = f"{request.build_absolute_uri(request.user.widget_script_url)}?v={timestamp}"
        script_tag = f'<script src="{widget_url}"></script>'
        sample_page_url = request.build_absolute_uri(request.user.sample_html_url)

        context = {
            'chatbot': chatbot,
            'total_chats': total_sessions,
            'total_messages': total_messages,
            'avg_messages_per_session': avg_messages_per_session,
            'daily_chats': all_dates,
            'hourly_distribution': all_hours,
            'script_tag': script_tag,
            'sample_page_url': sample_page_url,
        }

    except Chatbot.DoesNotExist:
        context = {
            'chatbot': None,
            'total_chats': 0,
            'total_messages': 0,
            'avg_messages_per_session': 0,
            'daily_chats': [],
            'hourly_distribution': [],
            'script_tag': '',
            'sample_page_url': '',
        }

    return render(request, 'user_dashboard.html', context)





@login_required
@user_passes_test(lambda u: u.is_user)
def create_or_update_chatbot(request):
    try:
        chatbot = Chatbot.objects.get(user=request.user)
    except Chatbot.DoesNotExist:
        chatbot = None

    if request.method == 'POST':
        form = ChatbotForm(request.POST, instance=chatbot)
        if form.is_valid():
            chatbot = form.save(commit=False)
            chatbot.user = request.user

            # If this is an update, preserve the existing web_app_info
            if chatbot.id:
                existing_chatbot = Chatbot.objects.get(id=chatbot.id)
                chatbot.web_app_info = existing_chatbot.web_app_info
            else:
                # For new chatbots, set a default value
                chatbot.web_app_info = ""  # or some default content

            # Set other default values
            if not chatbot.header_color:
                chatbot.header_color = "#0b3d2c"
            if not chatbot.send_button_color:
                chatbot.send_button_color = "#0b3d2c"
            if not chatbot.header_text:
                chatbot.header_text = "Name"
            if not chatbot.business_info:
                chatbot.business_info = "Business Information"
            if not chatbot.faq:
                chatbot.faq = "FAQ"
            if not chatbot.welcome_message:
                chatbot.welcome_message = "Welcome! How may I help you?"
            
            chatbot.save()

            lead_mails = request.POST.get('lead_mails')
            if lead_mails:
                request.user.lead_mails = lead_mails
                request.user.save()

            messages.success(request, 'Chatbot settings saved successfully.')
            return redirect('user_dashboard')
        else:
            messages.error(request, 'There was an error saving the chatbot settings.')
    else:
        initial_data = {
            'lead_mails': request.user.lead_mails,
        }
        form = ChatbotForm(instance=chatbot, initial=initial_data)

    return render(request, 'create_chatbot.html', {'form': form, 'chatbot': chatbot})




@login_required
@user_passes_test(lambda u: u.is_user)
def upload_pdf(request):
    if request.method == 'POST':
        formset = PDFUploadFormSet(request.POST, request.FILES)
        if formset.is_valid():
            chatbot, created = Chatbot.objects.get_or_create(user=request.user)
            for form in formset:
                if form.cleaned_data:
                    pdf_store = form.save(commit=False)
                    pdf_store.user = request.user
                    pdf_store.chatbot = chatbot
                    pdf_store.save()
                    
                    try:
                        file_path = pdf_store.documents.path
                        user_pdf_folder = os.path.join(rag_agent.base_pdf_folder, str(request.user.id))
                        if not os.path.exists(user_pdf_folder):
                            os.makedirs(user_pdf_folder)
                        
                        new_file_path = os.path.join(user_pdf_folder, os.path.basename(file_path))
                        shutil.copy2(file_path, new_file_path)
                        logger.info(f"PDF saved to user folder: {new_file_path}")
                        
                    except Exception as e:
                        logger.error(f"Error processing PDF: {str(e)}")
                        return render(request, 'upload_pdf.html', {'formset': formset, 'error': 'Error processing PDF'})
            
            messages.success(request, "PDFs uploaded successfully. Click 'Refresh Vector Store' to process them.")
            return redirect('upload_pdf')
    else:
        formset = PDFUploadFormSet()
    
    user_pdfs = PDFStore.objects.filter(user=request.user)
    return render(request, 'upload_pdf.html', {'formset': formset, 'user_pdfs': user_pdfs})



@csrf_exempt
def chat_response(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            query = data.get('query')
            session_id = data.get('session_id')
            is_new_session = data.get('is_new_session', False)
            logo_url = data.get('logo_url', '')

            if is_new_session or not session_id:
                session_id = generate_session_id()
                chat_history = []
            else:
                chat_history = load_chat_history(user_id, session_id)

            user = get_object_or_404(User, id=user_id)
            chatbot = get_object_or_404(Chatbot, user=user)

            # Process the response
            full_response = process_query(
                user_id=str(user_id),
                query=query,
                chat_history=chat_history,
                chatbot_role=chatbot.role_behavior,
                chatbot_tone='professional',
                fallback_message=chatbot.fallback_message,
                webapp_info=chatbot.web_app_info,
                conversation_behavior=chatbot.conversation_behavior,
                welcome_message=chatbot.welcome_message
            )

            cleaned_response = clean_response(full_response)
            client_ip = get_client_ip(request)

            # Create messages
            human_message = {
                "role": "human",
                "content": query,
                "timestamp": str(datetime.now()),
                "ip_address": client_ip
            }
            ai_message = {
                "role": "ai",
                "content": cleaned_response,
                "timestamp": str(datetime.now()),
                "ip_address": "chatbot"
            }

            # Update chat history
            chat_history.append(human_message)
            chat_history.append(ai_message)

            # Save chat history to file
            save_chat_history(user_id, session_id, chat_history)

            # Create new ChatHistory record for this message exchange
            ChatHistory.objects.create(
                user=user,
                chatbot=chatbot,
                session_id=session_id,
                content=chat_history,
                timestamp=datetime.now()
            )

            return JsonResponse({
                'response': cleaned_response,
                'session_id': session_id,
                'logo_url': logo_url,
                'chatbot_id': chatbot.id
            })

        except Exception as e:
            logger.error(f"Error in chat_response: {str(e)}")
            return JsonResponse({'error': 'An error occurred while processing your request'}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)




def cleanup_chat_history(chat_history):
    seen = set()
    cleaned_history = []
    
    for message in chat_history:
        # Create a unique identifier for each message using role and content
        message_id = (message.get('role'), message.get('content'))
        if message_id not in seen:
            seen.add(message_id)
            cleaned_history.append(message)
            
    return cleaned_history


def clean_response(response):
    response = re.sub(r'^(AI:|Human:)\s*', '', response, flags=re.IGNORECASE)
    response = re.sub(r'^Answer:\s*', '', response)
    response = re.sub(r'\nSources:.*', '', response, flags=re.DOTALL)
    return response.strip()

def logout_view(request):
    logout(request)
    return redirect('login_view')

@login_required
@user_passes_test(lambda u: u.is_user)
def chat_history(request):
    # Get chat histories for the specific user and their chatbot
    chatbot = get_object_or_404(Chatbot, user=request.user)
    chat_histories = ChatHistory.objects.filter(
        user=request.user,
        chatbot=chatbot
    ).order_by('-timestamp')
    
    # Prepare sessions data
    sessions = []
    for chat in chat_histories:
        content = json.loads(chat.content) if isinstance(chat.content, str) else chat.content
        if content:
            sessions.append({
                'session_id': chat.session_id,
                'timestamp': chat.timestamp
            })
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(sessions, 8)  # Show 8 sessions per page
    
    try:
        sessions = paginator.page(page)
    except PageNotAnInteger:
        sessions = paginator.page(1)
    except EmptyPage:
        sessions = paginator.page(paginator.num_pages)

    return render(request, 'chat_history.html', {
        'sessions': sessions
    })
    
@login_required
@user_passes_test(lambda u: u.is_user)
def session_chat_history(request, session_id):
    chatbot = get_object_or_404(Chatbot, user=request.user)
    
    # Get all chat histories for this session, ordered by timestamp
    chat_histories = ChatHistory.objects.filter(
        user=request.user,
        chatbot=chatbot,
        session_id=session_id
    ).order_by('timestamp')
    
    if not chat_histories.exists():
        raise Http404("Chat history not found")
    
    # Combine all messages and remove duplicates
    all_messages = []
    seen_messages = set()
    
    for chat_history in chat_histories:
        content = json.loads(chat_history.content) if isinstance(chat_history.content, str) else chat_history.content
        
        for message in content:
            # Create a unique identifier for each message
            message_content = message.get('content', '')
            message_role = message.get('role', '')
            message_identifier = f"{message_role}:{message_content}"
            
            if message_identifier not in seen_messages:
                if 'timestamp' not in message:
                    message['timestamp'] = chat_history.timestamp.isoformat()
                all_messages.append(message)
                seen_messages.add(message_identifier)
    
    # Sort messages by their timestamp
    all_messages.sort(key=lambda x: x.get('timestamp', ''))

    return render(request, 'session_chat_history.html', {
        'session_id': session_id,
        'all_messages': all_messages
    })
    
    

    
    
@login_required
@user_passes_test(lambda u: u.is_user)
def preview_chatbot(request):
    chatbot = Chatbot.objects.get(user=request.user)
    return render(request, 'preview_chatbot.html', {'chatbot': chatbot})

@login_required
@user_passes_test(lambda u: u.is_user)
def delete_pdf(request, pdf_id):
    pdf = get_object_or_404(PDFStore, id=pdf_id, user=request.user)
    if request.method == 'POST':
        user_pdf_folder = os.path.join(rag_agent.base_pdf_folder, str(request.user.id))
        file_path = os.path.join(user_pdf_folder, os.path.basename(pdf.documents.name))
        if os.path.exists(file_path):
            os.remove(file_path)
        
        pdf.delete()
        messages.success(request, "PDF deleted successfully.")
        return redirect('upload_pdf')
    return render(request, 'confirm_delete_pdf.html', {'pdf': pdf})

@login_required
@user_passes_test(lambda u: u.is_user)
def update_webapp_info(request):
    try:
        chatbot = Chatbot.objects.get(user=request.user)
    except Chatbot.DoesNotExist:
        messages.error(request, 'Please create a chatbot first.')
        return redirect('create_chatbot')

    if request.method == 'POST':
        web_app_info = request.POST.get('web_app_info')
        if web_app_info is not None:
            # Preserve the web_app_info update
            chatbot.web_app_info = web_app_info
            chatbot.save()
            messages.success(request, 'Training content updated successfully.')
            return redirect('user_dashboard')
        else:
            messages.error(request, 'No content provided.')

    return render(request, 'update_webapp_info.html', {'chatbot': chatbot})





# @login_required
@user_passes_test(lambda u: u.is_user)
def regenerate_widget(request):
    user = request.user
    widget_script_url = generate_chat_widget(request, user)  # Pass both request and user
    sample_html_url = generate_sample_html(user)
    user.widget_script_url = widget_script_url
    user.sample_html_url = sample_html_url
    user.save()
    
    # Add a success message
    messages.success(request, "Widget regenerated successfully. You may need to refresh the page to see the changes.")
    
    return redirect('user_dashboard')

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)



@login_required
@user_passes_test(lambda u: u.is_user)
def update_custom_rules(request):
    try:
        chatbot = Chatbot.objects.get(user=request.user)
    except Chatbot.DoesNotExist:
        chatbot = Chatbot.objects.create(user=request.user)

    if request.method == 'POST':
        custom_rules = request.POST.get('custom_rules')
        chatbot.custom_rules = custom_rules
        chatbot.save()
        return redirect('user_dashboard')

    return render(request, 'update_custom_rules.html', {'chatbot': chatbot})





@login_required
@user_passes_test(lambda u: u.is_admin)
def delete_user(request, user_id):
    if request.method == 'POST':
        user_to_delete = get_object_or_404(User, id=user_id, is_user=True)
        
        # Delete user's PDFs and vector store
        user_pdf_folder = os.path.join(rag_agent.base_pdf_folder, str(user_to_delete.id))
        user_vector_db_path = os.path.join(rag_agent.base_vector_db_path, f"user_{user_to_delete.id}")
        
        if os.path.exists(user_pdf_folder):
            shutil.rmtree(user_pdf_folder)
        
        if os.path.exists(user_vector_db_path):
            shutil.rmtree(user_vector_db_path)
        
        # Delete user's chatbot and chat history
        Chatbot.objects.filter(user=user_to_delete).delete()
        ChatHistory.objects.filter(user=user_to_delete).delete()
        
        # Delete the user
        user_to_delete.delete()
        
        messages.success(request, f"User {user_to_delete.username} has been deleted along with all associated data.")
    
    return redirect('admin_dashboard')



@login_required
@user_passes_test(lambda u: u.is_user)
def delete_vectorstore(request):
    if request.method == 'POST':
        user_id = str(request.user.id)
        user_vector_db_path = os.path.join(rag_agent.base_vector_db_path, f"user_{user_id}")
        logger.info(f"Attempting to delete vector store for user {user_id} at path: {user_vector_db_path}")

        if os.path.exists(user_vector_db_path):
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # List contents of the directory before deletion
                    logger.info(f"Contents of {user_vector_db_path} before deletion: {os.listdir(user_vector_db_path)}")
                    
                    shutil.rmtree(user_vector_db_path)
                    logger.info(f"Vector store deleted successfully for user {user_id}")
                    messages.success(request, "Vector store deleted successfully.")
                    break
                except PermissionError as pe:
                    logger.error(f"PermissionError on attempt {attempt + 1}: {str(pe)}")
                    if attempt < max_attempts - 1:
                        time.sleep(1)  # Wait for 1 second before retrying
                    else:
                        logger.error(f"Failed to delete vector store after {max_attempts} attempts")
                        messages.error(request, "Unable to delete vector store. It may be in use. Please try again later.")
                except Exception as e:
                    logger.error(f"Unexpected error while deleting vector store: {str(e)}")
                    messages.error(request, f"An error occurred while deleting the vector store: {str(e)}")
                    break

            if os.path.exists(user_vector_db_path):
                logger.warning(f"Vector store folder still exists after deletion attempt for user {user_id}")
                messages.warning(request, "Vector store folder could not be completely removed. Some files may still exist.")
            else:
                logger.info(f"Vector store folder successfully removed for user {user_id}")
        else:
            logger.info(f"Vector store does not exist for user {user_id}")
            messages.info(request, "Vector store does not exist.")

    return redirect('upload_pdf')


from django.shortcuts import render, redirect
from django.contrib import messages

from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.files.storage import default_storage
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback



@login_required
def refresh_vectorstore(request):
    user = request.user
    try:
        rag_agent = RAGAgent(base_pdf_folder="./user_docs", base_vector_db_path="./vector_store")
        user_vector_db_path = os.path.join(rag_agent.base_vector_db_path, f"user_{user.id}")

        # Load existing vector store
        vectorstore = Chroma(persist_directory=user_vector_db_path, embedding_function=rag_agent.embeddings)

        # Get all current PDFs for the user
        current_pdfs = PDFStore.objects.filter(user=user)

        # Get existing document sources
        existing_sources = set(metadata['source'] for metadata in vectorstore.get()['metadatas'])

        # Function to process a single PDF
        def process_pdf(pdf):
            try:
                if pdf.documents.name not in existing_sources:
                    file_path = default_storage.path(pdf.documents.name)
                    documents = rag_agent.load_pdf_documents(file_path)
                    category = rag_agent.categorize_document(documents, pdf.documents.name)
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000,
                        chunk_overlap=200,
                        separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
                    )
                    texts = text_splitter.split_text("\n\n".join(documents))
                    metadatas = [{"source": pdf.documents.name, "category": category}] * len(texts)
                    
                    vectorstore.add_texts(texts, metadatas=metadatas)
                    return f"Processed {pdf.documents.name} (Category: {category})"
                return f"Skipped {pdf.documents.name} (already in vector store)"
            except Exception as e:
                return f"Error processing {pdf.documents.name}: {str(e)}"

        # Process PDFs in parallel
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_pdf = {executor.submit(process_pdf, pdf): pdf for pdf in current_pdfs}
            for future in as_completed(future_to_pdf):
                results.append(future.result())

        # Remove embeddings for deleted PDFs
        current_pdf_names = set(pdf.documents.name for pdf in current_pdfs)
        for old_source in existing_sources - current_pdf_names:
            ids_to_delete = [id for id, metadata in zip(vectorstore.get()['ids'], vectorstore.get()['metadatas']) if metadata['source'] == old_source]
            if ids_to_delete:
                vectorstore.delete(ids=ids_to_delete)
                results.append(f"Removed embeddings for {old_source}")

        # Persist changes
        vectorstore.persist()

        # Summarize results
        success_count = sum(1 for r in results if not r.startswith("Error"))
        error_count = len(results) - success_count
        
        if error_count == 0:
            messages.success(request, f"Vector store successfully refreshed. Processed {success_count} PDFs.")
        else:
            messages.warning(request, f"Vector store refreshed with some issues. Processed {success_count} PDFs, encountered {error_count} errors.")
        
        # Log detailed results
        for result in results:
            if result.startswith("Error"):
                messages.error(request, result)
            else:
                messages.info(request, result)

    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        messages.error(request, traceback.format_exc())

    return redirect('upload_pdf')



@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_user)
def delete_logo(request):
    if request.method == 'POST':
        chatbot = get_object_or_404(Chatbot, user=request.user)
        if chatbot.logo:
            chatbot.logo.delete(save=True)
            return JsonResponse({'success': True})
        return JsonResponse({'success': False})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_user)
def delete_we_are_here_image(request):
    if request.method == 'POST':
        chatbot = get_object_or_404(Chatbot, user=request.user)
        if chatbot.we_are_here_image:
            chatbot.we_are_here_image.delete(save=True)
            return JsonResponse({'success': True})
        return JsonResponse({'success': False})
    return JsonResponse({'error': 'Invalid request'}, status=400)



@login_required
@user_passes_test(lambda u: u.is_admin)
def update_api_key(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            api_key = data.get('api_key')
            widget_script_url = data.get('widget_script_url')
            sample_html_url = data.get('sample_html_url')
            
            user = User.objects.get(id=user_id)
            
            if api_key is not None:
                user.openai_api_key = api_key
            if widget_script_url is not None:
                user.widget_script_url = widget_script_url
            if sample_html_url is not None:
                user.sample_html_url = sample_html_url
                
            user.save()

            if widget_script_url is not None or sample_html_url is not None:
                widget_script_url = generate_chat_widget(request, user)
                sample_html_url = generate_sample_html(user)
                user.widget_script_url = widget_script_url
                user.sample_html_url = sample_html_url
                user.save()
            
            return JsonResponse({
                'success': True, 
                'widget_script_url': user.widget_script_url,
                'sample_html_url': user.sample_html_url
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods

@ensure_csrf_cookie
# @login_required
@user_passes_test(lambda u: u.is_admin)
@require_http_methods(["POST"])
def toggle_translation(request, user_id):
    try:
        # Verify AJAX request
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            raise PermissionDenied
            
        # Parse JSON data
        try:
            data = json.loads(request.body)
            translation_enabled = data.get('translation_enabled')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)

        # Get and update user
        try:
            user = User.objects.get(id=user_id, is_user=True)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

        user.translation_enabled = translation_enabled
        user.save()

        # Regenerate widget
        widget_script_url = generate_chat_widget(request, user)
        user.widget_script_url = widget_script_url
        user.save()

        return JsonResponse({
            'success': True,
            'translation_enabled': user.translation_enabled,
            'widget_script_url': widget_script_url
        })

    except PermissionDenied:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required
@user_passes_test(lambda u: u.is_admin)
def update_whatsapp_license(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            license_number = data.get('whatsapp_license')
            
            user = User.objects.get(id=user_id)
            
            # Update both User model and WhatsAppConfig
            user.whatsapp_license_number = license_number
            user.save()
            
            # Update or create WhatsAppConfig
            whatsapp_config, created = WhatsAppConfig.objects.get_or_create(
                user=user,
                defaults={
                    'license_number': license_number,
                    'api_key': user.whatsapp_api_key or ''
                }
            )
            if not created:
                whatsapp_config.license_number = license_number
                whatsapp_config.save()
            
            return JsonResponse({
                'success': True,
                'whatsapp_license': license_number
            })
        except Exception as e:
            logger.error(f"Error updating WhatsApp license: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})



@login_required
@user_passes_test(lambda u: u.is_admin)
def update_whatsapp_api_key(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            api_key = data.get('whatsapp_api_key')
            
            user = User.objects.get(id=user_id)
            
            # Update both User model and WhatsAppConfig
            user.whatsapp_api_key = api_key
            user.save()
            
            # Update or create WhatsAppConfig
            whatsapp_config, created = WhatsAppConfig.objects.get_or_create(
                user=user,
                defaults={
                    'api_key': api_key,
                    'license_number': user.whatsapp_license_number or ''
                }
            )
            if not created:
                whatsapp_config.api_key = api_key
                whatsapp_config.save()
            
            return JsonResponse({
                'success': True,
                'whatsapp_api_key': api_key  # Return the value back
            })
        except Exception as e:
            logger.error(f"Error updating WhatsApp API key: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@user_passes_test(lambda u: u.is_admin)
def update_telegram_token(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            bot_token = data.get('telegram_bot_token')
            
            user = User.objects.get(id=user_id)
            user.telegram_bot_token = bot_token
            user.save()
            
            return JsonResponse({
                'success': True,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})





User = get_user_model()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a session with retries
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.1)
session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20))

def get_user_credentials(user_id):
    try:
        user = User.objects.get(id=user_id, is_user=True)
        # Make sure we're fetching the right credentials
        if not user.whatsapp_appkey or not user.whatsapp_authkey:
            raise ValueError("User is missing required WhatsApp credentials")
        return {
            'whatsapp_appkey': user.whatsapp_appkey,
            'whatsapp_authkey': user.whatsapp_authkey,
            'telegram_token': user.telegram_bot_token
        }
    except User.DoesNotExist:
        raise ValueError("User not found or not authorized")







from django.core.cache import cache
from django.shortcuts import get_object_or_404
import json
import requests
import logging

logger = logging.getLogger(__name__)

def process_whatsapp_message(request, user_id):
    """
    Process incoming WhatsApp messages and return chatbot response via WhatsApp API.
    Handles multiple payload formats and prevents duplicate message processing.
    """
    try:
        # 1. Get User and Validate Credentials
        user = get_object_or_404(User, id=user_id)
        appkey = user.whatsapp_appkey
        authkey = user.whatsapp_authkey

        if not appkey or not authkey:
            logger.error("WhatsApp credentials missing for user %s", user_id)
            raise ValueError("WhatsApp credentials not configured")

        # 2. Parse and Validate Payload
        try:
            payload = json.loads(request.body.decode('utf-8'))
            logger.debug("Raw payload:\n%s", json.dumps(payload, indent=2))
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload received")
            return {"status": "error", "message": "Invalid JSON format"}

        # 3. Extract Message ID for Deduplication
        message_id = None
        if 'messages' in payload:
            message_id = payload['messages'][0].get('id')
        elif 'entry' in payload:
            message_id = payload['entry'][0]['changes'][0]['value']['messages'][0].get('id')
        elif 'payload' in payload:
            message_id = payload['payload'].get('id')

        # 4. Check for Duplicate Message
        if message_id:
            cache_key = f"whatsapp_msg_{message_id}"
            if cache.get(cache_key):
                logger.warning("Duplicate message detected, ignoring ID: %s", message_id)
                return {"status": "ignored", "message": "Duplicate message"}
            cache.set(cache_key, True, timeout=86400)  # Cache for 24 hours

        # 5. Handle Different WhatsApp Payload Formats
        message = None
        contact_number = None
        
        # Format 1: Qubez API format
        if 'messages' in payload:
            message = payload['messages'][0]
            contact_number = message.get('from')
            logger.info("Processing Qubez format payload")

        # Format 2: WhatsApp Business API format
        elif 'entry' in payload:
            entry = payload['entry'][0]['changes'][0]['value']
            message = entry['messages'][0]
            contact_number = message.get('from')
            logger.info("Processing WhatsApp Business API format")

        # Format 3: New observed format (payload/sender/receiver)
        elif all(key in payload for key in ['payload', 'sender', 'receiver']):
            message = payload['payload']
            contact_number = payload['sender']
            logger.info("Processing new payload/sender/receiver format")
            
            # Normalize message structure
            if 'text' not in message:
                message['text'] = {'body': message.get('body', '')}
            if 'type' not in message:
                message['type'] = 'text'

        else:
            logger.error("Unrecognized payload format. Keys: %s", payload.keys())
            return {"status": "error", "message": f"Unsupported payload format. Received keys: {list(payload.keys())}"}

        # 6. Validate Message Contents
        if not message:
            logger.error("Empty message in payload")
            return {"status": "error", "message": "No message found in payload"}

        if message.get('type') != 'text':
            logger.warning("Non-text message received: %s", message.get('type'))
            return {"status": "ignored", "message": "Non-text message"}

        # 7. Extract Message Details
        try:
            user_message = message['text']['body']
            if not contact_number:
                contact_number = message.get('from') or payload.get('sender')
                
            logger.info("Processing message from %s: %s", contact_number, user_message)
        except KeyError as e:
            logger.error("Missing required field: %s", str(e))
            return {"status": "error", "message": f"Missing required field: {str(e)}"}

        # 8. Call Chatbot Service
        chatbot_url = f"{request.scheme}://{request.get_host()}/chat/response/{user_id}/"
        
        try:
            chatbot_response = requests.post(
                chatbot_url,
                json={
                    "query": user_message,
                    "session_id": contact_number,
                    "is_new_session": False
                },
                timeout=15
            )
            chatbot_response.raise_for_status()
            
            # Handle empty responses
            if not chatbot_response.content:
                raise ValueError("Empty response from chatbot")
                
            chatbot_data = chatbot_response.json()
            bot_message = chatbot_data.get('response', 'I could not process your message.')
            logger.debug("Chatbot response: %s", bot_message)

        except requests.exceptions.RequestException as e:
            logger.error("Chatbot API failure: %s", str(e))
            bot_message = "Sorry, I'm having trouble connecting to the service."
        except json.JSONDecodeError:
            logger.error("Invalid JSON from chatbot: %s", chatbot_response.text)
            bot_message = "Service response format error"

        # 9. Send WhatsApp Reply
        try:
            whatsapp_response = requests.post(
                "https://wa.qubez.in/api/create-message",
                data={
                    'appkey': appkey,
                    'authkey': authkey,
                    'to': contact_number,
                    'message': bot_message,
                },
                timeout=15
            )
            whatsapp_response.raise_for_status()
            
            logger.info("WhatsApp delivery success: %s", whatsapp_response.json())
            return {
                "status": "success",
                "chatbot_response": bot_message,
                "whatsapp_status": whatsapp_response.json()
            }

        except requests.exceptions.RequestException as e:
            logger.error("WhatsApp API failure: %s", str(e))
            return {
                "status": "error",
                "message": "Failed to deliver message",
                "error": str(e),
                "chatbot_response": bot_message
            }

    except Exception as e:
        logger.critical("Unhandled exception: %s", str(e), exc_info=True)
        return {
            "status": "error",
            "message": "Internal server error",
            "error": str(e)
        }

    
@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_admin)
def update_whatsapp_appkey(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            appkey = data.get('whatsapp_appkey')
            
            user = User.objects.get(id=user_id)
            user.whatsapp_appkey = appkey
            user.save()
            
            return JsonResponse({
                'success': True,
                'whatsapp_appkey': appkey
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_admin)
def update_whatsapp_authkey(request, user_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            authkey = data.get('whatsapp_authkey')
            
            user = User.objects.get(id=user_id)
            user.whatsapp_authkey = authkey
            user.save()
            
            return JsonResponse({
                'success': True,
                'whatsapp_authkey': authkey
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method'}) 


def process_telegram_message(request, user_id):
    try:
        # Get credentials for specific user
        credentials = get_user_credentials(user_id)
        TELEGRAM_BOT_TOKEN = credentials['telegram_token']
        TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

        # Build dynamic chatbot URL
        current_site = request.get_host()
        scheme = request.scheme
        chatbot_url = f"{scheme}://{current_site}/chat/response/{user_id}/"

        data = json.loads(request.body.decode('utf-8'))

        if 'message' not in data:
            raise ValueError("No message found in Telegram update")

        telegram_message = data['message']
        user_message = telegram_message.get('text', '')
        contact = str(telegram_message['from']['id'])

        if not user_message or not contact:
            raise ValueError(f"Missing required fields. Message: {user_message}, Contact: {contact}")

        chatbot_response = session.post(
            chatbot_url,
            json={
                "query": user_message,
                "session_id": contact,
                "is_new_session": False
            },
            timeout=10
        ).json()
        
        bot_message = chatbot_response.get('response', 'Sorry, I could not process your message')
        
        telegram_response = session.post(
            f"{TELEGRAM_API_BASE}/sendMessage",
            json={
                "chat_id": contact,
                "text": bot_message
            },
            timeout=10
        )
        
        return {
            "status": "success",
            "chatbot_message": bot_message,
            "telegram_status": telegram_response.json()
        }
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise e


@csrf_exempt
@require_http_methods(["GET", "POST"])
def handle_whatsapp_webhook(request, user_id):
    if request.method == 'GET':
        return HttpResponse("Webhook active!")
    
    result = process_whatsapp_message(request, user_id)
    return JsonResponse(result)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def handle_telegram_webhook(request, user_id):
    if request.method == 'GET':
        return HttpResponse("Telegram webhook server is running!")
    
    try:
        result = process_telegram_message(request, user_id)
        return JsonResponse(result)
    except ValueError as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=401)
    except requests.exceptions.Timeout:
        return JsonResponse({
            "status": "error",
            "message": "Request timed out"
        }, status=504)
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            "status": "error",
            "message": f"Network error: {str(e)}"
        }, status=502)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def test_message(request, user_id):
    try:
        data = json.loads(request.body)
        if not data or 'message' not in data or 'contact' not in data:
            return JsonResponse({
                "status": "error",
                "message": "Please provide both 'message' and 'contact' in the request body"
            }, status=400)
            
        result = process_whatsapp_message(request, user_id)
        return JsonResponse(result)
        
    except ValueError as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=401)
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
        

@csrf_exempt
@csrf_exempt
def save_lead(request, chatbot_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            phone = data.get('phone')
            email = data.get('email', '')
            session_id = data.get('session_id')
            property_selection = data.get('property_selection', '')
            budget_range = data.get('budget_range', '')
            user_selections = data.get('user_selections', {})  # Get all user selections

            if not all([name, phone, session_id]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                }, status=400)

            chatbot = get_object_or_404(Chatbot, id=chatbot_id)
            user = chatbot.user

            # Find all ChatHistory records for this session
            chat_histories = ChatHistory.objects.filter(
                chatbot=chatbot,
                session_id=session_id
            ).order_by('timestamp')

            # Update all chat histories with lead and property information
            chat_histories.update(
                lead_name=name,
                lead_phone=phone,
                lead_email=email,
                is_lead=True,
                property_selection=property_selection,
                budget_range=budget_range,
                user_selections=user_selections  # Store all user selections
            )

            # Add lead collection message to the latest chat history
            latest_chat = chat_histories.latest('timestamp')
            current_content = latest_chat.content if isinstance(latest_chat.content, list) else []

            lead_message = {
                "role": "system",
                "content": f"Lead collected - Name: {name}, Phone: {phone}, Email: {email}",
                "timestamp": str(datetime.now())
            }

            if not any(msg.get('content', '').startswith('Lead collected') for msg in current_content):
                current_content.append(lead_message)
                latest_chat.content = current_content
                latest_chat.save()

            # Send email
            send_email_to_fixed_address(name, phone, email, user, property_selection, budget_range)

            return JsonResponse({
                'success': True,
                'message': 'Lead information saved successfully',
                'chat_history_id': latest_chat.id
            })

        except Exception as e:
            logger.error(f"Error saving lead: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)

@login_required
@user_passes_test(lambda u: u.is_user)
def leads(request):
    # Get all leads for the user
    lead_list = ChatHistory.objects.filter(
        user=request.user,
        is_lead=True,
        lead_phone__isnull=False
    ).order_by('-timestamp')
    
    # Extract all unique questions from user selections
    questions = set()
    processed_leads = []
    
    for lead in lead_list:
        # Process lead data
        lead_data = lead.__dict__.copy()  # Copy all lead attributes
        
        # Process user selections to extract answers
        formatted_answers = []
        selections = lead.user_selections
        
        if selections:
            # Handle string serialized JSON if needed
            if isinstance(selections, str):
                try:
                    selections = json.loads(selections)
                except json.JSONDecodeError:
                    selections = {}
            
            # Extract all unique questions
            questions.update(selections.keys())
            
            # Store answers in order for template access
            for question in sorted(list(questions)):
                answer = "-"
                if question in selections:
                    answer_data = selections[question]
                    if isinstance(answer_data, dict) and 'label' in answer_data:
                        answer = answer_data['label']
                    else:
                        answer = str(answer_data)
                formatted_answers.append(answer)
        
        # Add formatted answers to the lead data
        lead_data['formatted_answers'] = formatted_answers
        processed_leads.append(lead_data)
    
    # Convert questions to sorted list
    questions = sorted(list(questions))
    
    # Set up pagination
    paginator = Paginator(processed_leads, 8)  # Show 8 leads per page
    page = request.GET.get('page')
    
    try:
        leads = paginator.page(page)
    except PageNotAnInteger:
        leads = paginator.page(1)
    except EmptyPage:
        leads = paginator.page(paginator.num_pages)
    
    return render(request, 'leads.html', {
        'leads': leads,
        'questions': questions
    })


@login_required
def lead_detail(request, chat_history_id):
    chat_history = get_object_or_404(
        ChatHistory, 
        id=chat_history_id, 
        user=request.user,
        is_lead=True
    )
    data = {
        'name': chat_history.lead_name,
        'phone': chat_history.lead_phone,
        'chatbot_name': chat_history.chatbot.name,
        'session_id': chat_history.session_id,
        'timestamp': chat_history.timestamp.strftime('%B %d, %Y %H:%M'),
        'conversation': chat_history.content
    }
    return JsonResponse(data)


@login_required
@user_passes_test(lambda u: u.is_admin)
@require_http_methods(["POST"])
def toggle_leads(request, user_id):
    try:
        data = json.loads(request.body)
        leads_enabled = data.get('leads_enabled')
        user = User.objects.get(id=user_id, is_user=True)
        user.leads_enabled = leads_enabled
        user.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_user)
def delete_chat_toggle_image(request):
    if request.method == 'POST':
        chatbot = get_object_or_404(Chatbot, user=request.user)
        if chatbot.chat_toggle_image:
            chatbot.chat_toggle_image.delete(save=True)
            return JsonResponse({'success': True})
        return JsonResponse({'success': False})
    return JsonResponse({'error': 'Invalid request'}, status=400)


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email_to_fixed_address(name, phone, email, user, property_selection, budget_range):
    sender_email = 'vinv8321@gmail.com'
    sender_password = 'iwdg xsuh uzym jwgw'  
    recipient_email = user.lead_mails

    try:
        subject = "New Lead Added"

        # HTML Template for the email body
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #ffffff;
                    margin: 0;
                    padding: 0;
                }}
                .header {{
                    background-color: #032c66;
                    color: #ffffff;
                    padding: 20px;
                    text-align: center;
                }}
                .header img {{
                    max-height: 50px;
                    vertical-align: middle;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }}
                h1 {{
                    color: #333333;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th, td {{
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f4f4f4;
                    color: #333333;
                }}
                .footer {{
                    border-top: 1px solid #ddd;
                    padding-top: 20px;
                    margin-top: 20px;
                    text-align: center;
                    color: #555555;
                }}
                .footer a {{
                    color: #032c66;
                    text-decoration: none;
                }}
                .footer a:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <img src="https://github.com/traromal/Aromal_TR/blob/main/helpybo.jpg?raw=true" alt="Helpybo Logo">
            </div>
            <div class="container">
                <h1>New Lead Added</h1>
                <table>
                    <tr>
                        <th>Field</th>
                        <th>Details</th>
                    </tr>
                    <tr>
                        <td><strong>Name</strong></td>
                        <td>{name}</td>
                    </tr>
                    <tr>
                        <td><strong>Phone</strong></td>
                        <td>{phone}</td>
                    </tr>
                    <tr>
                        <td><strong>Email</strong></td>
                        <td>{email}</td>
                    </tr>
                    <tr>
                        <td><strong>Property Selection</strong></td>
                        <td>{property_selection}</td>
                    </tr>
                    <tr>
                        <td><strong>Budget Range</strong></td>
                        <td>{budget_range}</td>
                    </tr>
                </table>
            </div>
            <div class="footer">
                <small>Powered by <a href="https://helpybo.com" target="_blank">Helpybo AI Engine</a></small>
            </div>
        </body>
        </html>
        """

        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach the HTML body to the email
        msg.attach(MIMEText(html_template, 'html'))

        # Use smtplib to send the email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)

        print(f"Email sent successfully to {recipient_email}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")



@login_required
@user_passes_test(lambda u: u.is_user)
@require_http_methods(["POST"])
def delete_lead(request, lead_id):
    try:
        lead = ChatHistory.objects.get(
            id=lead_id,
            user=request.user,
            is_lead=True
        )
        lead.delete()
        return JsonResponse({'success': True})
    except ChatHistory.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Lead not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def generate_summary(request, session_id):
    chat_history = get_object_or_404(ChatHistory, session_id=session_id)
    content = chat_history.content
    if isinstance(content, str):
        content = json.loads(content)
    
    # Generate the summary
    summary = generate_chat_summary(content)
    
    # Classify the chat summary into Hot, Warm, or Cold
    classification = classify_chat_summary(content)
    
    # Render the summary in a new page
    return render(request, 'summary.html', {
        'summary': summary,
        'session_id': session_id,
        'classification': classification,
    })

def classify_chat_summary(chat_content):
    """
    Classify the chat summary into Hot, Warm, or Cold based on the conversation.
    """
    # Example logic for classification:
    # - If the user mentions "interested", "buy", or "purchase", classify as Hot.
    # - If the user mentions "maybe", "later", or "interested in future", classify as Warm.
    # - Otherwise, classify as Cold.
    hot_keywords = ["interested", "buy", "purchase", "ready", "yes", "definitely"]
    warm_keywords = ["maybe", "later", "interested in future", "not now", "soon"]
    
    # Flatten the chat content into a single string for keyword matching
    chat_text = " ".join([msg.get("content", "").lower() for msg in chat_content])
    
    # Check for keywords
    if any(keyword in chat_text for keyword in hot_keywords):
        return "Hot"
    elif any(keyword in chat_text for keyword in warm_keywords):
        return "Warm"
    else:
        return "Cold"
    


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Category, Product
from .forms import CategoryForm, ProductForm
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from io import BytesIO

from django.http import JsonResponse

from django.http import JsonResponse

@login_required
@user_passes_test(lambda u: u.is_user)
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            
            # Return JSON response for AJAX requests
            return JsonResponse({
                'success': True,
                'category_id': category.id,
                'category_name': category.name
            })
        else:
            # Return JSON response with errors
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    else:
        form = CategoryForm()
    return render(request, 'add_category.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_user)
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.save()
            messages.success(request, 'Product added successfully.')
            return redirect('view_products')
    else:
        form = ProductForm(user=request.user)
    return render(request, 'add_product.html', {'form': form})

from django.core.paginator import Paginator
from django.shortcuts import render

@login_required
@user_passes_test(lambda u: u.is_user)
def view_products(request):  # Assuming this is your view function
    products_list = Product.objects.filter(user=request.user)
    paginator = Paginator(products_list, 8)  # Show 10 products per page
    
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)
    
    return render(request, 'view_products.html', {'products': products})






from django.http import HttpResponse
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.units import inch


@login_required
@user_passes_test(lambda u: u.is_user)
def download_products_pdf(request):
    products = Product.objects.filter(user=request.user)
    
    # Create a PDF buffer
    buffer = BytesIO()
    
    # Create the PDF object, using the buffer as its "file."
    pdf = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    # Create a list to hold the PDF content
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    body_style = styles['BodyText']
    
    # Add a title to the PDF
    title = Paragraph("", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))  # Add space after the title
    
    # Loop through products and add them to the PDF
    for index, product in enumerate(products, start=1):
        # Add product heading
        product_heading = Paragraph(f"{index}: {product.name}", heading_style)
        elements.append(product_heading)
        elements.append(Spacer(1, 6))  # Add space after the heading
        
        # Add product details
        details = [
            f"<b>Description:</b> {product.description}",
            f"<b>Category:</b> {product.category.name}",
            f"<b>Price:</b> ₹{product.price}" if product.price else "<b>Price:</b> N/A",
            f"<b>Discount:</b> {product.discount}%" if product.discount else "<b>Discount:</b> N/A",
            f"<b>Video:</b> {product.video}" if product.video else "<b>Video:</b> N/A",
            f"<b>Useful Link:</b> {product.useful_link}" if product.useful_link else "<b>Useful Link:</b> N/A",
            f"<b>Image URL:</b> {request.build_absolute_uri(product.image.url)}" if product.image else "<b>Image URL:</b> N/A"
        ]
        
        # Add each detail as a paragraph
        for detail in details:
            paragraph = Paragraph(detail, body_style)
            elements.append(paragraph)
            elements.append(Spacer(1, 6))  # Add space between details
        
        # Add space between products
        elements.append(Spacer(1, 12))
    
    # Build the PDF
    pdf.build(elements)
    
    # File response
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="products_list.pdf"'
    return response


# Add these imports at the top of views.py
from django.db.models import Max
import json
from .models import ChatFlow, FlowStep, FlowButton

@login_required
@user_passes_test(lambda u: u.is_user)
def custom_flow(request):
    """Single page for managing custom chat flows"""
    chatbot = get_object_or_404(Chatbot, user=request.user)
    flows = ChatFlow.objects.filter(chatbot=chatbot)
    
    return render(request, 'custom_flow.html', {
        'chatbot': chatbot,
        'flows': flows,
    })

@login_required
@user_passes_test(lambda u: u.is_user)
def api_create_flow(request):
    """API endpoint to create a new flow"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            chatbot = get_object_or_404(Chatbot, user=request.user)
            
            name = data.get('name')
            is_active = data.get('is_active', False)
            
            if not name:
                return JsonResponse({'success': False, 'error': 'Flow name is required'})
            
            # If making this flow active, deactivate others
            if is_active:
                ChatFlow.objects.filter(chatbot=chatbot, is_active=True).update(is_active=False)
            
            flow = ChatFlow.objects.create(
                chatbot=chatbot,
                name=name,
                is_active=is_active
            )
            
            return JsonResponse({
                'success': True, 
                'flow': {
                    'id': flow.id,
                    'name': flow.name,
                    'is_active': flow.is_active,
                    'created_at': flow.created_at.strftime('%Y-%m-%d %H:%M')
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_user)
def api_update_flow(request, flow_id):
    """API endpoint to update a flow"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flow = get_object_or_404(ChatFlow, id=flow_id, chatbot__user=request.user)
            
            name = data.get('name')
            is_active = data.get('is_active', False)
            
            if not name:
                return JsonResponse({'success': False, 'error': 'Flow name is required'})
            
            # If making this flow active, deactivate others
            if is_active and not flow.is_active:
                ChatFlow.objects.filter(chatbot=flow.chatbot, is_active=True).update(is_active=False)
            
            flow.name = name
            flow.is_active = is_active
            flow.save()
            
            return JsonResponse({
                'success': True, 
                'flow': {
                    'id': flow.id,
                    'name': flow.name,
                    'is_active': flow.is_active
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_user)
def api_delete_flow(request, flow_id):
    """API endpoint to delete a flow"""
    if request.method == 'POST':
        try:
            flow = get_object_or_404(ChatFlow, id=flow_id, chatbot__user=request.user)
            flow.delete()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_user)
def api_add_step(request, flow_id):
    """API endpoint to add a step to a flow"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flow = get_object_or_404(ChatFlow, id=flow_id, chatbot__user=request.user)
            
            step_type = data.get('step_type')
            message = data.get('message')
            
            if not step_type or not message:
                return JsonResponse({'success': False, 'error': 'Step type and message are required'})
            
            # Get the next order number
            highest_order = FlowStep.objects.filter(flow=flow).aggregate(Max('order'))['order__max'] or 0
            new_order = highest_order + 1
            
            step = FlowStep.objects.create(
                flow=flow,
                step_type=step_type,
                message=message,
                order=new_order
            )
            
            # Add buttons if provided
            buttons = []
            if step_type == 'buttons' and 'buttons' in data:
                for i, button_data in enumerate(data['buttons']):
                    if button_data.get('label') and button_data.get('value'):
                        button = FlowButton.objects.create(
                            step=step,
                            label=button_data['label'],
                            value=button_data['value'],
                            order=i
                        )
                        buttons.append({
                            'id': button.id,
                            'label': button.label,
                            'value': button.value,
                            'order': button.order
                        })
            
            return JsonResponse({
                'success': True,
                'step': {
                    'id': step.id,
                    'type': step.step_type,
                    'message': step.message,
                    'order': step.order,
                    'buttons': buttons
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_user)
def api_update_step(request, flow_id, step_id):
    """API endpoint to update a step or get step data"""
    flow = get_object_or_404(ChatFlow, id=flow_id, chatbot__user=request.user)
    step = get_object_or_404(FlowStep, id=step_id, flow=flow)
    
    # Handle GET request to fetch step data
    if request.method == 'GET':
        buttons = []
        if step.step_type == 'buttons':
            for button in FlowButton.objects.filter(step=step).order_by('order'):
                buttons.append({
                    'id': button.id,
                    'label': button.label,
                    'value': button.value,
                    'order': button.order
                })
        
        return JsonResponse({
            'success': True,
            'step': {
                'id': step.id,
                'type': step.step_type,
                'message': step.message,
                'order': step.order,
                'buttons': buttons
            }
        })
    
    # Handle POST request to update step
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            step_type = data.get('step_type')
            message = data.get('message')
            
            if not step_type or not message:
                return JsonResponse({'success': False, 'error': 'Step type and message are required'})
            
            step.step_type = step_type
            step.message = message
            step.save()
            
            # Update buttons
            buttons = []
            if step_type == 'buttons':
                # Delete existing buttons
                FlowButton.objects.filter(step=step).delete()
                
                # Add new buttons if provided
                if 'buttons' in data:
                    for i, button_data in enumerate(data['buttons']):
                        if button_data.get('label') and button_data.get('value'):
                            button = FlowButton.objects.create(
                                step=step,
                                label=button_data['label'],
                                value=button_data['value'],
                                order=i
                            )
                            buttons.append({
                                'id': button.id,
                                'label': button.label,
                                'value': button.value,
                                'order': button.order
                            })
            
            return JsonResponse({
                'success': True,
                'step': {
                    'id': step.id,
                    'type': step.step_type,
                    'message': step.message,
                    'order': step.order,
                    'buttons': buttons
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_user)
def api_delete_step(request, flow_id, step_id):
    """API endpoint to delete a step"""
    if request.method == 'POST':
        try:
            flow = get_object_or_404(ChatFlow, id=flow_id, chatbot__user=request.user)
            step = get_object_or_404(FlowStep, id=step_id, flow=flow)
            
            # Get the order of the step being deleted
            deleted_order = step.order
            
            # Delete the step
            step.delete()
            
            # Reorder remaining steps
            steps_to_update = FlowStep.objects.filter(flow=flow, order__gt=deleted_order)
            for step in steps_to_update:
                step.order -= 1
                step.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_user)
def api_reorder_steps(request, flow_id):
    """API endpoint to reorder steps"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            flow = get_object_or_404(ChatFlow, id=flow_id, chatbot__user=request.user)
            
            if 'steps' not in data:
                return JsonResponse({'success': False, 'error': 'Steps data is required'})
            
            # Update order of steps
            for step_data in data['steps']:
                step_id = step_data.get('id')
                new_order = step_data.get('order')
                
                if step_id and new_order is not None:
                    step = get_object_or_404(FlowStep, id=step_id, flow=flow)
                    step.order = new_order
                    step.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def get_flow_data(flow):
    """Helper function to get complete flow data including steps and buttons"""
    steps = FlowStep.objects.filter(flow=flow).order_by('order')
    step_data = []
    
    for step in steps:
        step_info = {
            'id': step.id,
            'type': step.step_type,
            'message': step.message,
            'order': step.order,
            'buttons': []
        }
        
        if step.step_type == 'buttons':
            buttons = FlowButton.objects.filter(step=step).order_by('order')
            for button in buttons:
                step_info['buttons'].append({
                    'label': button.label,
                    'value': button.value,
                    'order': button.order
                })
                
        step_data.append(step_info)
    
    return {
        'id': flow.id,
        'name': flow.name,
        'is_active': flow.is_active,
        'steps': step_data
    }

# ...existing code...

@login_required
@user_passes_test(lambda u: u.is_user)
def get_flow_json(request, flow_id):
    """Get full flow data including steps and buttons"""
    try:
        if request.method == 'GET':
            flow = get_object_or_404(ChatFlow, id=flow_id)
            flow_data = get_flow_data(flow)
            return JsonResponse({'success': True, 'flow': flow_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt 
@csrf_exempt 
def get_active_flow(request, chatbot_id):
    """Get the active flow for a specific chatbot"""
    try:
        # Get chatbot directly by ID
        chatbot = get_object_or_404(Chatbot, id=chatbot_id)
        
        logger.info(f"Fetching active flow for chatbot ID: {chatbot_id}")
        
        # Get active flow
        flow = ChatFlow.objects.filter(chatbot=chatbot, is_active=True).first()
        
        if flow:
            logger.info(f"Found active flow: {flow.name} (ID: {flow.id})")
            
            # Get steps with their buttons
            steps = []
            for step in FlowStep.objects.filter(flow=flow).order_by('order'):
                step_data = {
                    'id': step.id,
                    'type': step.step_type,
                    'message': step.message,
                    'order': step.order,
                    'buttons': []
                }
                
                if step.step_type == 'buttons':
                    for button in FlowButton.objects.filter(step=step).order_by('order'):
                        step_data['buttons'].append({
                            'label': button.label,
                            'value': button.value
                        })
                
                steps.append(step_data)
            
            return JsonResponse({
                'success': True,
                'has_flow': True,
                'flow': {
                    'id': flow.id,
                    'name': flow.name,
                    'steps': steps
                }
            })
        else:
            logger.info(f"No active flow found for chatbot ID: {chatbot_id}")
            return JsonResponse({'success': True, 'has_flow': False})
    except Exception as e:
        logger.error(f"Error fetching active flow for chatbot ID {chatbot_id}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})