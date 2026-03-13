import json
import logging
from typing import Dict, Any

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler that routes requests based on HTTP method and path.
    """
    try:
        # Extract request details
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        logger.info(f"Processing {http_method} request to {path}")
        
        # Route to appropriate handler
        if http_method == 'GET' and path == '/health':
            return handle_health_check(event, context)
        else:
            return create_response(404, {'error': 'Not Found'})
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return create_response(500, {'error': 'Internal Server Error'})

def handle_health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle GET /health endpoint.
    Returns service health status without authentication.
    """
    logger.info("Health check requested")
    
    response_body = {
        "status": "ok",
        "version": "1.0.0"
    }
    
    return create_response(200, response_body)

def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized API response with proper headers.
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps(body)
    }