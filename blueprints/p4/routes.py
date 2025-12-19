from . import p4_blueprint
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

@p4_blueprint.route('/product4')
def product4():
    return render_template('p4/home.html')

@p4_blueprint.route('/p4_admin_dashboard')
@login_required
def p4_admin_dashboard():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))

    return render_template('p4/p4_admin_dashboard.html')