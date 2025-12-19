#!/usr/bin/env python3
"""
Simple script to test autosave_draft endpoint by logging in and posting a draft with title only.
"""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from flask_app import app

USERNAME = 'alice_smith'
PASSWORD = 'password123'

with app.test_client() as client:
    # Login
    resp = client.post('/login', data={'username': USERNAME, 'password': PASSWORD}, follow_redirects=True)
    print('Login status:', resp.status_code)
    # Post draft with title only
    resp = client.post('/autosave_draft', data={'title': 'Title Only Draft', 'content': ''})
    print('Autosave draft response code:', resp.status_code)
    try:
        print('JSON:', resp.get_json())
    except Exception as e:
        print('Failed to parse JSON:', e)


print('Done')
