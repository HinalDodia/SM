import os
import requests
import logging

# Configure logging
logger = logging.getLogger(__name__)

class OptionsService:
    """
    Service class to interact with the Node.js Options Microservice.
    """
    
    BASE_URL = os.environ.get("OPTIONS_SERVICE_URL", "http://localhost:5001")
    TIMEOUT = 10  # seconds

    @staticmethod
    def get_options_chain(symbol):
        """
        Fetches the full options chain for a given symbol from the Node service.
        """
        url = f"{OptionsService.BASE_URL}/options/{symbol.upper()}"
        
        try:
            response = requests.get(url, timeout=OptionsService.TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("success"):
                return {
                    "success": False,
                    "error": data.get("error", "Unknown error from options service")
                }
            
            return {
                "success": True,
                "symbol": data.get("symbol"),
                "data": data.get("data", [])
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to options service for {symbol}")
            return {"success": False, "error": "Options service timeout"}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to options service: {str(e)}")
            return {"success": False, "error": f"Options service connection error: {str(e)}"}
            
        except Exception as e:
            logger.exception("Unexpected error in OptionsService")
            return {"success": False, "error": str(e)}

    @staticmethod
    def normalize_options_data(raw_data, target_expiry=None):
        """
        Normalizes and filters options data by expiry.
        Returns a dictionary with metadata and filtered rows.
        """
        if not raw_data:
            return None
            
        expiries = sorted(list(set(item["expiry"] for item in raw_data)))
        
        if not expiries:
            return None
            
        selected_expiry = target_expiry if target_expiry in expiries else expiries[0]
        
        filtered_data = [item for item in raw_data if item["expiry"] == selected_expiry]
        
        return {
            "available_expiries": expiries,
            "selected_expiry": selected_expiry,
            "data": filtered_data,
            "total_rows": len(filtered_data)
        }