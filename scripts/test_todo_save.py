"""Test script to verify todo save works with notification system."""

import requests
import json

BASE_URL = "http://127.0.0.1:5555"

# Login first
session = requests.Session()

# Login as testuser
login_data = {
    'username': 'testuser',
    'password': 'password123'
}
response = session.post(f"{BASE_URL}/auth/login", data=login_data)
print(f"Login status: {response.status_code}")

# Get user's folder view to find a todo file (or create one)
response = session.get(f"{BASE_URL}/p2/folder_view")
print(f"Folder view status: {response.status_code}")

# Test creating a new todo file
print("\n=== Testing Todo Create ===")
create_data = {
    'title': 'Test Todo List',
    'description': 'Testing todo save',
    'todo_data': json.dumps([
        {'text': 'Task A', 'done': False},
        {'text': 'Task B', 'done': True},
        {'text': 'Task C', 'done': False}
    ])
}
response = session.post(
    f"{BASE_URL}/p2/files/new/todo",
    data=create_data,
    headers={'X-Requested-With': 'XMLHttpRequest'}
)
print(f"Create status: {response.status_code}")
print(f"Response: {response.text[:200]}")

if response.status_code == 200:
    result = response.json()
    if result.get('success'):
        file_id = result.get('file_id')
        print(f"✓ Todo created successfully! File ID: {file_id}")
        
        # Now test editing/saving the todo
        print("\n=== Testing Todo Save ===")
        save_data = {
            'todo_data': json.dumps([
                {'text': 'Updated task a', 'done': False},
                {'text': 'Updated task b', 'done': False},
                {'text': 'Updated task c', 'done': True}
            ])
        }
        response = session.post(
            f"{BASE_URL}/p2/files/{file_id}/edit",
            data=save_data,
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        print(f"Save status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✓ Todo saved successfully! No flash message error!")
            else:
                print(f"✗ Save failed: {result.get('error')}")
        else:
            print(f"✗ HTTP error: {response.status_code}")
    else:
        print(f"✗ Create failed: {result.get('error')}")
else:
    print(f"✗ HTTP error: {response.status_code}")

# Check telemetry for notifications
print("\n=== Checking Telemetry Notifications ===")
response = session.get(f"{BASE_URL}/p2/api/telemetry_data")
if response.status_code == 200:
    telemetry = response.json()
    notifications = telemetry.get('recent_notifications', [])
    print(f"Found {len(notifications)} recent notifications:")
    for notif in notifications[:5]:
        print(f"  - [{notif['type']}] {notif['message']}")
else:
    print(f"✗ Telemetry fetch failed: {response.status_code}")

print("\n=== Test Complete ===")
