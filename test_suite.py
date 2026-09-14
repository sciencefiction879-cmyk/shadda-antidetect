import os
import sys
import time
import json
import threading
import urllib.request
import urllib.parse
import unittest

import automation_controller
import browser_runner
import server

class ComprehensiveSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start server on test port 5058
        cls.test_port = 5058
        server.PORT = cls.test_port
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', cls.test_port), server.ProfileHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_01_automation_controller_steps(self):
        """Test step generation for multiple platforms including custom 'other'"""
        platforms = ['youtube', 'facebook', 'other']
        custom_url = 'https://mysite.com/portal'
        steps = automation_controller.build_workflow_steps(platforms, custom_url)
        
        self.assertGreater(len(steps), 0)
        platform_names = [s['platform'] for s in steps]
        self.assertIn('youtube', platform_names)
        self.assertIn('facebook', platform_names)
        self.assertIn('other', platform_names)
        
        # Verify custom targetUrl was properly injected
        other_steps = [s for s in steps if s['platform'] == 'other']
        for s in other_steps:
            self.assertEqual(s['targetUrl'], custom_url)

    def test_02_automation_session_lifecycle(self):
        """Test start, state query, step advancement, and stop lifecycle"""
        pid = "test_profile_auto_1"
        platforms = ['youtube', 'tiktok']
        sess = automation_controller.start_automation_session(pid, platforms)
        
        self.assertEqual(sess['profileId'], pid)
        self.assertEqual(sess['status'], 'running')
        
        # Query state
        st = automation_controller.get_session_state(pid)
        self.assertTrue(st['active'])
        self.assertEqual(st['currentStepIndex'], 0)
        self.assertFalse(st['completed'])
        first_step = st['currentStep']
        self.assertEqual(first_step['id'], 'yt_init')
        
        # Advance step
        ok, msg = automation_controller.advance_step(pid, user_action='continue')
        self.assertTrue(ok)
        st2 = automation_controller.get_session_state(pid)
        self.assertEqual(st2['currentStepIndex'], 1)
        self.assertEqual(st2['currentStep']['id'], 'yt_auth')
        self.assertTrue(st2['currentStep']['requiresManual'])
        
        # Stop session
        stopped = automation_controller.stop_automation_session(pid)
        self.assertTrue(stopped)
        st_stopped = automation_controller.get_session_state(pid)
        self.assertFalse(st_stopped['active'])

    def test_03_chrome_launch_flags_no_resolver_conflict(self):
        """Ensure --host-resolver-rules is NOT added, preventing ERR_CONNECTION_CLOSED"""
        with open('browser_runner.py', 'r', encoding='utf-8') as f:
            src = f.read()
        self.assertNotIn('--host-resolver-rules', src, "browser_runner.py must not contain --host-resolver-rules")

    def test_04_extension_files_and_manifest(self):
        """Verify extension files exist and manifest includes automation_hud.js"""
        manifest_path = os.path.join('anti_detect_extension', 'manifest.json')
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        content_scripts = manifest.get('content_scripts', [])
        all_js = []
        for cs in content_scripts:
            all_js.extend(cs.get('js', []))
        self.assertIn('automation_hud.js', all_js)
        
        for js_file in all_js:
            p = os.path.join('anti_detect_extension', js_file)
            self.assertTrue(os.path.exists(p), f"Extension file {p} must exist")

    def test_05_server_api_profiles_and_automation(self):
        """Test HTTP API endpoints for profiles and automation state"""
        base = f"http://127.0.0.1:{self.test_port}"
        
        # 1. Fetch profiles
        req = urllib.request.Request(f"{base}/api/profiles")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            profiles = json.loads(resp.read().decode('utf-8'))
            self.assertIsInstance(profiles, list)

        # 2. Create profile with automation config
        new_prof = {
            'name': 'Auto Test Runner Profile',
            'proxyType': 'none',
            'automation': {
                'enabled': True,
                'platforms': ['youtube', 'x'],
                'customUrl': ''
            }
        }
        post_req = urllib.request.Request(
            f"{base}/api/profiles",
            data=json.dumps(new_prof).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(post_req) as resp:
            self.assertEqual(resp.status, 200)
            created = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(created.get('success'))
            pid = created['profile']['id']

        # 3. Start automation session via API
        start_req = urllib.request.Request(
            f"{base}/api/automation/{pid}/start",
            data=json.dumps({'platforms': ['youtube', 'twitter']}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(start_req) as resp:
            self.assertEqual(resp.status, 200)
            start_res = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(start_res.get('success'))

        # 4. Check active session API
        active_req = urllib.request.Request(f"{base}/api/automation/{pid}/state")
        with urllib.request.urlopen(active_req) as resp:
            self.assertEqual(resp.status, 200)
            state_data = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(state_data.get('active'))
            self.assertEqual(state_data.get('profileId'), pid)

        # 5. Action continue API
        act_req = urllib.request.Request(
            f"{base}/api/automation/{pid}/action",
            data=json.dumps({'action': 'continue'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(act_req) as resp:
            self.assertEqual(resp.status, 200)
            act_res = json.loads(resp.read().decode('utf-8'))
            self.assertTrue(act_res.get('success'))

        # Clean up session
        automation_controller.stop_automation_session(pid)

    def test_06_profile_launch_and_close_restoration(self):
        """Test profile launching, running detection, and clean button restoration on close"""
        base = f"http://127.0.0.1:{self.test_port}"
        pid = "test_window_close_pid"
        prof = {
            'id': pid,
            'name': 'Close Detect Profile',
            'proxyType': 'none',
            'startUrl': 'https://example.com'
        }
        
        # Launch browser
        ok, msg = browser_runner.launch_profile_browser(prof, url_override='https://example.com')
        self.assertTrue(ok)
        self.assertTrue(browser_runner.is_profile_running(pid))
        
        # Check via API
        req = urllib.request.Request(f"{base}/api/profiles")
        with urllib.request.urlopen(req) as resp:
            profiles = json.loads(resp.read().decode('utf-8'))
            for p in profiles:
                if p.get('id') == pid:
                    self.assertTrue(p.get('isRunning'))

        # Terminate / Stop browser
        stopped = browser_runner.stop_profile_browser(pid)
        self.assertTrue(stopped)
        time.sleep(1.0)
        self.assertFalse(browser_runner.is_profile_running(pid))

        # Check API status restored
        req2 = urllib.request.Request(f"{base}/api/profiles")
        with urllib.request.urlopen(req2) as resp:
            profiles = json.loads(resp.read().decode('utf-8'))
            for p in profiles:
                if p.get('id') == pid:
                    self.assertFalse(p.get('isRunning'))


if __name__ == '__main__':
    unittest.main()
