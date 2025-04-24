from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from market_data import market_data_client
import re
from typing import Optional, List

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

def extract_ticker_symbols(text: str) -> List[str]:
    """Extract ticker symbols from text using regex
    
    Looks for standard stock symbols like AAPL, crypto pairs like BTC/USD,
    and other common formats.
    """
    # Match common ticker patterns
    # Standard stocks: 1-5 uppercase letters
    stock_pattern = r'\b[A-Z]{1,5}\b'
    # Crypto pairs: e.g., BTC/USD, ETH/EUR
    crypto_pattern = r'\b[A-Z]{2,5}/[A-Z]{2,5}\b'
    
    # Combine patterns and find all matches
    combined_pattern = f"({stock_pattern}|{crypto_pattern})"
    matches = re.findall(combined_pattern, text)
    
    # Remove duplicates while preserving order
    unique_matches = []
    for match in matches:
        if isinstance(match, tuple):  # If match is a tuple (from capturing groups)
            match = match[0]  # Get the first group
        if match not in unique_matches:
            unique_matches.append(match)
            
    return unique_matches

def messages_to_prompt(messages):
    """
    Convert an array of messages (each with role & content) into a single prompt string.
    For example:
      System: ...

      User: ...
    """
    prompt_lines = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        prompt_lines.append(f"{role.capitalize()}: {content}")
    return "\n\n".join(prompt_lines)

def enhance_prompt_with_market_data(prompt: str) -> str:
    """Enhance the prompt with relevant market data if ticker symbols are found"""
    ticker_symbols = extract_ticker_symbols(prompt)
    
    if not ticker_symbols:
        return prompt
        
    market_context = []
    
    for ticker in ticker_symbols:
        try:
            # For U.S. stocks, include country information
            country = "US" if len(ticker) <= 5 and "/" not in ticker else None
            
            # Get quote and time series data
            quote = market_data_client.get_quote(ticker, country=country)
            time_series = market_data_client.get_time_series(
                ticker, 
                interval="1day", 
                outputsize=10,
                country=country
            )
            
            # Format the market data for this ticker
            ticker_data = f"""
Market Data for {ticker}:
"""
            
            # Add quote data if available
            if "symbol" in quote:
                ticker_data += f"""
Current Price: {quote.get('close', 'N/A')}
Change: {quote.get('change', 'N/A')} ({quote.get('percent_change', 'N/A')}%)
Open: {quote.get('open', 'N/A')}
High: {quote.get('high', 'N/A')}
Low: {quote.get('low', 'N/A')}
Volume: {quote.get('volume', 'N/A')}
"""
            # Add time series data if available (only for the most recent dates)
            if "values" in time_series and time_series["values"]:
                ticker_data += f"""
Recent Price History:
"""
                for idx, data_point in enumerate(time_series["values"][:5]):  # Limit to 5 most recent points
                    ticker_data += f"""- {data_point.get('datetime', 'N/A')}: Open ${data_point.get('open', 'N/A')}, Close ${data_point.get('close', 'N/A')}, High ${data_point.get('high', 'N/A')}, Low ${data_point.get('low', 'N/A')}, Volume {data_point.get('volume', 'N/A')}\n"""
            
            market_context.append(ticker_data)
            
        except Exception as e:
            print(f"Error fetching market data for {ticker}: {str(e)}")
            market_context.append(f"Error fetching market data for {ticker}.")
    
    # Combine all ticker data
    if market_context:
        combined_context = "\n".join(market_context)
        return f"{prompt}\n\n{combined_context}"
    
    return prompt

@app.route('/api/ollama', methods=['POST'])
def call_ollama():
    data = request.get_json(force=True)

    # Convert 'messages' array into a single 'prompt' field if present
    if "messages" in data:
        combined_prompt = messages_to_prompt(data["messages"])
        # Enhance prompt with market data if relevant
        enhanced_prompt = enhance_prompt_with_market_data(combined_prompt)
        data["prompt"] = enhanced_prompt
        del data["messages"]

    # Normalize key name if client sends 'mode' instead of 'model'
    if "model" not in data and "mode" in data:
        data["model"] = data.pop("mode")

    # Automatically inject performance parameters
    data["performance_mode"] = "high"
    data["accelerator"] = "metal"

    # Print the final payload to verify the keys are added
    print("Final payload to send to Ollama:")
    print(json.dumps(data, indent=2))

    # Set your Ollama API endpoint (adjust if needed)
    ollama_url = "http://localhost:11434/api/generate"

    try:
        response = requests.post(ollama_url, json=data, stream=True)

        def generate():
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    try:
                        parsed = json.loads(decoded_line)
                        if isinstance(parsed, dict) and "response" in parsed:
                            yield parsed["response"]
                        else:
                            yield decoded_line
                    except json.JSONDecodeError:
                        yield decoded_line
            yield "[DONE]"

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        return app.response_class(generate(), mimetype='text/plain', headers=headers)

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Could not connect to Ollama. Is it running?"}), 503
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/market-data/<symbol>', methods=['GET'])
def get_market_data(symbol: str):
    """Endpoint to get market data for a specific symbol"""
    try:
        # Get optional parameters from query string
        country = request.args.get('country', 'US')
        interval = request.args.get('interval', '1day')
        outputsize = int(request.args.get('outputsize', 30))
        
        quote = market_data_client.get_quote(symbol, country=country)
        time_series = market_data_client.get_time_series(
            symbol, 
            interval=interval, 
            outputsize=outputsize, 
            country=country
        )
        
        # If it's a stock, also get some technical indicators
        indicators = {}
        if len(symbol) <= 5 and "/" not in symbol:
            try:
                # Get 14-day Relative Strength Index (RSI)
                rsi = market_data_client.get_technical_indicators(
                    symbol, 
                    "rsi", 
                    interval=interval, 
                    country=country,
                    series_type="close"
                )
                # Get 20-day Simple Moving Average (SMA)
                sma = market_data_client.get_technical_indicators(
                    symbol, 
                    "sma", 
                    interval=interval, 
                    country=country,
                    series_type="close"
                )
                indicators = {
                    "rsi": rsi,
                    "sma": sma
                }
            except Exception as e:
                print(f"Error fetching technical indicators: {str(e)}")
        
        return jsonify({
            "quote": quote,
            "time_series": time_series,
            "indicators": indicators
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
#oh y god nigga