from flask import Blueprint, jsonify
from extensions import db
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

health_bp = Blueprint('health', __name__)

@health_bp.route('/health/db')
def health_check():
    """Database health check endpoint"""
    try:
        # Simple query to test database connectivity
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': db.session.execute(text('SELECT NOW()')).scalar()
        }), 200
    except OperationalError as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 503
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500