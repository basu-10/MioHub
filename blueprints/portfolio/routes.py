from datetime import datetime

from flask import render_template, request, flash, redirect, url_for

from . import portfolio_blueprint
from .data import AUTHOR, SECTIONS


def _ctx():
    """Common template context shared by every portfolio page."""
    return {"author": AUTHOR, "sections": SECTIONS, "now": datetime.utcnow()}


def _find_product(product_id):
    for section in SECTIONS:
        for p in section["products"]:
            if p["id"] == product_id:
                return p
    return None


# ── Routes ───────────────────────────────────────────────────────────────────

@portfolio_blueprint.route('/portfolio')
def portfolio():
    return render_template('portfolio/portfolio_apps.html', **_ctx())


@portfolio_blueprint.route('/portfolio/about')
def about():
    return render_template('portfolio/about.html', **_ctx())


@portfolio_blueprint.route('/portfolio/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Basic server-side validation at the boundary
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash('Please fill in all fields.', 'error')
        else:
            # TODO: send email / store in DB
            flash('Message sent! I\'ll get back to you soon.', 'success')
            return redirect(url_for('portfolio_bp.contact'))

    return render_template('portfolio/contact.html', **_ctx())


@portfolio_blueprint.route('/portfolio/product/<product_id>')
def product(product_id):
    p = _find_product(product_id)
    if p is None:
        return render_template('portfolio/404.html', **_ctx()), 404
    return render_template('portfolio/product.html', product=p, **_ctx())

