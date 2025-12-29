"""
Delete all existing MioBook documents (proprietary_blocks type files)
since we're moving to v2.0 with annotation support and no backward compatibility needed
"""

from flask import Flask
from extensions import db
from blueprints.p2.models import File
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    # Find all MioBook files (proprietary_blocks type)
    miobooks = File.query.filter_by(type='proprietary_blocks').all()
    
    print(f"Found {len(miobooks)} MioBook documents to delete:")
    for book in miobooks:
        print(f"  - ID: {book.id}, Title: {book.title}, Owner: {book.owner_id}")
    
    if miobooks:
        confirm = input("\n⚠️  Delete all these MioBook documents? This CANNOT be undone! (yes/no): ")
        
        if confirm.lower() == 'yes':
            for book in miobooks:
                db.session.delete(book)
            
            db.session.commit()
            print(f"\n✅ Successfully deleted {len(miobooks)} MioBook documents")
            print("📝 All MioBook documents have been removed from the database")
            print("🎉 Ready for v2.0 with annotation support!")
        else:
            print("\n❌ Deletion cancelled")
    else:
        print("\n✨ No MioBook documents found in database")
        print("🎉 Database is ready for v2.0!")
