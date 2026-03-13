import json

def health(event, context):
    """
    Health check endpoint handler.
    
    Args:
        event: API Gateway event data
        context: AWS Lambda context object
        
    Returns:
        Dict: API Gateway response format with status and headers
    """
    response = {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps({
            'status': 'ok',
            'version': '1.0.0'
        })
    }
    
    return response
