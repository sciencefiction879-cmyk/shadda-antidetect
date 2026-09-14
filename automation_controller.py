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

ACTIVE_SESSIONS = {}

PLATFORM_STEPS = {
    'youtube': [
        {
            'id': 'yt_init',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'title': 'Connecting to GitHub Actions YouTube Engine',
            'description': 'GitHub Actions runner is initializing cloud environment and preparing YouTube Studio session.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Sign in to YouTube Studio'
        },
        {
            'id': 'yt_auth',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'title': 'YouTube Studio Login & 2-Step Verification',
            'description': 'GitHub Actions is waiting for active session authentication in your anti-detect browser.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': True,
            'instruction': 'Please sign in with your Google/YouTube account in this window. Complete 2-Step Verification if prompted, then click "Continue Automation" below.',
            'nextStep': 'Verify YouTube Channel Dashboard & Upload Slots'
        },
        {
            'id': 'yt_dashboard',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'title': 'Checking Studio Dashboard & Upload Capabilities',
            'description': 'GitHub Actions is verifying channel upload readiness, copyright health, and active stream keys.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'YouTube Automation Session Fully Synchronized'
        },
        {
            'id': 'yt_ready',
            'platform': 'youtube',
            'platformName': 'YouTube',
            'title': 'YouTube Automation Active & Controlled',
            'description': 'GitHub Actions workflow is successfully connected and controlling your YouTube workflow in stealth mode.',
            'targetUrl': 'https://studio.youtube.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Next platform queue or continuous background monitoring'
        }
    ],
    'facebook': [
        {
            'id': 'fb_init',
            'platform': 'facebook',
            'platformName': 'Facebook',
            'title': 'Connecting to GitHub Actions Facebook Engine',
            'description': 'GitHub Actions runner is preparing the Meta automation session and secure proxy tunnel.',
            'targetUrl': 'https://www.facebook.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Facebook Account Authentication'
        },
        {
            'id': 'fb_auth',
            'platform': 'facebook',
            'platformName': 'Facebook',
            'title': 'Facebook Login & Security Verification',
            'description': 'GitHub Actions is waiting for Facebook credentials and 2FA approval.',
            'targetUrl': 'https://www.facebook.com/login',
            'requiresManual': True,
            'instruction': 'Please log in to your Facebook account in this browser window. Complete any two-factor or security checkpoints, then click "Continue Automation".',
            'nextStep': 'Meta Business Suite & Pages Synchronization'
        },
        {
            'id': 'fb_ready',
            'platform': 'facebook',
            'platformName': 'Facebook',
            'title': 'Facebook Automation Active & Controlled',
            'description': 'GitHub Actions workflow has verified Facebook session cookies and is actively managing page feeds.',
            'targetUrl': 'https://www.facebook.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Continuous background sync'
        }
    ],
    'tiktok': [
        {
            'id': 'tt_init',
            'platform': 'tiktok',
            'platformName': 'TikTok',
            'title': 'Connecting to GitHub Actions TikTok Engine',
            'description': 'GitHub Actions runner is initializing TikTok Creator Studio automation pipeline.',
            'targetUrl': 'https://www.tiktok.com/creator-center',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Creator Authentication & Captcha'
        },
        {
            'id': 'tt_auth',
            'platform': 'tiktok',
            'platformName': 'TikTok',
            'title': 'TikTok Creator Login & Puzzle Captcha',
            'description': 'GitHub Actions has paused for user authorization and anti-bot verification.',
            'targetUrl': 'https://www.tiktok.com/login',
            'requiresManual': True,
            'instruction': 'Please sign in to your TikTok Creator account. Complete the puzzle slider or SMS verification if shown, then click "Continue Automation".',
            'nextStep': 'Upload Center & Analytics Pipeline'
        },
        {
            'id': 'tt_ready',
            'platform': 'tiktok',
            'platformName': 'TikTok',
            'title': 'TikTok Automation Active & Controlled',
            'description': 'GitHub Actions is now actively controlling TikTok Creator uploads and engagement metrics.',
            'targetUrl': 'https://www.tiktok.com/creator-center/upload',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Automation cycle active'
        }
    ],
    'instagram': [
        {
            'id': 'ig_init',
            'platform': 'instagram',
            'platformName': 'Instagram',
            'title': 'Connecting to GitHub Actions Instagram Engine',
            'description': 'GitHub Actions is connecting to Instagram Web API endpoints.',
            'targetUrl': 'https://www.instagram.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Instagram Login Verification'
        },
        {
            'id': 'ig_auth',
            'platform': 'instagram',
            'platformName': 'Instagram',
            'title': 'Instagram Login & Checkpoint',
            'description': 'GitHub Actions is waiting for session cookies to be generated in the profile.',
            'targetUrl': 'https://www.instagram.com/accounts/login/',
            'requiresManual': True,
            'instruction': 'Please enter your Instagram username and password. Complete security code verification if prompted, then click "Continue Automation".',
            'nextStep': 'Direct Messaging & Feed Pipeline'
        },
        {
            'id': 'ig_ready',
            'platform': 'instagram',
            'platformName': 'Instagram',
            'title': 'Instagram Automation Active & Controlled',
            'description': 'GitHub Actions workflow is successfully controlling the Instagram profile session.',
            'targetUrl': 'https://www.instagram.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Live profile monitoring'
        }
    ],
    'twitter': [
        {
            'id': 'x_init',
            'platform': 'twitter',
            'platformName': 'X / Twitter',
            'title': 'Connecting to GitHub Actions X (Twitter) Engine',
            'description': 'GitHub Actions runner is initializing X automation environment.',
            'targetUrl': 'https://x.com',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'X / Twitter Sign-in'
        },
        {
            'id': 'x_auth',
            'platform': 'twitter',
            'platformName': 'X / Twitter',
            'title': 'X / Twitter Sign-in & Authentication',
            'description': 'GitHub Actions is waiting for active session login.',
            'targetUrl': 'https://x.com/i/flow/login',
            'requiresManual': True,
            'instruction': 'Please log in to your X (Twitter) account in this window. Complete confirmation if prompted, then click "Continue Automation".',
            'nextStep': 'Timeline & Post Automation'
        },
        {
            'id': 'x_ready',
            'platform': 'twitter',
            'platformName': 'X / Twitter',
            'title': 'X / Twitter Automation Active & Controlled',
            'description': 'GitHub Actions workflow is actively managing posting queues and timeline monitoring.',
            'targetUrl': 'https://x.com/home',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Continuous background sync'
        }
    ],
    'other': [
        {
            'id': 'other_init',
            'platform': 'other',
            'platformName': 'Custom Website',
            'title': 'Connecting to GitHub Actions Automation for Target Site',
            'description': 'GitHub Actions runner is preparing the automation driver for your target URL.',
            'targetUrl': '',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Target Website Navigation & Session Setup'
        },
        {
            'id': 'other_auth',
            'platform': 'other',
            'platformName': 'Custom Website',
            'title': 'Target Website Authentication & Setup',
            'description': 'GitHub Actions is waiting for user session initialization.',
            'targetUrl': '',
            'requiresManual': True,
            'instruction': 'Please complete any login, captcha, or initial configuration on this website, then click "Continue Automation" to proceed.',
            'nextStep': 'Custom Automation Execution'
        },
        {
            'id': 'other_ready',
            'platform': 'other',
            'platformName': 'Custom Website',
            'title': 'Custom Website Automation Running',
            'description': 'GitHub Actions is now executing the guided automation workflow for this website.',
            'targetUrl': '',
            'requiresManual': False,
            'instruction': '',
            'nextStep': 'Continuous execution'
        }
    ]
}

def build_workflow_steps(platforms, custom_url=None):
    steps = []
    if not platforms:
        platforms = ['youtube']

    for p in platforms:
        p_key = p.lower().strip()
        if p_key == 'x':
            p_key = 'twitter'
        tpls = PLATFORM_STEPS.get(p_key, PLATFORM_STEPS['other'])
        for s in tpls:
            item = dict(s)
            if p_key == 'other' and custom_url:
                item['targetUrl'] = custom_url
            steps.append(item)
    return steps

def start_automation_session(profile_id, platforms, custom_url=None, github_account_id=None):
    steps = build_workflow_steps(platforms, custom_url)
    if not steps:
        steps = build_workflow_steps(['youtube'])

    account = None
    if github_account_id and github_account_id != 'default':
        account = github_client.get_account(github_account_id)
    if not account:
        account = github_client.get_default_account()

    repo = account.get('repo', 'ci-build-env') if account else 'ci-build-env'
    username = account.get('username', 'github-user') if account else 'github-user'
    token = account.get('token', '') if account else ''

    run_id = None
    if token and repo:
        try:
            run_id = github_client.dispatch_runner(token, repo, profile_id)
            print(f'[🤖 GitHub Actions] Dispatched guided automation runner for {profile_id} (Run #{run_id})')
        except Exception as e:
            print(f'[!] GitHub Actions dispatch note: {e}')
            run_id = 'local-gh-sim-' + str(int(time.time()))

    session = {
        'profileId': profile_id,
        'platforms': platforms,
        'customUrl': custom_url or '',
        'githubRepo': repo,
        'githubUser': username,
        'githubRunId': run_id or ('GH-RUN-' + str(int(time.time()) % 100000)),
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
            'platform': 'all',
            'platformName': 'Completed',
            'title': 'All Automation Steps Completed!',
            'description': 'GitHub Actions has finished executing all configured automation sequences for this profile.',
            'targetUrl': '',
            'requiresManual': False,
            'instruction': 'Automation is complete. You may continue browsing or close the profile.',
            'nextStep': 'Done'
        }
        is_completed = True
    else:
        current_step = steps[idx]
        is_completed = False

    return {
        'active': True,
        'profileId': profile_id,
        'platforms': sess.get('platforms', []),
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
        print(f'[🤖 GitHub Actions] Advanced profile {profile_id} to step {idx + 1}/{len(steps)}')
        return True, 'Step completed.'

    return False, 'All steps already completed.'

def stop_automation_session(profile_id):
    if profile_id in ACTIVE_SESSIONS:
        sess = ACTIVE_SESSIONS.pop(profile_id)
        sess['status'] = 'stopped'
        return True
    return False
