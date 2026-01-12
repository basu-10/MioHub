from .core import core_blueprint
from .p1 import p1_blueprint
from .p2 import p2_blueprint, notes_bp, whiteboard_bp, folder_bp, combined_bp, file_bp, infinite_whiteboard_bp, graph_bp, extension_api_bp
from .p3 import p3_blueprint
from .p4 import p4_blueprint
from .auth import auth_blueprint
from .health import health_bp

bps=[core_blueprint, p1_blueprint, p2_blueprint, notes_bp, whiteboard_bp, folder_bp, combined_bp, file_bp, infinite_whiteboard_bp, graph_bp, extension_api_bp, p3_blueprint, p4_blueprint, auth_blueprint, health_bp]    

