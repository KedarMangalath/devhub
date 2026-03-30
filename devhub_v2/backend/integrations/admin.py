from django.contrib import admin

from .models import GitHubConnection, GitHubRepositoryLink


@admin.register(GitHubConnection)
class GitHubConnectionAdmin(admin.ModelAdmin):
    list_display = ("login", "name", "is_active", "connected_at", "updated_at")
    search_fields = ("login", "name", "email", "github_user_id")
    list_filter = ("is_active",)


@admin.register(GitHubRepositoryLink)
class GitHubRepositoryLinkAdmin(admin.ModelAdmin):
    list_display = ("full_name", "project", "connection", "is_private", "default_branch", "updated_at")
    search_fields = ("full_name", "owner_login", "repository_name", "project__name")
