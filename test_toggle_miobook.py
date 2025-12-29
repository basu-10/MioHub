#!/usr/bin/env python
"""Test script to toggle MioBook file 160 to public"""

from flask_app import app
from blueprints.p2.models import File
from extensions import db

with app.app_context():
    # Get MioBook file 160
    miobook = File.query.get(160)
    if not miobook:
        print("MioBook file 160 not found")
        exit(1)
    
    print(f"MioBook: {miobook.title}")
    print(f"Type: {miobook.type}")
    print(f"Owner ID: {miobook.owner_id}")
    print(f"Current is_public: {miobook.is_public}")
    print()
    
    # Toggle to public
    miobook.is_public = True
    db.session.commit()
    
    print("✓ MioBook toggled to public")
    print(f"New is_public value: {miobook.is_public}")
    print()
    print("Now check http://192.168.1.6:5555/users/3 - the MioBook should appear!")
