from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


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


@app.route('/api/ollama', methods=['POST'])
def call_ollama():
    data = request.get_json(force=True)

    # Convert 'messages' array into a single 'prompt' field if present
    if "messages" in data:
        combined_prompt = messages_to_prompt(data["messages"])
        data["prompt"] = combined_prompt
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
                            # Yield only the response text without adding extra newlines
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
#oh y god nigga