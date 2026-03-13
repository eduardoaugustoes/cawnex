import json

def health_check(event, context):
    """
    Health check endpoint that returns status and version information.
    
    Args:
        event: AWS Lambda event object
        context: AWS Lambda context object
        
    Returns:
        dict: Response with status code, headers, and body
    """
    response_body = {
        'status': 'ok',
        'version': '1.0.0'
    }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps(response_body)
    }

def lambda_handler(event, context):
    """
    Main Lambda handler function.
    Routes requests to appropriate handlers based on the HTTP method and path.
    
    Args:
        event: AWS Lambda event object
        context: AWS Lambda context object
        
    Returns:
        dict: Response with status code, headers, and body
    """
    try:
        # Extract HTTP method and path from the event
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        
        # Handle OPTIONS requests for CORS preflight
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
                },
                'body': ''
            }
        
        # Route to health check endpoint
        if path == '/health' and http_method == 'GET':
            return health_check(event, context)
        
        # Default response for unknown endpoints
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Not Found',
                'message': f'Endpoint {http_method} {path} not found'
            })
        }
        
    except Exception as e:
        # Handle any unexpected errors
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': str(e)
            })
        }
