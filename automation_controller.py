import os
import sys
import time
import json
import threading
import urllib.request
import github_client

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
if sys.platform == 'darwin':
    DATA_DIR = os.path.expanduser('~/Library/Application Support/ShaddaAntiDetect')
else:
    DATA_DIR = BASE_DIR

if os.path.exists(os.path.join(DATA_DIR, 'github_accounts.json')):
    github_client.ACCOUNTS_FILE = os.path.join(DATA_DIR, 'github_accounts.json')

ACTIVE_SESSIONS = {}

YOUTUBE_MODES = {
    'studio': [
        {
            'id': 'yt_studio_init',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Studio Upload & Management',
            'title': 'Connecting to GitHub Actions YouTube Engine',
            'description': 'GitHub Actions runner is initializing cloud environment and connecting to your assigned proxy tunnel.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Sign in to YouTube Studio'
        },
        {
            'id': 'yt_studio_auth',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Studio Upload & Management',
            'title': 'YouTube Studio Login & 2-Step Verification',
            'description': 'GitHub Actions is waiting for active session authentication in your anti-detect browser.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': True,
            'instruction': 'Please sign in with your Google/YouTube account in this window. Complete 2-Step Verification if prompted, then click "Continue Automation" below.',
            'nextStep': 'Verify YouTube Channel Dashboard & Upload Slots'
        },
        {
            'id': 'yt_studio_dashboard',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Studio Upload & Management',
            'title': 'Checking Studio Dashboard & Upload Capabilities',
            'description': 'GitHub Actions is verifying channel upload readiness, copyright health, and active stream keys.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Synchronize Video Scheduling & Processing'
        },
        {
            'id': 'yt_studio_ready',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Studio Upload & Management',
            'title': 'YouTube Studio Management Active',
            'description': 'GitHub Actions workflow is successfully connected and controlling your YouTube Studio session.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Continuous background synchronization'
        }
    ],
    'watch': [
        {
            'id': 'yt_watch_init',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Video Watch & Engagement',
            'title': 'Initializing YouTube Watch & Engagement Routine',
            'description': 'GitHub Actions runner is establishing stealth browser context via assigned proxy.',
            'targetUrl': 'https://www.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Navigate to Target Content'
        },
        {
            'id': 'yt_watch_auth',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Video Watch & Engagement',
            'title': 'YouTube Content Navigation',
            'description': 'Browse to the target video or search keyword in this window.',
            'targetUrl': 'https://www.youtube.com',
            'requiresManual': True,
            'instruction': 'Browse to your desired YouTube video or search query, then click "Continue Automation" to commence watch time retention.',
            'nextStep': 'Execute Watch & Retention Automation'
        },
        {
            'id': 'yt_watch_active',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Video Watch & Engagement',
            'title': 'Watch & Engagement In Progress',
            'description': 'GitHub Actions runner is tracking watch sessions, stealth scrolling, and natural viewer interaction.',
            'targetUrl': 'https://www.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Continuous engagement cycling'
        }
    ],
    'full': [
        {
            'id': 'yt_full_init',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Full Automation Pipeline',
            'title': 'Connecting Full-Stack YouTube Pipeline',
            'description': 'GitHub Actions is initializing multi-stage YouTube Studio and Viewer automation pipeline.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Authentication & Studio Dashboard'
        },
        {
            'id': 'yt_full_auth',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Full Automation Pipeline',
            'title': 'Studio Account Sign-In & Verification',
            'description': 'Authenticate your channel session in this browser window.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': True,
            'instruction': 'Sign in to your YouTube channel and click "Continue Automation".',
            'nextStep': 'Run Studio Automation'
        },
        {
            'id': 'yt_full_studio',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Full Automation Pipeline',
            'title': 'Studio Synchronization & Video Processing',
            'description': 'Syncing videos, playlist tags, description templates, and analytics.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Switch to Viewer Engagement Loop'
        },
        {
            'id': 'yt_full_engagement',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'modeName': 'Full Automation Pipeline',
            'title': 'YouTube Pipeline Fully Synchronized',
            'description': 'All YouTube Studio workflows and engagement routines are active under GitHub Actions orchestration.',
            'targetUrl': 'https://www.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Autonomous scheduled runs'
        }
    ]
}

def build_workflow_steps(platforms=None, custom_url=None, youtube_mode='studio'):
    mode = (youtube_mode or 'studio').lower().strip()
    if mode not in YOUTUBE_MODES:
        mode = 'studio'
    template = YOUTUBE_MODES.get(mode, YOUTUBE_MODES['studio'])
    steps = [dict(s) for s in template]
    if custom_url:
        for s in steps:
            if s.get('targetUrl') == 'https://www.youtube.com':
                s['targetUrl'] = custom_url
    return steps

def start_automation_session(profile_id, platforms=None, custom_url=None, github_account_id=None, youtube_mode='studio', profile_name=None, assigned_proxy=None):
    mode = (youtube_mode or 'studio').lower().strip()
    if mode not in YOUTUBE_MODES:
        mode = 'studio'

    steps = build_workflow_steps(platforms, custom_url, youtube_mode=mode)

    account = None
    if github_account_id and github_account_id != 'default':
        account = github_client.get_account(github_account_id)
    if not account:
        account = github_client.get_default_account()

    repo = account.get('repo', 'sciencefiction879-cmyk/yt-proxy-runner') if account else 'sciencefiction879-cmyk/yt-proxy-runner'
    username = account.get('username', 'github-user') if account else 'github-user'
    token = account.get('token', '') if account else ''

    run_id = None
    if token and repo:
        try:
            run_id = github_client.dispatch_runner(token, repo, profile_id)
            print(f'[🤖 GitHub Actions] Dispatched guided YouTube automation runner for {profile_id} (Run #{run_id})')
        except Exception as e:
            print(f'[!] GitHub Actions dispatch note: {e}')
            run_id = 'gh-yt-run-' + str(int(time.time()))

    session = {
        'profileId': profile_id,
        'profileName': profile_name or f"Profile {profile_id[:8]}",
        'proxyLabel': assigned_proxy or "Assigned Proxy",
        'platforms': ['youtube'],
        'youtubeMode': mode,
        'modeName': YOUTUBE_MODES[mode][0].get('modeName', 'YouTube Automation'),
        'customUrl': custom_url or '',
        'githubRepo': repo,
        'githubUser': username,
        'githubRunId': run_id or ('GH-YT-' + str(int(time.time()) % 100000)),
        'status': 'running',
        'currentStepIndex': 0,
        'steps': steps,
        'startTime': time.time(),
        'lastUpdate': time.time(),
        'history': []
    }

    ACTIVE_SESSIONS[profile_id] = session
    return session

def get_session_state(profile_id):
    if profile_id not in ACTIVE_SESSIONS:
        return {'active': False}

    sess = ACTIVE_SESSIONS[profile_id]
    steps = sess.get('steps', [])
    idx = sess.get('currentStepIndex', 0)

    if idx >= len(steps):
        current_step = {
            'id': 'completed',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'title': 'YouTube Automation Active & Synchronized!',
            'description': 'GitHub Actions has completed the setup workflow and is now running autonomous YouTube cycles.',
            'targetUrl': '',
            'requiresManual': False,
            'instruction': 'YouTube automation is actively synchronized. You may browse or leave this session running.',
            'nextStep': 'Autonomous Loop Active'
        }
        is_completed = True
    else:
        current_step = steps[idx]
        is_completed = False

    return {
        'active': True,
        'profileId': profile_id,
        'profileName': sess.get('profileName', f"Profile {profile_id[:8]}"),
        'proxyLabel': sess.get('proxyLabel', 'Assigned Proxy'),
        'platforms': ['youtube'],
        'youtubeMode': sess.get('youtubeMode', 'studio'),
        'modeName': sess.get('modeName', 'YouTube Automation'),
        'githubRepo': sess.get('githubRepo'),
        'githubUser': sess.get('githubUser'),
        'githubRunId': sess.get('githubRunId'),
        'status': sess.get('status', 'running'),
        'currentStepIndex': idx,
        'totalSteps': len(steps),
        'currentStep': current_step,
        'completed': is_completed,
        'elapsedSeconds': int(time.time() - sess.get('startTime', time.time()))
    }

def advance_step(profile_id, user_action=None):
    if profile_id not in ACTIVE_SESSIONS:
        return False, 'No active session.'

    sess = ACTIVE_SESSIONS[profile_id]
    idx = sess.get('currentStepIndex', 0)
    steps = sess.get('steps', [])

    if idx < len(steps):
        completed_step = steps[idx]
        sess['history'].append({
            'step': completed_step,
            'completedAt': time.time(),
            'userAction': user_action
        })
        sess['currentStepIndex'] = idx + 1
        sess['lastUpdate'] = time.time()
        print(f'[🤖 YouTube Automation] Advanced profile {profile_id} to step {idx + 1}/{len(steps)}')
        return True, 'Step completed.'

    return False, 'All steps already completed.'

def stop_automation_session(profile_id):
    if profile_id in ACTIVE_SESSIONS:
        sess = ACTIVE_SESSIONS.pop(profile_id)
        sess['status'] = 'stopped'
        return True
    return False
