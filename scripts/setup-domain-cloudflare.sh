#!/bin/bash
# Setup SES for Cloudflare-managed domain

set -e

DOMAIN_NAME=${1}
STAGE=${2:-prod}

if [ -z "$DOMAIN_NAME" ]; then
    echo "❌ Usage: $0 <domain_name> [stage]"
    echo "   Example: $0 cawnex.ai prod"
    exit 1
fi

echo "🌍 Setting up SES for Cloudflare-managed domain: $DOMAIN_NAME (stage: $STAGE)"

# Check AWS CLI availability
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is required but not installed"
    exit 1
fi

# Deploy SES-only stack
echo "🚀 Deploying SES infrastructure for Cloudflare DNS..."
cd "$(dirname "$0")/../infra"

# Use the Cloudflare-compatible stack
npx cdk deploy CawnexCloudflareStack-$STAGE \
    --context stage=$STAGE \
    --context domainName=$DOMAIN_NAME \
    --require-approval never

# Get SES DKIM tokens
echo ""
echo "🔐 Getting DKIM tokens for manual DNS setup..."
sleep 10  # Wait for SES to be ready

DKIM_TOKENS=$(aws sesv2 get-email-identity \
    --email-identity $DOMAIN_NAME \
    --region us-east-1 \
    --query 'DkimAttributes.Tokens' \
    --output text 2>/dev/null || echo "")

if [ -n "$DKIM_TOKENS" ]; then
    echo ""
    echo "✅ SES deployment complete for $DOMAIN_NAME!"
    echo ""
    echo "📋 ADD THESE RECORDS IN CLOUDFLARE DNS:"
    echo ""
    echo "1️⃣ SPF Record:"
    echo "   Type: TXT"
    echo "   Name: @ (root)"
    echo "   Content: v=spf1 include:amazonses.com ~all"
    echo ""
    echo "2️⃣ DMARC Record:"
    echo "   Type: TXT"
    echo "   Name: _dmarc"
    echo "   Content: v=DMARC1; p=quarantine; fo=1; rua=mailto:dmarc@$DOMAIN_NAME; ruf=mailto:dmarc@$DOMAIN_NAME"
    echo ""
    echo "3️⃣ DKIM Records:"
    
    counter=1
    for token in $DKIM_TOKENS; do
        echo "   DKIM $counter:"
        echo "   Type: CNAME"
        echo "   Name: ${token}._domainkey"
        echo "   Content: ${token}.dkim.amazonses.com"
        echo ""
        counter=$((counter + 1))
    done
    
    echo "📧 After adding these records, emails from noreply@$DOMAIN_NAME will work!"
    echo ""
    echo "🧪 Test verification in ~10 minutes:"
    echo "   aws sesv2 get-email-identity --email-identity $DOMAIN_NAME --region us-east-1 --query 'VerifiedForSendingStatus'"
else
    echo "⚠️  DKIM tokens not ready yet. Get them manually:"
    echo "   aws sesv2 get-email-identity --email-identity $DOMAIN_NAME --region us-east-1 --query 'DkimAttributes.Tokens'"
    echo ""
    echo "📋 For now, add these basic records in Cloudflare:"
    echo ""
    echo "SPF Record:"
    echo "   Type: TXT, Name: @, Content: v=spf1 include:amazonses.com ~all"
    echo ""
    echo "DMARC Record:"
    echo "   Type: TXT, Name: _dmarc, Content: v=DMARC1; p=quarantine; fo=1; rua=mailto:dmarc@$DOMAIN_NAME"
fi