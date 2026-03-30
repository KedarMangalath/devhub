import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.core import signing
from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.views import _build_import_inspection, _parse_json_body
from core.models import Project
from .github import (
    GitHubIntegrationError,
    clone_repository_with_token,
    exchange_oauth_code,
    fetch_authenticated_user,
    get_user_repository,
    github_authorize_url,
    github_oauth_config,
    github_oauth_public_settings,
    github_oauth_is_configured,
    list_repository_issues,
    list_repository_pulls,
    list_user_repositories,
    normalize_github_oauth_config,
    save_github_oauth_config,
    create_repository_issue,
    create_repository_pull,
)
from .models import GitHubConnection, GitHubRepositoryLink


GITHUB_STATE_SALT = "devhub.github.oauth"
DEFAULT_FRONTEND_URL = "http://localhost:5173/"


def _oauth_callback_url(request) -> str:
    return request.build_absolute_uri("/api/integrations/github/callback/")


def _normalize_return_to(request, value: str | None) -> str:
    raw = str(value or "").strip()
    if raw.startswith("http://localhost") or raw.startswith("http://127.0.0.1") or raw.startswith("https://localhost"):
        return raw
    origin = str(request.headers.get("Origin") or "").strip()
    if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1") or origin.startswith("https://localhost"):
        return origin.rstrip("/") + "/"
    return DEFAULT_FRONTEND_URL


def _append_query(url: str, **params: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            continue
        query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _connection_payload(connection: GitHubConnection | None) -> dict | None:
    if not connection:
        return None
    return {
        "id": connection.id,
        "login": connection.login,
        "name": connection.name,
        "email": connection.email,
        "avatar_url": connection.avatar_url,
        "profile_url": connection.profile_url,
        "token_scope": connection.token_scope,
        "connected_at": connection.connected_at,
        "updated_at": connection.updated_at,
        "is_active": connection.is_active,
    }


def _repository_payload(repo: dict, connection: GitHubConnection | None = None) -> dict:
    owner = repo.get("owner") or {}
    return {
        "connection_id": connection.id if connection else None,
        "repository_id": repo.get("id"),
        "owner_login": owner.get("login"),
        "repository_name": repo.get("name"),
        "full_name": repo.get("full_name"),
        "default_branch": repo.get("default_branch"),
        "html_url": repo.get("html_url"),
        "clone_url": repo.get("clone_url"),
        "private": bool(repo.get("private")),
        "permissions": repo.get("permissions") or {},
        "open_issues_count": repo.get("open_issues_count"),
    }


def _active_connection() -> GitHubConnection | None:
    return GitHubConnection.objects.filter(is_active=True).order_by("-updated_at").first()


def _linked_repository_or_404(project_id: str):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return None, None, JsonResponse({"error": "Project not found"}, status=404)

    link = GitHubRepositoryLink.objects.select_related("connection").filter(project=project).first()
    if not link or not link.connection_id or not link.connection or not link.connection.access_token:
        return project, None, JsonResponse({"error": "Project is not linked to a connected GitHub repository"}, status=404)
    return project, link, None


@csrf_exempt
def github_connection_status(request):
    if request.method == "GET":
        connection = _active_connection()
        return JsonResponse(
            {
                "github": github_oauth_public_settings(),
                "connection": _connection_payload(connection),
            }
        )

    if request.method == "POST":
        try:
            body = _parse_json_body(request)
            config = save_github_oauth_config(body.get("github") or body)
            return JsonResponse({"github": github_oauth_public_settings(config)})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


def github_connect(request):
    try:
        config = github_oauth_config()
        if not github_oauth_is_configured(config):
            return JsonResponse({"error": "GitHub OAuth is not configured on the server."}, status=400)
        return_to = _normalize_return_to(request, request.GET.get("return_to"))
        state = signing.dumps({"return_to": return_to}, salt=GITHUB_STATE_SALT)
        authorize_url = github_authorize_url(config, state=state, redirect_uri=_oauth_callback_url(request))
        return HttpResponseRedirect(authorize_url)
    except GitHubIntegrationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


def github_callback(request):
    return_to = _normalize_return_to(request, request.GET.get("return_to"))
    try:
        state = str(request.GET.get("state") or "")
        code = str(request.GET.get("code") or "")
        if not state or not code:
            return HttpResponseRedirect(_append_query(return_to, github="error", reason="missing_callback_parameters"))

        payload = signing.loads(state, salt=GITHUB_STATE_SALT, max_age=900)
        return_to = _normalize_return_to(request, payload.get("return_to"))

        config = github_oauth_config()
        token_payload = exchange_oauth_code(config, code=code, redirect_uri=_oauth_callback_url(request))
        access_token = str(token_payload.get("access_token") or "")
        user = fetch_authenticated_user(config, access_token)

        GitHubConnection.objects.exclude(github_user_id=user.get("id")).update(is_active=False)
        connection, _created = GitHubConnection.objects.update_or_create(
            github_user_id=user.get("id"),
            defaults={
                "login": str(user.get("login") or ""),
                "name": str(user.get("name") or ""),
                "email": str(user.get("email") or ""),
                "avatar_url": str(user.get("avatar_url") or ""),
                "profile_url": str(user.get("html_url") or ""),
                "access_token": access_token,
                "token_scope": str(token_payload.get("scope") or ""),
                "is_active": True,
                "raw_payload": user,
            },
        )
        GitHubConnection.objects.exclude(id=connection.id).update(is_active=False)
        return HttpResponseRedirect(_append_query(return_to, github="connected", github_login=connection.login))
    except signing.BadSignature:
        return HttpResponseRedirect(_append_query(return_to, github="error", reason="invalid_state"))
    except GitHubIntegrationError as exc:
        return HttpResponseRedirect(_append_query(return_to, github="error", reason=str(exc)))
    except Exception as exc:
        return HttpResponseRedirect(_append_query(return_to, github="error", reason=str(exc)))


@csrf_exempt
def github_disconnect(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    GitHubConnection.objects.filter(is_active=True).update(is_active=False)
    return JsonResponse({"success": True})


def github_repositories(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    connection = _active_connection()
    if not connection or not connection.access_token:
        return JsonResponse({"error": "Connect GitHub first."}, status=404)

    try:
        config = github_oauth_config()
        repositories = list_user_repositories(config, connection.access_token)
        return JsonResponse(
            {
                "connection": _connection_payload(connection),
                "repositories": [_repository_payload(repo, connection) for repo in repositories],
            }
        )
    except GitHubIntegrationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def inspect_github_connected_import(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    temp_dir = None
    try:
        body = _parse_json_body(request)
        full_name = str(body.get("github_repository_full_name") or "").strip()
        idea = str(body.get("idea") or "").strip()
        connection_id = int(body.get("github_connection_id") or 0)
        connection = GitHubConnection.objects.filter(id=connection_id, is_active=True).first() if connection_id else _active_connection()
        if not full_name:
            return JsonResponse({"error": "GitHub repository is required"}, status=400)
        if not connection or not connection.access_token:
            return JsonResponse({"error": "Connect GitHub before importing a repository."}, status=400)

        config = github_oauth_config()
        repository = get_user_repository(config, connection.access_token, full_name)
        temp_dir = Path(tempfile.mkdtemp(prefix="devhub-github-import-"))
        repo_root = temp_dir / "repo"
        clone_repository_with_token(connection.access_token, full_name, repo_root)
        inspection = _build_import_inspection(repo_root, "github", idea=idea, source_label=repository.get("html_url") or full_name)
        inspection["github_url"] = repository.get("html_url") or f"https://github.com/{full_name}"
        inspection["github_connection_id"] = connection.id
        inspection["github_repository_full_name"] = full_name
        inspection["github_repository"] = _repository_payload(repository, connection)
        return JsonResponse(inspection)
    except GitHubIntegrationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@csrf_exempt
def project_github_status(request, project_id: str):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    project, link, error = _linked_repository_or_404(project_id)
    if error:
        return error

    return JsonResponse(
        {
            "project_id": str(project.id),
            "connection": _connection_payload(link.connection),
            "repository": {
                "connection_id": link.connection_id,
                "full_name": link.full_name,
                "owner_login": link.owner_login,
                "repository_name": link.repository_name,
                "default_branch": link.default_branch,
                "html_url": link.html_url,
                "private": link.is_private,
                "permissions": link.permissions or {},
            },
        }
    )


@csrf_exempt
def project_github_issues(request, project_id: str):
    project, link, error = _linked_repository_or_404(project_id)
    if error:
        return error

    try:
        config = normalize_github_oauth_config(github_oauth_config())
        token = link.connection.access_token
        if request.method == "GET":
            issues = list_repository_issues(config, token, link.full_name)
            return JsonResponse(
                {
                    "repository": {"full_name": link.full_name, "html_url": link.html_url},
                    "issues": [
                        {
                            "id": item.get("id"),
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "state": item.get("state"),
                            "html_url": item.get("html_url"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "author": (item.get("user") or {}).get("login"),
                            "labels": [label.get("name") for label in (item.get("labels") or []) if isinstance(label, dict)],
                            "comments": item.get("comments"),
                        }
                        for item in issues
                    ],
                }
            )

        if request.method == "POST":
            body = _parse_json_body(request)
            title = str(body.get("title") or "").strip()
            if not title:
                return JsonResponse({"error": "Issue title is required"}, status=400)
            payload = {
                "title": title,
                "body": str(body.get("body") or "").strip(),
                "labels": body.get("labels") or [],
                "assignees": body.get("assignees") or [],
            }
            issue = create_repository_issue(config, token, link.full_name, payload)
            return JsonResponse(
                {
                    "issue": {
                        "id": issue.get("id"),
                        "number": issue.get("number"),
                        "title": issue.get("title"),
                        "state": issue.get("state"),
                        "html_url": issue.get("html_url"),
                    }
                },
                status=201,
            )
    except GitHubIntegrationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def project_github_pulls(request, project_id: str):
    project, link, error = _linked_repository_or_404(project_id)
    if error:
        return error

    try:
        config = normalize_github_oauth_config(github_oauth_config())
        token = link.connection.access_token
        if request.method == "GET":
            pulls = list_repository_pulls(config, token, link.full_name)
            return JsonResponse(
                {
                    "repository": {"full_name": link.full_name, "html_url": link.html_url},
                    "pulls": [
                        {
                            "id": item.get("id"),
                            "number": item.get("number"),
                            "title": item.get("title"),
                            "state": item.get("state"),
                            "html_url": item.get("html_url"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                            "author": (item.get("user") or {}).get("login"),
                            "draft": bool(item.get("draft")),
                            "base_branch": ((item.get("base") or {}).get("ref")),
                            "head_branch": ((item.get("head") or {}).get("ref")),
                        }
                        for item in pulls
                    ],
                }
            )

        if request.method == "POST":
            body = _parse_json_body(request)
            title = str(body.get("title") or "").strip()
            head = str(body.get("head") or "").strip()
            base = str(body.get("base") or link.default_branch or "").strip()
            if not title or not head or not base:
                return JsonResponse({"error": "Pull request title, head branch, and base branch are required"}, status=400)
            payload = {
                "title": title,
                "body": str(body.get("body") or "").strip(),
                "head": head,
                "base": base,
                "draft": bool(body.get("draft")),
            }
            pull = create_repository_pull(config, token, link.full_name, payload)
            return JsonResponse(
                {
                    "pull": {
                        "id": pull.get("id"),
                        "number": pull.get("number"),
                        "title": pull.get("title"),
                        "state": pull.get("state"),
                        "html_url": pull.get("html_url"),
                    }
                },
                status=201,
            )
    except GitHubIntegrationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)
