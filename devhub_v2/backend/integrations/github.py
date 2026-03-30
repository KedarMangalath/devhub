from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


DEVHUB_SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "devhub-settings.json"


class GitHubIntegrationError(Exception):
    pass


def _load_devhub_settings() -> dict:
    if not DEVHUB_SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(DEVHUB_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_devhub_settings(settings: dict) -> None:
    DEVHUB_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEVHUB_SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def normalize_github_oauth_config(config: dict | None = None) -> dict:
    raw = dict(config or {})
    client_id = str(raw.get("client_id") or os.getenv("DEVHUB_GITHUB_CLIENT_ID") or "").strip()
    client_secret = str(raw.get("client_secret") or os.getenv("DEVHUB_GITHUB_CLIENT_SECRET") or "").strip()
    app_name = str(raw.get("app_name") or os.getenv("DEVHUB_GITHUB_APP_NAME") or "GitHub").strip()
    app_base_url = str(raw.get("app_base_url") or os.getenv("DEVHUB_GITHUB_APP_BASE_URL") or "https://github.com").strip().rstrip("/")
    api_base_url = str(raw.get("api_base_url") or os.getenv("DEVHUB_GITHUB_API_BASE_URL") or "https://api.github.com").strip().rstrip("/")
    scopes = str(raw.get("scopes") or os.getenv("DEVHUB_GITHUB_SCOPES") or "repo read:org").strip()
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "app_name": app_name,
        "app_base_url": app_base_url,
        "api_base_url": api_base_url,
        "scopes": scopes,
    }


def github_oauth_config() -> dict:
    settings = _load_devhub_settings()
    return normalize_github_oauth_config(settings.get("github_oauth") or {})


def save_github_oauth_config(config: dict) -> dict:
    settings = _load_devhub_settings()
    normalized = normalize_github_oauth_config(config)
    settings["github_oauth"] = normalized
    _save_devhub_settings(settings)
    return normalized


def github_oauth_is_configured(config: dict | None = None) -> bool:
    cfg = normalize_github_oauth_config(config or github_oauth_config())
    return bool(cfg.get("client_id") and cfg.get("client_secret"))


def github_oauth_public_settings(config: dict | None = None) -> dict:
    cfg = normalize_github_oauth_config(config or github_oauth_config())
    return {
        "configured": github_oauth_is_configured(cfg),
        "app_name": cfg.get("app_name"),
        "scopes": cfg.get("scopes"),
        "has_client_credentials": bool(cfg.get("client_id") and cfg.get("client_secret")),
        "api_base_url": cfg.get("api_base_url"),
        "app_base_url": cfg.get("app_base_url"),
    }


def github_authorize_url(config: dict, *, state: str, redirect_uri: str) -> str:
    cfg = normalize_github_oauth_config(config)
    if not github_oauth_is_configured(cfg):
        raise GitHubIntegrationError("GitHub OAuth is not configured. Add a client id and client secret on the server first.")
    query = urlencode(
        {
            "client_id": cfg["client_id"],
            "redirect_uri": redirect_uri,
            "scope": cfg["scopes"],
            "state": state,
        }
    )
    return f"{cfg['app_base_url']}/login/oauth/authorize?{query}"


def exchange_oauth_code(config: dict, *, code: str, redirect_uri: str) -> dict:
    cfg = normalize_github_oauth_config(config)
    if not github_oauth_is_configured(cfg):
        raise GitHubIntegrationError("GitHub OAuth is not configured on the server.")
    response = requests.post(
        f"{cfg['app_base_url']}/login/oauth/access_token",
        headers={"Accept": "application/json", "User-Agent": "DevHub-V2"},
        json={
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise GitHubIntegrationError(response.text or "GitHub OAuth token exchange failed.")
    data = response.json()
    if data.get("error"):
        raise GitHubIntegrationError(data.get("error_description") or data["error"])
    if not data.get("access_token"):
        raise GitHubIntegrationError("GitHub did not return an access token.")
    return data


def _github_request(
    config: dict,
    method: str,
    path: str,
    *,
    access_token: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    cfg = normalize_github_oauth_config(config)
    url = path if path.startswith("http") else f"{cfg['api_base_url']}/{path.lstrip('/')}"
    response = requests.request(
        method.upper(),
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DevHub-V2",
        },
        params=params,
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        try:
            data = response.json()
        except Exception:
            data = {}
        raise GitHubIntegrationError(data.get("message") or response.text or f"GitHub request failed with {response.status_code}")
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def fetch_authenticated_user(config: dict, access_token: str) -> dict:
    return _github_request(config, "GET", "/user", access_token=access_token)


def list_user_repositories(config: dict, access_token: str) -> list[dict]:
    data = _github_request(
        config,
        "GET",
        "/user/repos",
        access_token=access_token,
        params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
    )
    return data if isinstance(data, list) else []


def get_user_repository(config: dict, access_token: str, full_name: str) -> dict:
    return _github_request(config, "GET", f"/repos/{full_name}", access_token=access_token)


def list_repository_issues(config: dict, access_token: str, full_name: str) -> list[dict]:
    data = _github_request(
        config,
        "GET",
        f"/repos/{full_name}/issues",
        access_token=access_token,
        params={"state": "all", "per_page": 100},
    )
    return [item for item in data if isinstance(item, dict) and "pull_request" not in item]


def create_repository_issue(config: dict, access_token: str, full_name: str, payload: dict[str, Any]) -> dict:
    return _github_request(config, "POST", f"/repos/{full_name}/issues", access_token=access_token, payload=payload)


def list_repository_pulls(config: dict, access_token: str, full_name: str) -> list[dict]:
    data = _github_request(
        config,
        "GET",
        f"/repos/{full_name}/pulls",
        access_token=access_token,
        params={"state": "all", "per_page": 100},
    )
    return data if isinstance(data, list) else []


def create_repository_pull(config: dict, access_token: str, full_name: str, payload: dict[str, Any]) -> dict:
    return _github_request(config, "POST", f"/repos/{full_name}/pulls", access_token=access_token, payload=payload)


def clone_repository_with_token(access_token: str, full_name: str, destination: Path) -> None:
    destination = Path(destination)
    https_url = f"https://github.com/{full_name}.git"
    authenticated_url = f"https://x-access-token:{access_token}@github.com/{full_name}.git"
    result = subprocess.run(
        ["git", "clone", "--depth", "1", authenticated_url, str(destination)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise GitHubIntegrationError(result.stderr.strip() or "GitHub clone failed.")
    subprocess.run(
        ["git", "-C", str(destination), "remote", "set-url", "origin", https_url],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
