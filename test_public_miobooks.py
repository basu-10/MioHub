#!/usr/bin/env python
"""Test script to check public MioBook files for user 3"""

from flask_app import app
from blueprints.p2.models import File, User

with app.app_context():
    user = User.query.get(3)
    if not user:
        print("User 3 not found")
        exit(1)
    
    print(f"User: {user.username}")
    print(f"User type: {user.user_type}")
    print()
    
    # Check all MioBook files
    all_miobooks = File.query.filter_by(owner_id=user.id, type='proprietary_blocks').all()
    print(f"Total MioBook files: {len(all_miobooks)}")
    
    # Check public MioBook files
    public_miobooks = File.query.filter_by(owner_id=user.id, type='proprietary_blocks', is_public=True).all()
    print(f"Public MioBook files: {len(public_miobooks)}")
    print()
    
    if public_miobooks:
        print("Public MioBlocks:")
        for f in public_miobooks:
            print(f"  - ID {f.id}: {f.title}")
            print(f"    Type: {f.type}")
            print(f"    Public: {f.is_public}")
            print(f"    Folder ID: {f.folder_id}")
    else:
        print("No public MioBook files found")
        if all_miobooks:
            print("\nAll MioBlocks (not public):")
            for f in all_miobooks:
                print(f"  - ID {f.id}: {f.title} (public={f.is_public})")
