from flask import Blueprint

p3_blueprint = Blueprint(
    'p3_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/p3/static'
)

from . import routes, models