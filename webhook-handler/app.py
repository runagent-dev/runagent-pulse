"""
Webhook Handler Service
Receives execution results from Pulse and logs/stores them
"""
from flask import Flask, request, jsonify
import json
import os
from datetime import datetime
from glob import glob

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
                "endpoints": {
                    "get_all_executions": "/results/<task_id> - Get all execution results for a task",
                    "get_specific_execution": "/results/<task_id>/<execution_id> - Get specific execution result"
                },
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
    
    # Save to file - use execution_id if available, otherwise task_id
    task_id = data.get('task_id', 'unknown')
    execution_id = data.get('execution_id', 'unknown')
    
    # Save with execution_id to avoid overwriting
    if execution_id and execution_id != 'unknown':
        filename = f"{task_id}_{execution_id}.json"
    else:
        filename = f"{task_id}.json"
    
    filepath = f"{RESULTS_DIR}/{filename}"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Don't save duplicate task_id.json file - only save with execution_id
    
    return jsonify({"status": "received", "task_id": task_id, "execution_id": execution_id})


@app.route('/results/<task_id>')
def get_all_results(task_id):
    """Get all execution results for a task_id"""
    try:
        # Find all result files for this task_id
        # Pattern: task_id_execution_id.json (prefer execution-specific files)
        pattern = f"{RESULTS_DIR}/{task_id}_*.json"
        result_files = glob(pattern)
        
        # Also check for task_id.json (backward compatibility)
        task_file = f"{RESULTS_DIR}/{task_id}.json"
        if os.path.exists(task_file) and task_file not in result_files:
            result_files.append(task_file)
        
        if not result_files:
            return jsonify({"error": "No results found", "task_id": task_id}), 404
        
        results = []
        seen_execution_ids = set()
        
        for filepath in sorted(result_files, key=os.path.getmtime, reverse=True):
            try:
                with open(filepath) as f:
                    result_data = json.load(f)
                    execution_id = result_data.get('execution_id')
                    
                    # Skip duplicates (same execution_id)
                    if execution_id and execution_id in seen_execution_ids:
                        continue
                    if execution_id:
                        seen_execution_ids.add(execution_id)
                    
                    results.append({
                        "execution_id": execution_id,
                        "task_id": result_data.get('task_id'),
                        "status": result_data.get('status'),
                        "timestamp": result_data.get('timestamp'),
                        "execution_time_ms": result_data.get('execution_time_ms'),
                        "result": result_data.get('result'),
                        "error": result_data.get('error'),
                        "file": os.path.basename(filepath)
                    })
            except Exception as e:
                # Skip corrupted files
                continue
        
        # Sort by timestamp (oldest first)
        results.sort(key=lambda x: x.get('timestamp', 0))
        
        return jsonify({
            "task_id": task_id,
            "total_executions": len(results),
            "executions": results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/results/<task_id>/<execution_id>')
def get_specific_result(task_id, execution_id):
    """Get specific execution result by task_id and execution_id"""
    # Try execution_id-specific file first
    filename = f"{task_id}_{execution_id}.json"
    filepath = f"{RESULTS_DIR}/{filename}"
    
    if os.path.exists(filepath):
        with open(filepath) as f:
            return jsonify(json.load(f))
    
    # Fallback: search all files for this task_id and execution_id
    pattern = f"{RESULTS_DIR}/{task_id}*.json"
    result_files = glob(pattern)
    
    for filepath in result_files:
        try:
            with open(filepath) as f:
                data = json.load(f)
                if data.get('execution_id') == execution_id:
                    return jsonify(data)
        except:
            continue
    
    return jsonify({"error": "Not found", "task_id": task_id, "execution_id": execution_id}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3001)

