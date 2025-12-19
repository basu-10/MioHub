from . import p1_blueprint
from flask import render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user

@p1_blueprint.route('/product1')
def product1():
    return render_template('p1/home.html')

@p1_blueprint.route('/p1_admin_dashboard')
@login_required
def p1_admin_dashboard():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    # Calculator admin data
    calculator_functions = [
        {'name': 'Basic Math', 'description': 'Addition, subtraction, multiplication, division'},
        {'name': 'Power Operations', 'description': 'Exponentiation (^) and roots'},
        {'name': 'Business Functions', 'description': 'profit(cp, sp), tax(amount, rate), markup(cp, percent)'},
        {'name': 'Math Constants', 'description': 'pi, e'},
        {'name': 'Math Functions', 'description': 'sqrt, cbrt, log, ln'}
    ]
    
    return render_template('p1/p1_admin_dashboard.html', calculator_functions=calculator_functions)


@p1_blueprint.route("/clear", methods=["POST"])
def clear():
    session["history"] = []
    return redirect(url_for('p1_bp.product1'))


