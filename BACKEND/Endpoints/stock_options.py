# pyrefly: ignore [missing-import]
import traceback
from flask import Blueprint, request, jsonify, current_app, g
from flask_cors import cross_origin
from invest.options_service import OptionsService
from invest.routes import cache   # reuse the app-initialized cache instance

stock_options_bp = Blueprint("stock_options_bp", __name__)

@stock_options_bp.route("/options/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def options_chain(symbol):
    """
    Production-ready options route that proxies the Node.js NSE Options service.
    Includes caching, error handling, and expiry filtering.
    """
    symbol = symbol.upper()
    target_expiry = request.args.get("expiry")

    try:
        # 1. Fetch data from Node.js Service (with caching)
        # We cache the full chain for the symbol to avoid redundant service calls
        cache_key = f"options_full_{symbol}"
        result = cache.get(cache_key)

        if not result:
            result = OptionsService.get_options_chain(symbol)
            if result.get("success"):
                cache.set(cache_key, result, timeout=300)  # 5 minute cache
        
        if not result.get("success"):
            return jsonify({
                "success": False,
                "error": result.get("error", "Failed to fetch options data")
            }), 502

        # 2. Normalize and Filter by Expiry
        normalized = OptionsService.normalize_options_data(
            result.get("data", []), 
            target_expiry=target_expiry
        )

        if not normalized:
            return jsonify({
                "success": False,
                "error": f"No options data found for {symbol}"
            }), 404

        # 3. Return Clean JSON
        return jsonify({
            "success": True,
            "symbol": symbol,
            "available_expiries": normalized["available_expiries"],
            "selected_expiry": normalized["selected_expiry"],
            "total_rows": normalized["total_rows"],
            "data": normalized["data"]
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": "Internal server error while processing options"
        }), 500

