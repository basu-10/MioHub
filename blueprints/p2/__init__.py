from flask import Blueprint

p2_blueprint = Blueprint(
    'p2_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/p2_bp/static'
)

notes_bp = Blueprint('notes', __name__)
whiteboard_bp = Blueprint('boards', __name__, url_prefix='/boards')
folder_bp = Blueprint('folders', __name__, url_prefix='/folders')
combined_bp = Blueprint('combined', __name__, url_prefix='/combined')
file_bp = Blueprint('file', __name__, url_prefix='/p2')
graph_bp = Blueprint('graph', __name__, url_prefix='/graph')

# Import infinite whiteboard routes to get the blueprint
from .infinite_whiteboard_routes import infinite_whiteboard_bp

# import all route modules to register their endpoints
from . import whiteboard_routes
from . import infinite_whiteboard_routes
from . import notes_route
from . import folder_routes
from . import combined_routes
from . import file_routes
from . import utils
from . import routes
from . import folder_bp
from . import graph_routes