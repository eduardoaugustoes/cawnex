#!/bin/bash
# Verify domain and email configuration for Cawnex

set -e

DOMAIN_NAME=${1}
STAGE=${2:-dev}

if [ -z "$DOMAIN_NAME" ]; then
    echo "❌ Usage: $0 <domain_name> [stage]"
    echo "   Example: $0 cawnex.ai dev"
    exit 1
fi

echo "🔍 Verifying domain setup for: $DOMAIN_NAME (stage: $STAGE)"
echo ""

# Check Route53 hosted zone
echo "1️⃣ Checking Route53 hosted zone..."
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
    --dns-name $DOMAIN_NAME \
    --query 'HostedZones[?Name==`'${DOMAIN_NAME}'.`].Id' \
    --output text | cut -d'/' -f3)

if [ -n "$HOSTED_ZONE_ID" ]; then
    echo "   ✅ Hosted Zone: $HOSTED_ZONE_ID"
else
    echo "   ❌ No hosted zone found for $DOMAIN_NAME"
    exit 1
fi

# Check DNS records
echo ""
echo "2️⃣ Checking DNS records..."

# SPF record
SPF_RECORD=$(dig txt $DOMAIN_NAME +short | grep "v=spf1" || echo "")
if [ -n "$SPF_RECORD" ]; then
    echo "   ✅ SPF: $SPF_RECORD"
else
    echo "   ❌ No SPF record found"
fi

# DMARC record
DMARC_RECORD=$(dig txt _dmarc.$DOMAIN_NAME +short | grep "v=DMARC1" || echo "")
if [ -n "$DMARC_RECORD" ]; then
    echo "   ✅ DMARC: $DMARC_RECORD"
else
    echo "   ❌ No DMARC record found"
fi

# Check SES verification
echo ""
echo "3️⃣ Checking SES domain verification..."
SES_STATUS=$(aws sesv2 get-email-identity \
    --email-identity $DOMAIN_NAME \
    --region us-east-1 \
    --query '{Verified:VerifiedForSendingStatus,DKIM:DkimAttributes.Status}' \
    --output table 2>/dev/null || echo "SES domain not found")

echo "   $SES_STATUS"

# Check DKIM DNS records
echo ""
echo "4️⃣ Checking DKIM DNS records..."
DKIM_TOKENS=$(aws sesv2 get-email-identity \
    --email-identity $DOMAIN_NAME \
    --region us-east-1 \
    --query 'DkimAttributes.Tokens' \
    --output text 2>/dev/null || echo "")

if [ -n "$DKIM_TOKENS" ]; then
    for token in $DKIM_TOKENS; do
        DKIM_RECORD=$(dig cname ${token}._domainkey.$DOMAIN_NAME +short || echo "")
        if [ -n "$DKIM_RECORD" ]; then
            echo "   ✅ DKIM token ${token}: $DKIM_RECORD"
        else
            echo "   ❌ DKIM token ${token}: Not found"
        fi
    done
else
    echo "   ❌ No DKIM tokens found"
fi

# Check SSL certificate
echo ""
echo "5️⃣ Checking SSL certificate..."
CERT_ARN=$(aws cloudformation describe-stacks \
    --region us-east-1 \
    --stack-name CawnexDomainStack-$STAGE \
    --query 'Stacks[0].Outputs[?OutputKey==`CertificateArn`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [ -n "$CERT_ARN" ]; then
    CERT_STATUS=$(aws acm describe-certificate \
        --certificate-arn $CERT_ARN \
        --region us-east-1 \
        --query 'Certificate.Status' \
        --output text)
    echo "   ✅ Certificate: $CERT_STATUS ($CERT_ARN)"
else
    echo "   ❌ No certificate found"
fi

# Test email sending capability
echo ""
echo "6️⃣ Testing email sending capability..."
TEST_EMAIL=${TEST_EMAIL:-"your-email@example.com"}

if [ "$TEST_EMAIL" = "your-email@example.com" ]; then
    echo "   ⚠️  Set TEST_EMAIL env var to test email sending"
    echo "      Example: TEST_EMAIL=you@domain.com $0 $DOMAIN_NAME $STAGE"
else
    echo "   📧 Testing email to: $TEST_EMAIL"
    
    # Check if email is verified in SES (required for sandbox)
    EMAIL_STATUS=$(aws sesv2 get-email-identity \
        --email-identity $TEST_EMAIL \
        --region us-east-1 \
        --query 'VerifiedForSendingStatus' \
        --output text 2>/dev/null || echo "false")
    
    if [ "$EMAIL_STATUS" = "true" ]; then
        # Send test email
        aws sesv2 send-email \
            --region us-east-1 \
            --from-email-address "noreply@$DOMAIN_NAME" \
            --destination "ToAddresses=$TEST_EMAIL" \
            --content "Simple={
                Subject={Data=\"Cawnex Domain Test\",Charset=utf-8},
                Body={Text={Data=\"This is a test email from your Cawnex domain setup. If you receive this, your domain configuration is working correctly!\",Charset=utf-8}}
            }" > /dev/null
        echo "   ✅ Test email sent successfully"
    else
        echo "   ⚠️  Target email not verified in SES (sandbox mode)"
        echo "      Add $TEST_EMAIL to SES verified identities to test sending"
    fi
fi

# Summary
echo ""
echo "📋 Domain Setup Summary for $DOMAIN_NAME:"
echo "   Hosted Zone: $([ -n "$HOSTED_ZONE_ID" ] && echo "✅" || echo "❌")"
echo "   SPF Record: $([ -n "$SPF_RECORD" ] && echo "✅" || echo "❌")"  
echo "   DMARC Record: $([ -n "$DMARC_RECORD" ] && echo "✅" || echo "❌")"
echo "   SES Verified: $(aws sesv2 get-email-identity --email-identity $DOMAIN_NAME --region us-east-1 --query 'VerifiedForSendingStatus' --output text 2>/dev/null || echo "false")"
echo "   SSL Certificate: $([ -n "$CERT_ARN" ] && echo "✅" || echo "❌")"
echo ""
echo "🚀 Ready for production email sending: $([ -n "$SPF_RECORD" ] && [ -n "$DMARC_RECORD" ] && echo "✅ YES" || echo "❌ NO - Fix DNS records first")"