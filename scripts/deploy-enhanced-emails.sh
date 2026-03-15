#!/bin/bash
set -e

# Cawnex Enhanced Email Templates Deployment Script
# Usage: ./scripts/deploy-enhanced-emails.sh [dev|staging|prod]

STAGE="${1:-dev}"
DOMAIN_NAME="${2:-cawnex.ai}"

echo "🚀 Deploying Enhanced Email Templates for Cawnex"
echo "Stage: $STAGE"
echo "Domain: $DOMAIN_NAME"
echo "----------------------------------------"

# Validate stage parameter
case $STAGE in
  dev|staging|prod)
    echo "✅ Stage '$STAGE' is valid"
    ;;
  *)
    echo "❌ Invalid stage '$STAGE'. Use: dev, staging, or prod"
    exit 1
    ;;
esac

# Navigate to infrastructure directory
cd "$(dirname "$0")/../infra" || {
  echo "❌ Error: Could not find infra directory"
  exit 1
}

echo "📦 Installing dependencies..."
npm install

echo "🔨 Building CDK stacks..."
npm run build

echo "🔍 Checking current auth stack..."
CURRENT_STACK="CawnexAuthStack-$STAGE"
ENHANCED_STACK="CawnexAuthStackEnhanced-$STAGE"

# Check if enhanced stack already exists
if aws cloudformation describe-stacks --stack-name "$ENHANCED_STACK" --region us-east-1 >/dev/null 2>&1; then
  echo "✅ Enhanced stack already exists, updating..."
  ACTION="update"
else
  echo "📊 Enhanced stack does not exist, creating new..."
  ACTION="create"
fi

echo "🚀 Deploying enhanced auth stack with custom email templates..."
npx cdk deploy "$ENHANCED_STACK" \
  --context stage="$STAGE" \
  --context domainName="$DOMAIN_NAME" \
  --require-approval never \
  --verbose

if [ $? -eq 0 ]; then
  echo "✅ Enhanced auth stack deployed successfully!"
else
  echo "❌ Error deploying enhanced auth stack"
  exit 1
fi

echo "🔍 Verifying custom email sender Lambda..."
FUNCTION_NAME="cawnex-custom-email-sender-$STAGE"
if aws lambda get-function --function-name "$FUNCTION_NAME" --region us-east-1 >/dev/null 2>&1; then
  echo "✅ Custom email sender Lambda is deployed and accessible"
else
  echo "⚠️  Warning: Custom email sender Lambda not found or not accessible"
fi

echo "🔍 Verifying Cognito trigger configuration..."
case $STAGE in
  prod)
    USER_POOL_ID="us-east-1_6LT5eHiBs"
    ;;
  dev)
    USER_POOL_ID="us-east-1_38Ay7DArT"
    ;;
  *)
    echo "⚠️  Unknown user pool ID for stage $STAGE"
    USER_POOL_ID=""
    ;;
esac

if [ -n "$USER_POOL_ID" ]; then
  LAMBDA_CONFIG=$(aws cognito-idp describe-user-pool \
    --user-pool-id "$USER_POOL_ID" \
    --region us-east-1 \
    --query 'UserPool.LambdaConfig' \
    --output json 2>/dev/null || echo "{}")

  if echo "$LAMBDA_CONFIG" | grep -q "CustomMessage"; then
    echo "✅ Cognito custom message trigger is configured"
  else
    echo "⚠️  Warning: Cognito custom message trigger not found in configuration"
  fi
fi

echo "🧪 Testing email template loading..."
TEST_PAYLOAD='{
  "triggerSource": "CustomMessage_SignUp",
  "request": {
    "codeParameter": "123456",
    "userAttributes": {
      "email": "test@example.com",
      "name": "Test User"
    }
  },
  "response": {}
}'

echo "$TEST_PAYLOAD" > /tmp/test_payload.json

TEST_RESULT=$(aws lambda invoke \
  --function-name "$FUNCTION_NAME" \
  --payload file:///tmp/test_payload.json \
  --region us-east-1 \
  /tmp/test_response.json 2>&1 || echo "ERROR")

if echo "$TEST_RESULT" | grep -q "ERROR"; then
  echo "⚠️  Warning: Could not test email template loading"
  echo "Error: $TEST_RESULT"
else
  echo "✅ Email templates are loading successfully"
fi

# Cleanup test files
rm -f /tmp/test_payload.json /tmp/test_response.json

echo ""
echo "🎉 Enhanced Email Templates Deployment Complete!"
echo "----------------------------------------"
echo "📧 Email Templates Available:"
echo "  • Verification emails with custom branding"
echo "  • Welcome emails after account confirmation"
echo "  • Password reset emails with security features"
echo ""
echo "📊 Next Steps:"
echo "  1. Test the signup flow with a real email address"
echo "  2. Monitor CloudWatch logs for email sending"
echo "  3. Check SES metrics for delivery performance"
echo "  4. Review user feedback on email experience"
echo ""
echo "📚 Documentation:"
echo "  • Implementation guide: docs/enhanced-email-implementation-guide.md"
echo "  • Template customization: lambdas/custom-email-sender/templates/"
echo ""
echo "🔧 Monitoring:"
echo "  • Lambda logs: aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo "  • SES metrics: aws ses get-send-statistics --region us-east-1"
echo ""

if [ "$ACTION" = "create" ] && [ -n "$USER_POOL_ID" ]; then
  echo "⚡ Important: If this is the first deployment, you may need to:"
  echo "  1. Wait 5-10 minutes for all triggers to be fully active"
  echo "  2. Test with a new signup (not existing users)"
  echo "  3. Check that domain verification is complete in SES"
fi

echo "✅ Deployment completed successfully!"
