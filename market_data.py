import requests
from typing import Dict, Optional, List
import os
from datetime import datetime, timedelta

# Instead of using dotenv, let's directly set the API key here
# You should replace this with your actual API key from Twelve Data
TWELVE_DATA_API_KEY = "ea051d31139f4c45ad5f3442aeb27b16"

class TwelveDataAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.twelvedata.com"
        
    def get_quote(self, symbol: str, country: Optional[str] = None) -> Dict:
        """Get real-time quote for a symbol"""
        endpoint = f"{self.base_url}/quote"
        params = {
            "symbol": symbol,
            "apikey": self.api_key
        }
        if country:
            params["country"] = country
            
        response = requests.get(endpoint, params=params)
        return response.json()
    
    def get_time_series(self, symbol: str, interval: str = "1day", outputsize: int = 30, 
                        country: Optional[str] = None, exchange: Optional[str] = None) -> Dict:
        """Get historical time series data
        
        Args:
            symbol: The ticker symbol (e.g., AAPL, BTC)
            interval: Time interval (1min, 5min, 15min, 30min, 45min, 1h, 2h, 4h, 1day, 1week, 1month)
            outputsize: Number of data points to return
            country: Country code (e.g., US)
            exchange: Exchange name (e.g., NYSE)
        """
        endpoint = f"{self.base_url}/time_series"
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": self.api_key
        }
        if country:
            params["country"] = country
        if exchange:
            params["exchange"] = exchange
            
        response = requests.get(endpoint, params=params)
        data = response.json()
        
        # Return empty dict if there's an error in the response
        if "code" in data and data["code"] != 200:
            print(f"Error from Twelve Data API: {data.get('message', 'Unknown error')}")
            return {"error": data.get("message", "Unknown error")}
            
        return data
    
    def get_technical_indicators(self, symbol: str, indicator: str, interval: str = "1day", 
                                country: Optional[str] = None, series_type: str = "close") -> Dict:
        """Get technical indicators for a symbol
        
        Args:
            symbol: The ticker symbol (e.g., AAPL, BTC)
            indicator: Indicator name (e.g., sma, ema, macd)
            interval: Time interval (same options as time_series)
            country: Country code (e.g., US)
            series_type: Series type for calculations (open, high, low, close)
        """
        endpoint = f"{self.base_url}/{indicator}"  # TwelveData uses endpoint names based on indicators
        params = {
            "symbol": symbol,
            "interval": interval,
            "series_type": series_type,
            "apikey": self.api_key
        }
        if country:
            params["country"] = country
            
        response = requests.get(endpoint, params=params)
        return response.json()
        
    def search_symbol(self, symbol: str, country: Optional[str] = None) -> Dict:
        """Search for a symbol"""
        endpoint = f"{self.base_url}/symbol_search"
        params = {
            "symbol": symbol,
            "apikey": self.api_key
        }
        if country:
            params["country"] = country
            
        response = requests.get(endpoint, params=params)
        return response.json()

# Initialize the API client
# Try to get from environment first, then use hardcoded value
api_key = os.getenv("TWELVE_DATA_API_KEY", TWELVE_DATA_API_KEY)
if not api_key:
    raise ValueError("TWELVE_DATA_API_KEY not found. Please set it in your environment or in this file.")

market_data_client = TwelveDataAPI(api_key) 