#!/bin/bash
# Setup custom domain for Cawnex with SES verification

set -e

# Configuration
DOMAIN_NAME=${1}
HOSTED_ZONE_ID=""
STAGE="dev"

# Smart parameter detection
if [ -n "${2}" ]; then
    # Check if second parameter is a stage (dev/staging/prod) or hosted zone ID
    if [[ "${2}" =~ ^(dev|staging|prod)$ ]]; then
        STAGE=${2}
    else
        HOSTED_ZONE_ID=${2}
        STAGE=${3:-dev}
    fi
fi

if [ -z "$DOMAIN_NAME" ]; then
    echo "❌ Usage: $0 <domain_name> [hosted_zone_id|stage] [stage]"
    echo "   Examples:"
    echo "     $0 cawnex.ai prod                    # New hosted zone, prod stage"
    echo "     $0 cawnex.ai Z123ABCDEFGHIJ dev      # Existing zone, dev stage"
    echo "     $0 mydomain.com                      # New hosted zone, dev stage"
    exit 1
fi

echo "🌍 Setting up domain: $DOMAIN_NAME for stage: $STAGE"

# Check AWS CLI availability
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is required but not installed"
    exit 1
fi

# Deploy domain stack
echo "🚀 Deploying domain infrastructure..."
cd "$(dirname "$0")/../infra"

if [ -n "$HOSTED_ZONE_ID" ]; then
    echo "📋 Using existing hosted zone: $HOSTED_ZONE_ID"
    npx cdk deploy CawnexDomainStack-$STAGE \
        --context stage=$STAGE \
        --context domainName=$DOMAIN_NAME \
        --context hostedZoneId=$HOSTED_ZONE_ID \
        --require-approval never
else
    echo "📋 Creating new hosted zone for: $DOMAIN_NAME"
    npx cdk deploy CawnexDomainStack-$STAGE \
        --context stage=$STAGE \
        --context domainName=$DOMAIN_NAME \
        --require-approval never
    
    # Get the new hosted zone ID and nameservers
    NEW_HOSTED_ZONE_ID=$(aws cloudformation describe-stacks \
        --region us-east-1 \
        --stack-name CawnexDomainStack-$STAGE \
        --query 'Stacks[0].Outputs[?OutputKey==`HostedZoneId`].OutputValue' \
        --output text)
    
    NAMESERVERS=$(aws cloudformation describe-stacks \
        --region us-east-1 \
        --stack-name CawnexDomainStack-$STAGE \
        --query 'Stacks[0].Outputs[?OutputKey==`NameServers`].OutputValue' \
        --output text)
    
    echo ""
    echo "🔧 IMPORTANT: Configure these nameservers at your domain registrar:"
    echo "   Domain: $DOMAIN_NAME"
    echo "   Hosted Zone ID: $NEW_HOSTED_ZONE_ID"
    echo "   Nameservers: $NAMESERVERS"
    echo ""
    echo "⏳ Wait 24-48 hours for DNS propagation before proceeding with SES verification."
    
    HOSTED_ZONE_ID=$NEW_HOSTED_ZONE_ID
fi

# Verify SES domain
echo "📧 Checking SES domain verification status..."
SES_IDENTITY_STATUS=$(aws sesv2 get-email-identity \
    --email-identity $DOMAIN_NAME \
    --region us-east-1 \
    --query 'VerifiedForSendingStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$SES_IDENTITY_STATUS" = "true" ]; then
    echo "✅ SES domain is already verified: $DOMAIN_NAME"
elif [ "$SES_IDENTITY_STATUS" = "false" ]; then
    echo "⏳ SES domain verification in progress: $DOMAIN_NAME"
    echo "   Check DNS records and wait for verification to complete."
else
    echo "❌ SES domain not found. CDK should have created it."
    echo "   Check the CawnexDomainStack-$STAGE deployment."
fi

# Check DKIM status
echo "🔐 Checking DKIM configuration..."
DKIM_STATUS=$(aws sesv2 get-email-identity \
    --email-identity $DOMAIN_NAME \
    --region us-east-1 \
    --query 'DkimAttributes.Status' \
    --output text 2>/dev/null || echo "NOT_FOUND")

echo "   DKIM Status: $DKIM_STATUS"

# Redeploy auth stack with domain integration
echo "🔐 Redeploying auth stack with SES integration..."
npx cdk deploy CawnexAuthStack-$STAGE \
    --context stage=$STAGE \
    --context domainName=$DOMAIN_NAME \
    --require-approval never

echo "✅ Domain setup complete for $DOMAIN_NAME!"
echo ""
echo "📧 Email Configuration:"
echo "   From Address: noreply@$DOMAIN_NAME"
echo "   SES Region: us-east-1"
echo "   DKIM: Enabled"
echo ""
echo "🧪 Test email sending:"
echo "   1. Create a user in Cognito User Pool"
echo "   2. Verification emails will be sent from noreply@$DOMAIN_NAME"
echo "   3. Check email delivery and spam folder status"
echo ""
echo "📋 Next steps:"
echo "   1. Test user signup flow with real email"
echo "   2. Monitor SES sending reputation"
echo "   3. Set up email bounce/complaint handling (if needed)"