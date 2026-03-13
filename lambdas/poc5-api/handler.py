from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'version': '1.0.0'
    }), 200

# AWS Lambda handler
def lambda_handler(event, context):
    """AWS Lambda handler for Flask app"""
    try:
        # Extract HTTP method and path from the event
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        
        # Handle the health endpoint
        if path == '/health' and http_method == 'GET':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': '{"status": "ok", "version": "1.0.0"}'
            }
        
        # Return 404 for other endpoints
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': '{"error": "Not Found"}'
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': f'{{"error": "Internal Server Error", "message": "{str(e)}"}}'
        }

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
