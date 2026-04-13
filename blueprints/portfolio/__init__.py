from flask import Blueprint

portfolio_blueprint = Blueprint(
    'portfolio_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/portfolio_bp/static'
)

from . import routes
