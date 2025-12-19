from flask import Blueprint

p1_blueprint = Blueprint(
    'p1_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/p1_bp/static'
)

from . import routes