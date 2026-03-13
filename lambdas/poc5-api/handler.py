import json

def lambda_handler(event, context):
    """
    AWS Lambda handler for POC5 API
    """
    
    # Extract HTTP method and path
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    
    # Handle GET /health endpoint
    if http_method == 'GET' and path == '/health':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS'
            },
            'body': json.dumps({
                'status': 'ok',
                'version': '1.0.0'
            })
        }
    
    # Handle other endpoints (placeholder for future implementation)
    return {
        'statusCode': 404,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': 'Not Found',
            'message': f'The requested endpoint {http_method} {path} was not found'
        })
    }
