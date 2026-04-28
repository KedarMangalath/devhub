from django.urls import path

from integrations import views as integration_views

from api.views.agent import deep_documentation_progress, deep_documentation_stream, start_agent
from api.views.chat import project_chat, project_chat_undo
from api.views.chat_stream import project_chat_agent_stream
from api.views.import_views import inspect_folder_import, inspect_github_import, pick_local_folder, suggest_project_details
from api.views.skills import detect_skills, skill_detail, skills_list
from api.views.projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
    pipeline_action,
    project_codebase_doc,
    project_coder_customization_bootstrap,
    project_documentation,
    project_features,
    update_project,
)
from api.views.settings import devhub_ai_settings
from api.views.workspace import workspace_fs, workspace_process_io, workspace_runtime, workspace_setup, workspace_spawn

urlpatterns = [
    path('integrations/github/', integration_views.github_connection_status, name='github_connection_status'),
    path('integrations/github/connect/', integration_views.github_connect, name='github_connect'),
    path('integrations/github/callback/', integration_views.github_callback, name='github_callback'),
    path('integrations/github/disconnect/', integration_views.github_disconnect, name='github_disconnect'),
    path('integrations/github/repositories/', integration_views.github_repositories, name='github_repositories'),

    # Projects
    path('projects/', list_projects, name='list_projects'),
    path('projects/create/', create_project, name='create_project'),
    path('projects/suggest/', suggest_project_details, name='suggest_project_details'),
    path('settings/ai/', devhub_ai_settings, name='devhub_ai_settings'),
    path('projects/import/github/inspect/', inspect_github_import, name='inspect_github_import'),
    path('projects/import/github-connect/inspect/', integration_views.inspect_github_connected_import, name='inspect_github_connected_import'),
    path('projects/import/folder/pick/', pick_local_folder, name='pick_local_folder'),
    path('projects/import/folder/inspect/', inspect_folder_import, name='inspect_folder_import'),
    path('projects/<str:project_id>/', get_project, name='get_project'),
    path('projects/<str:project_id>/coder-customization/bootstrap/', project_coder_customization_bootstrap, name='project_coder_customization_bootstrap'),
    path('projects/<str:project_id>/update/', update_project, name='update_project'),
    path('projects/<str:project_id>/delete/', delete_project, name='delete_project'),
    path('projects/<str:project_id>/documentation/', project_documentation, name='project_documentation'),
    path('projects/<str:project_id>/codebase/doc/', project_codebase_doc, name='project_codebase_doc'),

    # Features (pipeline)
    path('projects/<str:project_id>/features/', project_features, name='project_features'),

    # Pipeline actions (advance / reject / approve)
    path('projects/<str:project_id>/pipeline/action/', pipeline_action, name='pipeline_action'),

    # Chat
    path('projects/<str:project_id>/chat/', project_chat, name='project_chat'),
    path('projects/<str:project_id>/chat/undo/', project_chat_undo, name='project_chat_undo'),
    path('projects/<str:project_id>/chat/agent-stream/', project_chat_agent_stream, name='project_chat_agent_stream'),
    path('projects/<str:project_id>/github/', integration_views.project_github_status, name='project_github_status'),
    path('projects/<str:project_id>/github/issues/', integration_views.project_github_issues, name='project_github_issues'),
    path('projects/<str:project_id>/github/pulls/', integration_views.project_github_pulls, name='project_github_pulls'),

    # Agent
    path('projects/<str:project_id>/agent/start/', start_agent, name='start_agent'),
    path('projects/<str:project_id>/agent/deep-docs/', deep_documentation_stream, name='deep_documentation_stream'),
    path('projects/<str:project_id>/agent/deep-docs/progress/', deep_documentation_progress, name='deep_documentation_progress'),

    # Global Skills
    path('skills/', skills_list, name='skills_list'),
    path('skills/detect/', detect_skills, name='detect_skills'),
    path('skills/<str:slug>/', skill_detail, name='skill_detail'),

    # Workspace filesystem
    path('workspace/<str:workspace_id>/fs/', workspace_fs, name='workspace_fs'),
    path('workspace/<str:workspace_id>/spawn/', workspace_spawn, name='workspace_spawn'),
    path('workspace/<str:workspace_id>/process/<str:process_id>/', workspace_process_io, name='workspace_process_io'),
    path('workspace/<str:workspace_id>/runtime/', workspace_runtime, name='workspace_runtime'),
    path('workspace/<str:workspace_id>/setup/', workspace_setup, name='workspace_setup'),
]
