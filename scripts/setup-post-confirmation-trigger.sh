#!/bin/bash
# Add PostConfirmation trigger to Cognito User Pool after deployment
# This avoids circular dependency during CDK deployment

set -e

STAGE=${1:-dev}
echo "🔧 Setting up PostConfirmation trigger for Cawnex-$STAGE..."

# Get stack outputs
AUTH_STACK_NAME="CawnexAuthStack-$STAGE"

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$AUTH_STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

# Get PostConfirmation Lambda function name (it's predictable from CDK)
LAMBDA_FUNCTION_NAME="cawnex-post-confirmation-$STAGE"

echo "✅ Found resources:"
echo "   UserPool ID: $USER_POOL_ID"
echo "   Lambda Function: $LAMBDA_FUNCTION_NAME"

# Check if trigger already exists
echo "🔍 Checking existing triggers..."
EXISTING_TRIGGER=$(aws cognito-idp describe-user-pool \
    --user-pool-id "$USER_POOL_ID" \
    --query 'UserPool.LambdaConfig.PostConfirmation' \
    --output text 2>/dev/null || echo "None")

if [ "$EXISTING_TRIGGER" != "None" ] && [ "$EXISTING_TRIGGER" != "" ]; then
    echo "⚠️  PostConfirmation trigger already exists: $EXISTING_TRIGGER"
    echo "   Skipping setup."
    exit 0
fi

# Get Lambda function ARN
LAMBDA_ARN=$(aws lambda get-function \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --query 'Configuration.FunctionArn' \
    --output text)

echo "✅ Lambda ARN: $LAMBDA_ARN"

# Add Lambda permission for Cognito to invoke the function
echo "🔧 Adding Lambda invoke permission for Cognito..."
aws lambda add-permission \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --statement-id "CognitoPostConfirmationInvoke" \
    --action "lambda:InvokeFunction" \
    --principal "cognito-idp.amazonaws.com" \
    --source-arn "arn:aws:cognito-idp:us-east-1:*:userpool/$USER_POOL_ID" \
    --output text > /dev/null 2>&1 || echo "   Permission may already exist"

# Update User Pool with PostConfirmation trigger
echo "🔧 Adding PostConfirmation trigger to User Pool..."
aws cognito-idp update-user-pool \
    --user-pool-id "$USER_POOL_ID" \
    --lambda-config PostConfirmation="$LAMBDA_ARN"

echo "✅ PostConfirmation trigger configured successfully!"
echo ""
echo "🎉 User signup flow now includes:"
echo "   1. User signs up → Email verification"
echo "   2. User confirms email → PostConfirmation Lambda triggered"
echo "   3. Lambda creates tenant + assigns tenant_id to user"
echo "   4. User can log in with multi-tenant JWT tokens"
echo ""
echo "The Cognito authentication system is now fully operational!"
