from flask import Blueprint

core_blueprint = Blueprint(
    'core_blueprint',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/core_blueprint/static'
)

from . import routes