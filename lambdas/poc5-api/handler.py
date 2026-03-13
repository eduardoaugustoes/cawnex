import json
import boto3
from typing import Dict, Any

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for POC 5 API endpoints"""
    
    try:
        # Extract HTTP method and path from the API Gateway event
        http_method = event.get('httpMethod', '').upper()
        path = event.get('path', '')
        
        # Handle GET /health endpoint
        if http_method == 'GET' and path == '/health':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({
                    'status': 'ok',
                    'version': '1.0.0'
                })
            }
        
        # Handle other endpoints (placeholder for future implementation)
        elif http_method == 'POST' and path == '/murder':
            # Placeholder for murder endpoint
            return {
                'statusCode': 501,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Murder endpoint not yet implemented',
                    'message': 'This endpoint will be implemented in future iterations'
                })
            }
        
        elif http_method == 'GET' and path.startswith('/murder/'):
            # Placeholder for murder status endpoint
            execution_id = path.split('/')[-1]
            return {
                'statusCode': 501,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Murder status endpoint not yet implemented',
                    'execution_id': execution_id,
                    'message': 'This endpoint will be implemented in future iterations'
                })
            }
        
        # Handle OPTIONS for CORS preflight
        elif http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': ''
            }
        
        # Handle unknown endpoints
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Not Found',
                    'message': f'Endpoint {http_method} {path} not found',
                    'available_endpoints': {
                        'GET /health': 'Health check endpoint',
                        'POST /murder': 'Create murder execution (not yet implemented)',
                        'GET /murder/{id}': 'Get murder execution status (not yet implemented)'
                    }
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