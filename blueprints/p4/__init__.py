from flask import Blueprint

p4_blueprint = Blueprint(
    'p4_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/p4_bp/static'
)

from . import routes