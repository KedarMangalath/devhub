from django.db import models

from core.models import Project


class GitHubConnection(models.Model):
    github_user_id = models.BigIntegerField(unique=True)
    login = models.CharField(max_length=255)
    name = models.CharField(max_length=255, blank=True)
    email = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    profile_url = models.URLField(max_length=500, blank=True)
    access_token = models.TextField(blank=True)
    token_scope = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    raw_payload = models.JSONField(default=dict)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "login"]

    def __str__(self):
        return self.login


class GitHubRepositoryLink(models.Model):
    project = models.OneToOneField(Project, related_name="github_repository_link", on_delete=models.CASCADE)
    connection = models.ForeignKey(
        GitHubConnection,
        related_name="repository_links",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    repository_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    owner_login = models.CharField(max_length=255)
    repository_name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    default_branch = models.CharField(max_length=255, blank=True)
    html_url = models.URLField(max_length=500, blank=True)
    clone_url = models.URLField(max_length=500, blank=True)
    issues_url = models.URLField(max_length=500, blank=True)
    pulls_url = models.URLField(max_length=500, blank=True)
    is_private = models.BooleanField(default=False)
    permissions = models.JSONField(default=dict)
    raw_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name
