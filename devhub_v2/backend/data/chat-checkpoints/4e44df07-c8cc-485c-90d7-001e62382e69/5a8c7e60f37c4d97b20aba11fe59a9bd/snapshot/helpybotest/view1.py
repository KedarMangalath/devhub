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
            welcome_message=chatbot.welcome_message
        )

    logo_url = request.build_absolute_uri(chatbot.logo.url) if chatbot.logo else ''
    we_are_here_url = request.build_absolute_uri(chatbot.we_are_here_image.url) if chatbot.we_are_here_image else ''
    chat_response_url = request.build_absolute_uri(reverse('chat_response', args=[user.id]))
    # chat_response_url = request.build_absolute_uri(reverse('chat_response', args=[user.id])).replace("http://", "https://")

    script_content = render_to_string('chat_widget_template.js', {
        'user_id': user.id,
        'header_color': chatbot.header_color,
        'send_button_color': chatbot.send_button_color,
        'header_text': chatbot.header_text,
        'welcome_message': chatbot.welcome_message,
        'logo_url': logo_url,
        'we_are_here_url': we_are_here_url,
        'chat_response_url': chat_response_url,
        'translation_enabled': user.translation_enabled

    })
    script_path = os.path.join(settings.MEDIA_ROOT, f'chat_widgets/user_{user.id}_widget.js')
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, 'w') as f:
        f.write(script_content)

    timestamp = int(datetime.now().timestamp())
    return f'/media/chat_widgets/user_{user.id}_widget.js?v={timestamp}'




def generate_sample_html(user):
    html_content = render_to_string('sample_widget_page.html', {'user_id': user.id})
    html_path = os.path.join(settings.MEDIA_ROOT, f'sample_pages/user_{user.id}_sample.html')
    os.makedirs(os.path.dirname(html_path), exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(html_content)
    return f'/media/sample_pages/user_{user.id}_sample.html'


@login_required
@user_passes_test(lambda u: u.is_user)
def customize_chatbot(request):
    chatbot = get_object_or_404(Chatbot, user=request.user)
    if request.method == 'POST':
        form = ChatbotCustomizationForm(request.POST, request.FILES, instance=chatbot)
        if form.is_valid():
            chatbot = form.save(commit=False)
            
            if 'logo' in request.FILES:
                chatbot.logo = request.FILES['logo']
            
            if 'we_are_here_image' in request.FILES:
                chatbot.we_are_here_image = request.FILES['we_are_here_image']
            
            chatbot.save()
            generate_chat_widget(request, request.user)
            messages.success(request, 'Chatbot customization saved successfully.')
            return redirect('user_dashboard')
        else:
            messages.error(request, 'There was an error saving the chatbot customization.')
    else:
        form = ChatbotCustomizationForm(instance=chatbot)
    return render(request, 'customize_chatbot.html', {'form': form})


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
    users = User.objects.filter(is_user=True)
    paginator = Paginator(users, 10)  # Show 10 users per page
    page = request.GET.get('page')
    users_paginated = paginator.get_page(page)
    return render(request, 'admin_dashboard.html', {'users': users_paginated})

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

            if not chatbot.header_color:
                chatbot.header_color = "#0b3d2c"
            if not chatbot.send_button_color:
                chatbot.send_button_color = "#0b3d2c"
            if not chatbot.header_text:
                chatbot.header_text = "Name"
            if not chatbot.welcome_message:
                chatbot.welcome_message = "Welcome! How may I help you?"
            
            chatbot.save()
            messages.success(request, 'Chatbot settings saved successfully.')
            return redirect('user_dashboard')
        else:
            messages.error(request, 'There was an error saving the chatbot settings.')
    else:
        form = ChatbotForm(instance=chatbot)

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
            full_response = process_query(
                user_id=str(user_id),
                query=query,
                chat_history=chat_history,
                chatbot_role=chatbot.role_behavior,
                chatbot_tone='professional',
                fallback_message=chatbot.fallback_message,
                webapp_info=chatbot.web_app_info,
                welcome_message=chatbot.welcome_message 
            )

            cleaned_response = clean_response(full_response)
            client_ip = get_client_ip(request)

            # Only append new messages if they don't exist
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

            # Check if these exact messages aren't already in chat history
            if not any(msg["content"] == query and msg["role"] == "human" for msg in chat_history):
                chat_history.append(human_message)
            if not any(msg["content"] == cleaned_response and msg["role"] == "ai" for msg in chat_history):
                chat_history.append(ai_message)

            if len(chat_history) > 10:
                chat_history = chat_history[-10:]

            save_chat_history(user_id, session_id, chat_history)

            ChatHistory.objects.create(
                user=user,
                chatbot=chatbot,
                session_id=session_id,
                content=chat_history
            )

            return JsonResponse({
                'response': cleaned_response, 
                'session_id': session_id,
                'logo_url': logo_url
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
    return redirect('index')

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
        chatbot = Chatbot.objects.create(user=request.user)

    if request.method == 'POST':
        web_app_info = request.POST.get('web_app_info')
        chatbot.web_app_info = web_app_info
        chatbot.save()
        return redirect('user_dashboard')

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
def admin_dashboard(request):
    users = User.objects.filter(is_user=True).values(
        'id', 
        'username', 
        'openai_api_key',
        'widget_script_url',
        'sample_html_url',
        'translation_enabled',
        'whatsapp_license_number',
        'whatsapp_api_key',
        'telegram_bot_token'
    ).order_by('id')
    
    # Enhance user data with related WhatsApp config
    users_list = list(users)
    for user in users_list:
        try:
            whatsapp_config = WhatsAppConfig.objects.get(user_id=user['id'])
            user['whatsapp_license_number'] = whatsapp_config.license_number
            user['whatsapp_api_key'] = whatsapp_config.api_key
        except WhatsAppConfig.DoesNotExist:
            # Keep existing values from User model if WhatsAppConfig doesn't exist
            pass
    
    return render(request, 'admin_dashboard.html', {'users': users_list})



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
        if not user.whatsapp_license_number or not user.whatsapp_api_key or not user.telegram_bot_token:
            raise ValueError("User is missing required credentials")
        return {
            'whatsapp_license': user.whatsapp_license_number,
            'whatsapp_api_key': user.whatsapp_api_key,
            'telegram_token': user.telegram_bot_token
        }
    except User.DoesNotExist:
        raise ValueError("User not found or not authorized")

def process_whatsapp_message(request, user_id):
    try:
        # Get credentials for specific user
        credentials = get_user_credentials(user_id)
        LICENSE_NUMBER = credentials['whatsapp_license']
        API_KEY = credentials['whatsapp_api_key']

        # Build dynamic chatbot URL
        current_site = request.get_host()
        scheme = request.scheme
        chatbot_url = f"{scheme}://{current_site}/chat/response/{user_id}/"

        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            if request.POST:
                form_key = next(iter(request.POST))
                try:
                    data = json.loads(form_key)
                except:
                    data = request.POST.dict()
            else:
                data = {}

        if 'statuses' in data:
            return {
                "status": "success",
                "message": "Status update received"
            }

        if 'messages' not in data:
            return {
                "status": "success",
                "message": "Non-message update received"
            }

        message = data['messages'][0]
        
        if message.get('type') != 'text':
            return {
                "status": "success",
                "message": "Non-text message received"
            }

        user_message = message.get('text', {}).get('body', '')
        contact = message.get('from', '')

        if not user_message or not contact:
            return {
                "status": "error",
                "message": "Missing required fields"
            }

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
        
        whatsapp_response = session.get(
            "https://app.bytepaper.com/api/sendmediamessage.php",
            params={
                "LicenseNumber": LICENSE_NUMBER,
                "APIKey": API_KEY,
                "Contact": contact,
                "Message": bot_message,
                "Type": "text",
                "HeaderType": "text"
            },
            timeout=10
        )
        
        try:
            whatsapp_json = whatsapp_response.json()
        except json.JSONDecodeError:
            whatsapp_json = {"error": "Invalid JSON response", "text": whatsapp_response.text}
        
        return {
            "status": "success",
            "chatbot_message": bot_message,
            "whatsapp_status": whatsapp_json
        }
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise e

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
        return HttpResponse("WhatsApp webhook server is running!")
    
    try:
        result = process_whatsapp_message(request, user_id)
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