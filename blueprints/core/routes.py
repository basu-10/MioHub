from . import core_blueprint
from flask import render_template

@core_blueprint.route("/")
def landing():
    return render_template("core/index.html")
    # session.permanent = True  # Make session persistent
    # # Initialize history if not present
    # if "history" not in session:
    #     session["history"] = []
    # return render_template("index.html", history=session["history"])




@core_blueprint.route('/about')
def about():
    return render_template('core/about.html')


@core_blueprint.route('/features/p1')
def features_p1():
    return render_template('core/features_p1.html')


@core_blueprint.route('/features/p2')
def features_p2():
    return render_template('core/features_p2.html')


@core_blueprint.route('/features/p3')
def features_p3():
    return render_template('core/features_p3.html')


@core_blueprint.route('/features/p4')
def features_p4():
    return render_template('core/features_p4.html')