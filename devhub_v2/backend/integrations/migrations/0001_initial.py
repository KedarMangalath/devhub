from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0002_project_workspace_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="GitHubConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("github_user_id", models.BigIntegerField(unique=True)),
                ("login", models.CharField(max_length=255)),
                ("name", models.CharField(blank=True, max_length=255)),
                ("email", models.CharField(blank=True, max_length=255)),
                ("avatar_url", models.URLField(blank=True, max_length=500)),
                ("profile_url", models.URLField(blank=True, max_length=500)),
                ("access_token", models.TextField(blank=True)),
                ("token_scope", models.CharField(blank=True, max_length=500)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("raw_payload", models.JSONField(default=dict)),
                ("connected_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-updated_at", "login"]},
        ),
        migrations.CreateModel(
            name="GitHubRepositoryLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("repository_id", models.BigIntegerField(blank=True, db_index=True, null=True)),
                ("owner_login", models.CharField(max_length=255)),
                ("repository_name", models.CharField(max_length=255)),
                ("full_name", models.CharField(max_length=255)),
                ("default_branch", models.CharField(blank=True, max_length=255)),
                ("html_url", models.URLField(blank=True, max_length=500)),
                ("clone_url", models.URLField(blank=True, max_length=500)),
                ("issues_url", models.URLField(blank=True, max_length=500)),
                ("pulls_url", models.URLField(blank=True, max_length=500)),
                ("is_private", models.BooleanField(default=False)),
                ("permissions", models.JSONField(default=dict)),
                ("raw_payload", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="repository_links",
                        to="integrations.githubconnection",
                    ),
                ),
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="github_repository_link",
                        to="core.project",
                    ),
                ),
            ],
            options={"ordering": ["full_name"]},
        ),
    ]
