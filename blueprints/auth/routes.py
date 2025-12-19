from . import auth_blueprint
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user

@auth_blueprint.route('/admin_central')
@login_required
def admin_central():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    return render_template('auth/admin_central.html')