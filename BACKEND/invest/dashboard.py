from flask import Blueprint, jsonify, current_app, g
from .portfolio import get_dashboard_data
from .auth import require_user as auth_required

# Create a Blueprint for dashboard-related routes
dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard/<int:userid>", methods=["GET"])
@auth_required
def dashboard_route(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    try:
        data = get_dashboard_data(userid)
        if "error" in data:
            return jsonify(data), 404
        return jsonify(data)
    except Exception as e:
        current_app.logger.exception(f"Error in /dashboard/{userid}: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500
