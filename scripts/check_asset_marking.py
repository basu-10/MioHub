"""
Simple test script to exercise asset mark/unmark flow against a running app.
Adjust `base` and `username`/`password` as needed.

Usage:
  python scripts/check_asset_marking.py
"""

import requests, io, sys

base = 'http://127.0.0.1:5555'
username = 'testuser'
password = 'password123'  # Replace with real test user

s = requests.Session()

def login():
    resp = s.post(base + '/login', data={'username': username, 'password': password})
    print('Login:', resp.status_code)
    return resp

def upload_image():
    png = b'\x89PNG\r\n\x1a\n' + b'\x00' * 2048
    files = [('files', ('test.png', io.BytesIO(png), 'image/png'))]
    resp = s.post(base + '/assets/upload', files=files)
    print('Upload:', resp.status_code)
    try:
        print(resp.json())
    except Exception as e:
        print('No JSON', e)
        print(resp.text[:400])
    return resp


def list_assets():
    resp = s.get(base + '/assets/list')
    print('assets/list', resp.status_code)
    try:
        data = resp.json()
        for img in data.get('images', []):
            print(img.get('filename'), 'used_in:', img.get('used_in'))
        return data
    except Exception as e:
        print('No JSON', e)
        print(resp.text[:400])
        return None


def mark_used(filename):
    resp = s.post(base + '/assets/mark_used', json={'filename': filename})
    print('mark_used', resp.status_code, resp.text)
    return resp


def unmark_used(filename):
    resp = s.post(base + '/assets/unmark_used', json={'filename': filename})
    print('unmark_used', resp.status_code, resp.text)
    return resp


if __name__ == '__main__':
    if login().status_code != 200:
        print('Failed login; aborting')
        sys.exit(1)
    upload_resp = upload_image()
    try:
        fname = upload_resp.json().get('uploaded', [])[0].get('filename')
    except Exception as e:
        print('Could not determine uploaded filename', e)
        sys.exit(1)

    list_assets()
    mark_used(fname)
    list_assets()
    unmark_used(fname)
    list_assets()
