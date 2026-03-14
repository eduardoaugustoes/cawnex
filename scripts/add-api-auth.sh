#!/bin/bash
# Add JWT authentication to deployed API after stack deployment
# This avoids circular dependency during initial deployment

set -e

STAGE=${1:-dev}
echo "🔐 Adding JWT authentication to Cawnex-$STAGE API..."

# Get stack outputs
STACK_NAME="Cawnex-$STAGE"

USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

IOS_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`iOSClientId`].OutputValue' \
    --output text)

WEB_CLIENT_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`WebClientId`].OutputValue' \
    --output text)

API_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
    --output text | sed 's|https://||' | cut -d'.' -f1)

echo "✅ Found resources:"
echo "   UserPool ID: $USER_POOL_ID" 
echo "   iOS Client ID: $IOS_CLIENT_ID"
echo "   Web Client ID: $WEB_CLIENT_ID"
echo "   API ID: $API_ID"

# Create JWT Authorizer via AWS CLI
echo "🔧 Creating JWT Authorizer..."

AUTHORIZER_ID=$(aws apigatewayv2 create-authorizer \
    --api-id "$API_ID" \
    --authorizer-type JWT \
    --name "CognitoAuthorizer" \
    --identity-sources '$request.header.Authorization' \
    --jwt-configuration Audience="[$IOS_CLIENT_ID,$WEB_CLIENT_ID]",Issuer="https://cognito-idp.us-east-1.amazonaws.com/$USER_POOL_ID" \
    --query 'AuthorizerId' \
    --output text)

echo "✅ Created JWT Authorizer: $AUTHORIZER_ID"

# Get the route ID for /{proxy+} 
ROUTE_ID=$(aws apigatewayv2 get-routes \
    --api-id "$API_ID" \
    --query 'Items[?RouteKey==`ANY /{proxy+}`].RouteId' \
    --output text)

if [ -z "$ROUTE_ID" ]; then
    echo "❌ Could not find proxy route"
    exit 1
fi

echo "✅ Found proxy route: $ROUTE_ID"

# Update the route to use the authorizer
echo "🔧 Adding authorization to proxy route..."
aws apigatewayv2 update-route \
    --api-id "$API_ID" \
    --route-id "$ROUTE_ID" \
    --authorization-type JWT \
    --authorizer-id "$AUTHORIZER_ID" > /dev/null

echo "✅ JWT authorization enabled on API!"
echo ""
echo "🎉 API security is now fully configured:"
echo "   - /health → No authentication (monitoring)"
echo "   - /{proxy+} → JWT authentication required"
echo ""
echo "The iOS app can now authenticate with the API using Cognito tokens."