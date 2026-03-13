import json
import boto3
import os
from typing import Dict, Any, Optional
import time
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import logging
from github import Github
from datetime import datetime, timezone
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS resources
dynamodb = boto3.resource('dynamodb')
blackboard_table = dynamodb.Table(os.environ['BLACKBOARD_TABLE'])

def lambda_handler(event, context):
    """API Gateway handler for POC 5 async blackboard operations"""
    try:
        logger.info(f"Event: {json.dumps(event)}")
        
        http_method = event.get('httpMethod', '')
        path = event.get('path', '')
        
        # Health check endpoint
        if http_method == 'GET' and path == '/health':
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'ok',
                    'version': '1.0.0'
                })
            }
        
        # Route to appropriate handler
        if path.startswith('/murder'):
            return handle_murder_endpoints(event, context)
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Not found'})
            }
            
    except Exception as e:
        logger.error(f"Handler error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def handle_murder_endpoints(event, context):
    """Handle murder-related endpoints"""
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')
    
    if http_method == 'POST' and path == '/murder':
        return create_murder_execution(event, context)
    elif http_method == 'GET' and path.startswith('/murder/'):
        execution_id = path.split('/')[-1]
        return get_murder_status(execution_id, context)
    else:
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }

def create_murder_execution(event, context):
    """Create a new murder execution"""
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        repo = body.get('repo')
        issue_number = body.get('issue_number')
        
        if not repo or not issue_number:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'repo and issue_number are required'})
            }
        
        # Validate GitHub issue exists
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'GitHub token not configured'})
            }
        
        g = Github(github_token)
        try:
            repo_obj = g.get_repo(repo)
            issue = repo_obj.get_issue(issue_number)
        except Exception as e:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Invalid repo or issue: {str(e)}'})
            }
        
        # Generate execution ID
        execution_id = str(uuid.uuid4())
        
        # Create initial blackboard entry
        blackboard_item = {
            'id': execution_id,
            'type': 'EXECUTION',
            'status': 'PENDING',
            'repo': repo,
            'issue_number': issue_number,
            'issue_title': issue.title,
            'issue_body': issue.body or '',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'tasks': [],
            'cost': Decimal('0'),
            'ai_minutes': 0,
            'logs': []
        }
        
        # Store in DynamoDB
        blackboard_table.put_item(Item=blackboard_item)
        
        # Create TASK record to trigger murder lambda
        task_item = {
            'id': f"task-{execution_id}",
            'type': 'TASK',
            'execution_id': execution_id,
            'agent': 'murder',
            'action': 'solve_issue',
            'status': 'PENDING',
            'payload': {
                'repo': repo,
                'issue_number': issue_number
            },
            'created_at': datetime.now(timezone.utc).isoformat(),
            'priority': 1
        }
        
        blackboard_table.put_item(Item=task_item)
        
        logger.info(f"Created execution {execution_id} for {repo}#{issue_number}")
        
        return {
            'statusCode': 201,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'execution_id': execution_id,
                'status': 'PENDING',
                'repo': repo,
                'issue_number': issue_number,
                'issue_title': issue.title,
                'message': 'Execution created and queued for processing'
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid JSON in request body'})
        }
    except Exception as e:
        logger.error(f"Error creating execution: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to create execution'})
        }

def get_murder_status(execution_id: str, context):
    """Get the status of a murder execution"""
    try:
        # Get execution record
        response = blackboard_table.get_item(
            Key={'id': execution_id, 'type': 'EXECUTION'}
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Execution not found'})
            }
        
        execution = response['Item']
        
        # Get associated tasks
        task_response = blackboard_table.query(
            IndexName='type-index',  # Assuming you have a GSI on type
            KeyConditionExpression=Key('type').eq('TASK'),
            FilterExpression=Key('execution_id').eq(execution_id)
        )
        
        tasks = task_response.get('Items', [])
        
        # Convert Decimal to float for JSON serialization
        def convert_decimal(obj):
            if isinstance(obj, dict):
                return {k: convert_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimal(v) for v in obj]
            elif isinstance(obj, Decimal):
                return float(obj)
            else:
                return obj
        
        execution_data = convert_decimal(execution)
        tasks_data = convert_decimal(tasks)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'execution_id': execution_id,
                'execution': execution_data,
                'tasks': tasks_data
            })
        }
        
    except Exception as e:
        logger.error(f"Error getting execution status: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to get execution status'})
        }
