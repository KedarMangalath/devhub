from django.urls import path
from . import views

urlpatterns = [
    path('workspace/<str:workspace_id>/fs/', views.workspace_fs, name='workspace_fs'),
    path('workspace/<str:workspace_id>/spawn/', views.workspace_spawn, name='workspace_spawn'),
    path('workspace/<str:workspace_id>/process/<str:process_id>/', views.workspace_process_io, name='workspace_process_io'),
    path('projects/', views.list_projects, name='list_projects'),
    path('projects/<str:project_id>/', views.get_project, name='get_project'),
]
