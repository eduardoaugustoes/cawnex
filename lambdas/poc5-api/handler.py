import json
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    AWS Lambda function handler for the API Gateway integration.
    Routes HTTP requests to appropriate endpoints.
    """
    try:
        # Extract HTTP method and path from the event
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        logger.info(f"Received {http_method} request for path: {path}")
        
        # Route requests
        if http_method == 'GET' and path == '/health':
            return handle_health()
        
        # Handle unknown endpoints
        return {
            'statusCode': 404,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'error': 'Not Found',
                'message': f'Endpoint {http_method} {path} not found'
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred'
            })
        }

def handle_health():
    """
    Health check endpoint handler.
    Returns application status and version information.
    """
    try:
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
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': 'Health check failed'
            })
        }
