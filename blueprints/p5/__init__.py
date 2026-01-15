from flask import Blueprint

p5_blueprint = Blueprint(
    'p5_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/p5/static'
)

from .extension_api import extension_api_bp
from . import routes
