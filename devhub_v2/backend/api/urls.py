from django.urls import path
from . import views

urlpatterns = [
    # Projects
    path('projects/', views.list_projects, name='list_projects'),
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/<str:project_id>/', views.get_project, name='get_project'),
    path('projects/<str:project_id>/delete/', views.delete_project, name='delete_project'),

    # Features (pipeline)
    path('projects/<str:project_id>/features/', views.project_features, name='project_features'),

    # Pipeline actions (advance / reject / approve)
    path('projects/<str:project_id>/pipeline/action/', views.pipeline_action, name='pipeline_action'),

    # Chat
    path('projects/<str:project_id>/chat/', views.project_chat, name='project_chat'),

    # Agent
    path('projects/<str:project_id>/agent/start/', views.start_agent, name='start_agent'),

    # Workspace filesystem
    path('workspace/<str:workspace_id>/fs/', views.workspace_fs, name='workspace_fs'),
    path('workspace/<str:workspace_id>/spawn/', views.workspace_spawn, name='workspace_spawn'),
    path('workspace/<str:workspace_id>/process/<str:process_id>/', views.workspace_process_io, name='workspace_process_io'),
    path('workspace/<str:workspace_id>/runtime/', views.workspace_runtime, name='workspace_runtime'),
    path('workspace/<str:workspace_id>/setup/', views.workspace_setup, name='workspace_setup'),
]
