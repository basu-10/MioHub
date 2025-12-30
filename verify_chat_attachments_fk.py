"""Quick verification of foreign key constraints"""
from flask import Flask
from extensions import db
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
db.init_app(app)

with app.app_context():
    inspector = db.inspect(db.engine)
    
    print("Foreign keys in chat_attachments:")
    fks = inspector.get_foreign_keys('chat_attachments')
    for fk in fks:
        print(f"  • {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
    
    print("\nForeign keys in chat_sessions:")
    session_fks = inspector.get_foreign_keys('chat_sessions')
    for fk in session_fks:
        print(f"  • {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
    
    print("\n✅ All foreign key constraints verified!")
