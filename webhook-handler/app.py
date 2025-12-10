"""
Webhook Handler Service
Receives execution results from Pulse and logs/stores them
"""
from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
RESULTS_DIR = os.getenv("RESULTS_DIR", "/app/results")
os.makedirs(RESULTS_DIR, exist_ok=True)


@app.route('/health')
def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.route('/results', methods=['POST', 'GET'])
def handle_result():
    """Receive result from Pulse after agent execution (POST) or show info (GET)"""
    if request.method == 'GET':
        # List available results or show info
        try:
            result_files = [f.replace('.json', '') for f in os.listdir(RESULTS_DIR) if f.endswith('.json')]
            return jsonify({
                "message": "Webhook handler is running",
                "endpoint": "/results",
                "methods": {
                    "POST": "Receive execution results from Pulse",
                    "GET": "This info endpoint"
                },
                "get_result": "/results/<task_id> - Get specific result",
                "available_results": len(result_files),
                "recent_results": result_files[-10:] if result_files else []
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # POST: Receive result from Pulse
    data = request.json
    
    # Log to console
    print("\n" + "="*70)
    print(f"📬 RESULT RECEIVED AT {datetime.now()}")
    print("="*70)
    print(json.dumps(data, indent=2))
    print("="*70 + "\n")
    
    # Save to file
    task_id = data.get('task_id', 'unknown')
    with open(f"{RESULTS_DIR}/{task_id}.json", 'w') as f:
        json.dump(data, f, indent=2)
    
    return jsonify({"status": "received", "task_id": task_id})


@app.route('/results/<task_id>')
def get_result(task_id):
    """Retrieve saved result"""
    result_file = f"{RESULTS_DIR}/{task_id}.json"
    if os.path.exists(result_file):
        with open(result_file) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Not found"}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)

