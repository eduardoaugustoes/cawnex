import json

def lambda_handler(event, context):
    """
    Main Lambda handler function that routes HTTP requests
    """
    
    # Extract HTTP method and path
    http_method = event.get('httpMethod')
    path = event.get('path')
    
    # Route requests
    if http_method == 'GET' and path == '/health':
        return handle_health_check()
    
    # Default response for unmatched routes
    return {
        'statusCode': 404,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': 'Not Found',
            'message': f'Route {http_method} {path} not found'
        })
    }

def handle_health_check():
    """
    Handle GET /health endpoint
    Returns basic health status without authentication
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'ok',
            'version': '1.0.0'
        })
    }