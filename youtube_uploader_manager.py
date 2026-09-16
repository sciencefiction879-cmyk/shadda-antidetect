"""
youtube_uploader_manager.py - Optional YouTube Cloud Uploader & GitHub Automation Manager
Supports linking custom GitHub accounts/repos, custom uploader source (MEGA/Drive),
custom scheduling slots (e.g. 7PM & 10PM PKT), 1-click workflow dispatch, and live status monitoring.
"""

import os
import json
import time
import urllib.request
import urllib.error
import ssl

DATA_DIR = os.path.expanduser('~/Library/Application Support/ShaddaAntiDetect')
CONFIG_FILE = os.path.join(DATA_DIR, 'youtube_uploader_config.json')

DEFAULT_CONFIG = {
    "enabled": False,
    "github_account_id": "",
    "github_repo": "sciencefiction879-cmyk/youtube-automation-with-github",
    "workflow_file": "upload.yml",
    "branch": "main",
    "custom_token": "",
    "channel_name": "Sci-Fi & 3D Animation Chronicles",
    "channel_email": "sciencefiction879@gmail.com",
    "storage_source": "mega",
    "mega_folder_url": "https://mega.nz/folder/OORhyJ4A#hv02IpcssHV3xX6TYvU6Eg",
    "gdrive_folder_id": "",
    "slot1_time_pkt": "19:00",
    "slot2_time_pkt": "22:00",
    "timezone": "Asia/Karachi (PKT, UTC+5)",
    "cron_expression": "0 14,17 * * *",
    "default_privacy": "public",
    "default_category_id": "24",
    "default_made_for_kids": False,
    "shorts_max_seconds": 180,
    "description_footer": "\n\n🔔 Subscribe to the channel for more epic 3D Sci-Fi and Animated adventures!",
    "tags": ["Sci-Fi", "3D Animation", "Shorts", "Trending", "CGI"],
    "discord_webhook_url": "",
    "auto_generate_metadata": True,
    "auto_generate_thumbnail": True,
    "last_run": None,
    "history": []
}


def _ensure_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)


def load_config():
    _ensure_dir()
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update(cfg)
            return merged
    except Exception as e:
        print(f'[!] Error reading uploader config: {e}')
        return dict(DEFAULT_CONFIG)


def save_config(new_config):
    _ensure_dir()
    current = load_config() if os.path.exists(CONFIG_FILE) else dict(DEFAULT_CONFIG)
    current.update(new_config)
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(current, f, indent=2)
        return True, current
    except Exception as e:
        return False, str(e)


def _get_effective_token(cfg, explicit_token=None):
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()
    if cfg.get('custom_token') and cfg['custom_token'].strip():
        return cfg['custom_token'].strip()
    try:
        import github_client
        acc_id = cfg.get('github_account_id')
        if acc_id:
            acc = github_client.get_account(acc_id)
            if acc and acc.get('token'):
                return acc['token']
        default_acc = github_client.get_default_account()
        if default_acc and default_acc.get('token'):
            return default_acc['token']
    except Exception:
        pass
    return None


def verify_github_repo(token=None, repo=None):
    cfg = load_config()
    token = _get_effective_token(cfg, token)
    repo = repo or cfg.get('github_repo')

    if not token:
        return {'success': False, 'error': 'No GitHub Personal Access Token (PAT) provided or configured.'}
    if not repo or '/' not in repo:
        return {'success': False, 'error': 'Invalid repository format. Must be owner/repo (e.g. username/repo).'}

    owner, repo_name = repo.strip().split('/', 1)
    url = f'https://api.github.com/repos/{owner}/{repo_name}'

    req = urllib.request.Request(url, headers={
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ShaddaAntiDetect/0.3'
    })

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            permissions = data.get('permissions', {})
            has_push = permissions.get('push', False)
            return {
                'success': True,
                'repo': data.get('full_name'),
                'private': data.get('private', False),
                'default_branch': data.get('default_branch', 'main'),
                'permissions': permissions,
                'can_dispatch': has_push or permissions.get('admin', False),
                'owner': data.get('owner', {}).get('login'),
                'stars': data.get('stargazers_count', 0)
            }
    except urllib.error.HTTPError as e:
        msg = f'GitHub API error {e.code}: {e.reason}'
        if e.code == 401:
            msg = 'Invalid GitHub Personal Access Token (Authentication Failed).'
        elif e.code == 404:
            msg = f'Repository {repo} not found or token lacks access permissions.'
        return {'success': False, 'error': msg, 'code': e.code}
    except Exception as e:
        return {'success': False, 'error': f'Connection error: {str(e)}'}


def trigger_workflow(slot='slot1', dry_run=False, force_video='', token=None, repo=None, workflow_file=None, branch=None):
    cfg = load_config()
    token = _get_effective_token(cfg, token)
    repo = repo or cfg.get('github_repo')
    workflow_file = workflow_file or cfg.get('workflow_file', 'upload.yml')
    branch = branch or cfg.get('branch', 'main')

    if not token:
        return {'success': False, 'error': 'Missing GitHub token. Please configure GitHub in the uploader settings.'}
    if not repo or '/' not in repo:
        return {'success': False, 'error': 'Invalid repository name.'}

    owner, repo_name = repo.strip().split('/', 1)
    url = f'https://api.github.com/repos/{owner}/{repo_name}/actions/workflows/{workflow_file}/dispatches'

    payload = {
        'ref': branch,
        'inputs': {
            'slot': slot,
            'dry_run': bool(dry_run),
            'force_video': str(force_video or '')
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'ShaddaAntiDetect/0.3'
        },
        method='POST'
    )

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
            if resp.status in (204, 200, 201):
                run_record = {
                    'timestamp': int(time.time()),
                    'iso_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()),
                    'slot': slot,
                    'dry_run': dry_run,
                    'force_video': force_video,
                    'repo': repo,
                    'workflow': workflow_file,
                    'status': 'dispatched'
                }
                cfg['last_run'] = run_record
                history = cfg.get('history', [])
                history.insert(0, run_record)
                cfg['history'] = history[:30]
                save_config(cfg)

                return {
                    'success': True,
                    'message': f'GitHub Actions workflow {workflow_file} successfully dispatched on {branch} branch!',
                    'slot': slot,
                    'repo': repo,
                    'actions_url': f'https://github.com/{repo}/actions'
                }
            return {'success': False, 'error': f'Unexpected response from GitHub: status {resp.status}'}
    except urllib.error.HTTPError as e:
        err_body = ''
        try:
            err_body = e.read().decode('utf-8')
        except Exception:
            pass
        return {
            'success': False,
            'error': f'GitHub dispatch failed ({e.code}): {e.reason}. {err_body}',
            'code': e.code
        }
    except Exception as e:
        return {'success': False, 'error': f'Connection error: {str(e)}'}


def get_workflow_runs(token=None, repo=None, workflow_file=None, per_page=5):
    cfg = load_config()
    token = _get_effective_token(cfg, token)
    repo = repo or cfg.get('github_repo')
    workflow_file = workflow_file or cfg.get('workflow_file', 'upload.yml')

    if not token or not repo or '/' not in repo:
        return {'success': False, 'runs': [], 'error': 'GitHub token or repo not configured.'}

    owner, repo_name = repo.strip().split('/', 1)
    url = f'https://api.github.com/repos/{owner}/{repo_name}/actions/workflows/{workflow_file}/runs?per_page={per_page}'

    req = urllib.request.Request(url, headers={
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ShaddaAntiDetect/0.3'
    })

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            runs = []
            for r in data.get('workflow_runs', []):
                runs.append({
                    'id': r.get('id'),
                    'name': r.get('name'),
                    'status': r.get('status'),
                    'conclusion': r.get('conclusion'),
                    'event': r.get('event'),
                    'created_at': r.get('created_at'),
                    'updated_at': r.get('updated_at'),
                    'html_url': r.get('html_url'),
                    'run_number': r.get('run_number'),
                    'actor': r.get('actor', {}).get('login')
                })
            return {
                'success': True,
                'total_count': data.get('total_count', 0),
                'runs': runs,
                'actions_url': f'https://github.com/{repo}/actions'
            }
    except urllib.error.HTTPError as e:
        return {'success': False, 'runs': [], 'error': f'GitHub API {e.code}: {e.reason}'}
    except Exception as e:
        return {'success': False, 'runs': [], 'error': str(e)}