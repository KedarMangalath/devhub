from django.urls import path
from . import views

urlpatterns = [
    # Projects
    path('projects/', views.list_projects, name='list_projects'),
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/suggest/', views.suggest_project_details, name='suggest_project_details'),
    path('settings/ai/', views.devhub_ai_settings, name='devhub_ai_settings'),
    path('projects/import/github/inspect/', views.inspect_github_import, name='inspect_github_import'),
    path('projects/import/folder/pick/', views.pick_local_folder, name='pick_local_folder'),
    path('projects/import/folder/inspect/', views.inspect_folder_import, name='inspect_folder_import'),
    path('projects/<str:project_id>/', views.get_project, name='get_project'),
    path('projects/<str:project_id>/update/', views.update_project, name='update_project'),
    path('projects/<str:project_id>/delete/', views.delete_project, name='delete_project'),
    path('projects/<str:project_id>/documentation/', views.project_documentation, name='project_documentation'),
    path('projects/<str:project_id>/codebase/doc/', views.project_codebase_doc, name='project_codebase_doc'),

    # Features (pipeline)
    path('projects/<str:project_id>/features/', views.project_features, name='project_features'),

    # Pipeline actions (advance / reject / approve)
    path('projects/<str:project_id>/pipeline/action/', views.pipeline_action, name='pipeline_action'),

    # Chat
    path('projects/<str:project_id>/chat/', views.project_chat, name='project_chat'),

    # Agent
    path('projects/<str:project_id>/agent/start/', views.start_agent, name='start_agent'),
    path('projects/<str:project_id>/agent/deep-docs/', views.deep_documentation_stream, name='deep_documentation_stream'),
    path('projects/<str:project_id>/agent/deep-docs/progress/', views.deep_documentation_progress, name='deep_documentation_progress'),

    # Workspace filesystem
    path('workspace/<str:workspace_id>/fs/', views.workspace_fs, name='workspace_fs'),
    path('workspace/<str:workspace_id>/spawn/', views.workspace_spawn, name='workspace_spawn'),
    path('workspace/<str:workspace_id>/process/<str:process_id>/', views.workspace_process_io, name='workspace_process_io'),
    path('workspace/<str:workspace_id>/runtime/', views.workspace_runtime, name='workspace_runtime'),
    path('workspace/<str:workspace_id>/setup/', views.workspace_setup, name='workspace_setup'),
]
