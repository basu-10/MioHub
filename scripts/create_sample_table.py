"""
Create a sample table file for testing Luckysheet integration.
"""
from flask import Flask
from extensions import db
from blueprints.p2.models import File, Folder, User
import config
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    # Get testuser
    user = User.query.filter_by(username='testuser').first()
    if not user:
        print("❌ User 'testuser' not found!")
        exit(1)
    
    # Get root folder
    folder = Folder.query.filter_by(user_id=user.id, parent_id=None).first()
    if not folder:
        print("❌ Root folder not found!")
        exit(1)
    
    # Create sample table data in Luckysheet format
    table_data = [
        {
            "name": "Inventory",
            "color": "",
            "status": 1,
            "order": 0,
            "data": [
                ["Product", "Quantity", "Price", "Category", "Status"],
                ["Laptop", 5, 999.99, "Electronics", "In Stock"],
                ["Mouse", 25, 29.99, "Accessories", "In Stock"],
                ["Keyboard", 15, 79.99, "Accessories", "In Stock"],
                ["Monitor", 8, 349.99, "Electronics", "Low Stock"],
                ["Headphones", 0, 149.99, "Audio", "Out of Stock"]
            ],
            "config": {
                "columnlen": {
                    "0": 120,
                    "1": 100,
                    "2": 100,
                    "3": 120,
                    "4": 120
                }
            },
            "index": 0
        }
    ]
    
    # Create table file
    table_file = File(
        owner_id=user.id,
        folder_id=folder.id,
        type='table',
        title='Product Inventory',
        content_json=table_data,
        is_public=False,
        metadata_json={"description": "Sample inventory spreadsheet with Luckysheet"}
    )
    
    db.session.add(table_file)
    db.session.commit()
    
    print(f"✅ Created sample table file:")
    print(f"   ID: {table_file.id}")
    print(f"   Title: {table_file.title}")
    print(f"   Type: {table_file.type}")
    print(f"   Rows: {len(table_data[0]['data'])}")
    print(f"   Columns: {len(table_data[0]['data'][0])}")
    print(f"   Size: {table_file.get_content_size()} bytes")
    print(f"\n📊 View at: http://localhost:5555/p2/files/{table_file.id}/view")
    print(f"✏️  Edit at: http://localhost:5555/p2/files/{table_file.id}/edit")
