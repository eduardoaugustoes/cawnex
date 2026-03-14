# 🌍 Cawnex Domain Setup Guide

**Complete guide to setting up custom domain with AWS Route53, SES, DKIM, and SSL certificates.**

---

## 🎯 **What This Sets Up:**

### **DNS Management:**

- ✅ Route53 Hosted Zone (DNS management by AWS)
- ✅ SPF record (email authentication)
- ✅ DMARC record (email security policy)
- ✅ Wildcard SSL Certificate (\*.yourdomain.com)

### **Email Services:**

- ✅ SES Domain Verification (send from your domain)
- ✅ DKIM Signing (email authentication)
- ✅ Custom email addresses (`noreply@yourdomain.com`)
- ✅ Cognito integration (verification emails from your domain)

### **Subdomains Ready:**

- ✅ `api.yourdomain.com` (API Gateway custom domain)
- ✅ `app.yourdomain.com` (Web dashboard)
- ✅ `auth.yourdomain.com` (Cognito custom domain)

---

## 🚀 **Quick Setup (Recommended)**

### **Step 1: Configure Your Domain**

```bash
# Replace with your actual domain
DOMAIN="yourdomain.com"
STAGE="dev"

# If you already have Route53 hosted zone:
./scripts/setup-domain.sh $DOMAIN Z123ABCDEFGHIJ $STAGE

# If you need AWS to manage DNS:
./scripts/setup-domain.sh $DOMAIN $STAGE
```

### **Step 2: Verify Setup**

```bash
# Wait 5-10 minutes for deployment
./scripts/verify-domain-setup.sh $DOMAIN $STAGE

# Test email sending (optional)
TEST_EMAIL=your-email@gmail.com ./scripts/verify-domain-setup.sh $DOMAIN $STAGE
```

### **Step 3: Deploy with Domain Integration**

```bash
# Redeploy auth stack with domain
cd infra
npx cdk deploy CawnexAuthStack-$STAGE \
    --context stage=$STAGE \
    --context domainName=$DOMAIN
```

---

## 📋 **Manual Setup Process**

### **Prerequisites:**

- Domain registered (GoDaddy, Namecheap, Route53, etc.)
- AWS CLI configured with appropriate permissions
- CDK installed (`npm install -g aws-cdk`)

### **Step 1: Deploy Domain Stack**

```bash
cd infra

# Deploy domain infrastructure
npx cdk deploy CawnexDomainStack-dev \
    --context stage=dev \
    --context domainName=yourdomain.com \
    --require-approval never
```

### **Step 2: Update Nameservers (if new hosted zone)**

```bash
# Get nameservers from stack output
aws cloudformation describe-stacks \
    --stack-name CawnexDomainStack-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`NameServers`].OutputValue' \
    --output text

# Update at your domain registrar:
# ns-123.awsdns-12.com
# ns-456.awsdns-34.net
# ns-789.awsdns-56.co.uk
# ns-012.awsdns-78.org
```

### **Step 3: Wait for DNS Propagation**

```bash
# Check DNS propagation (may take 24-48 hours)
dig ns yourdomain.com
dig txt yourdomain.com  # Should show SPF record
dig txt _dmarc.yourdomain.com  # Should show DMARC record
```

### **Step 4: Verify SES Domain**

```bash
# Check SES verification status
aws sesv2 get-email-identity \
    --email-identity yourdomain.com \
    --region us-east-1
```

### **Step 5: Redeploy Auth Stack with SES**

```bash
# Redeploy with domain integration
npx cdk deploy CawnexAuthStack-dev \
    --context stage=dev \
    --context domainName=yourdomain.com
```

---

## 🔧 **Domain Configuration Examples**

### **Production Setup (cawnex.ai):**

```bash
# Full production setup
./scripts/setup-domain.sh cawnex.ai Z0123456789ABCDEF prod

# Verify production setup
./scripts/verify-domain-setup.sh cawnex.ai prod

# Subdomains will be:
# - api.cawnex.ai (API Gateway)
# - app.cawnex.ai (Web dashboard)
# - auth.cawnex.ai (Cognito custom domain)
# - Email: noreply@cawnex.ai, support@cawnex.ai
```

### **Development Setup (dev.cawnex.ai):**

```bash
# Development with subdomain
./scripts/setup-domain.sh dev.cawnex.ai Z0123456789ABCDEF dev

# Subdomains will be:
# - api-dev.dev.cawnex.ai
# - app-dev.dev.cawnex.ai
# - auth-dev.dev.cawnex.ai
```

### **Custom Domain Setup (mydomain.com):**

```bash
# Your own domain
./scripts/setup-domain.sh mydomain.com dev

# Follow nameserver instructions
# Wait 24-48 hours for DNS propagation
# Then verify setup
```

---

## ✅ **Verification Checklist**

### **DNS Records (dig commands):**

```bash
# SPF record (email authentication)
dig txt yourdomain.com | grep "v=spf1"
# Expected: "v=spf1 include:amazonses.com ~all"

# DMARC record (email security)
dig txt _dmarc.yourdomain.com | grep "v=DMARC1"
# Expected: "v=DMARC1; p=quarantine; fo=1; rua=mailto:dmarc@yourdomain.com"

# DKIM records (get tokens from SES first)
aws sesv2 get-email-identity --email-identity yourdomain.com --query 'DkimAttributes.Tokens'
dig cname TOKEN1._domainkey.yourdomain.com
dig cname TOKEN2._domainkey.yourdomain.com
dig cname TOKEN3._domainkey.yourdomain.com
```

### **SES Verification:**

```bash
# Domain verification status
aws sesv2 get-email-identity \
    --email-identity yourdomain.com \
    --region us-east-1 \
    --query 'VerifiedForSendingStatus'
# Expected: true

# DKIM status
aws sesv2 get-email-identity \
    --email-identity yourdomain.com \
    --region us-east-1 \
    --query 'DkimAttributes.Status'
# Expected: "SUCCESS"
```

### **SSL Certificate:**

```bash
# Certificate status
CERT_ARN=$(aws cloudformation describe-stacks \
    --stack-name CawnexDomainStack-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`CertificateArn`].OutputValue' \
    --output text)

aws acm describe-certificate \
    --certificate-arn $CERT_ARN \
    --region us-east-1 \
    --query 'Certificate.Status'
# Expected: "ISSUED"
```

---

## 📧 **Email Testing**

### **Test Email Sending:**

```bash
# Verify your test email first (SES sandbox requirement)
aws sesv2 create-email-identity \
    --email-identity your-test@gmail.com \
    --region us-east-1

# Send test email
aws sesv2 send-email \
    --region us-east-1 \
    --from-email-address "noreply@yourdomain.com" \
    --destination "ToAddresses=your-test@gmail.com" \
    --content "Simple={
        Subject={Data=\"Cawnex Test Email\",Charset=utf-8},
        Body={Text={Data=\"Test email from your custom domain!\",Charset=utf-8}}
    }"
```

### **Test Cognito Verification:**

```bash
# Create test user (will send verification email from your domain)
aws cognito-idp admin-create-user \
    --region us-east-1 \
    --user-pool-id us-east-1_YOURPOOLID \
    --username testuser \
    --user-attributes Name=email,Value=your-test@gmail.com \
    --temporary-password "TempPass123!" \
    --message-action DELIVER
```

---

## 🚨 **Troubleshooting**

### **Common Issues:**

#### **SES Domain Not Verified:**

```bash
# Check DNS records are properly set
dig txt yourdomain.com | grep amazonses
dig cname TOKEN._domainkey.yourdomain.com

# Force re-verification
aws sesv2 delete-email-identity --email-identity yourdomain.com
# Redeploy domain stack
```

#### **Emails Going to Spam:**

```bash
# Check SPF/DMARC records
./scripts/verify-domain-setup.sh yourdomain.com dev

# Warm up sending reputation gradually
# Start with verified emails only
# Monitor bounce/complaint rates
```

#### **Certificate Not Issued:**

```bash
# Check DNS validation records
aws acm describe-certificate --certificate-arn $CERT_ARN \
    --query 'Certificate.DomainValidationOptions'

# Ensure Route53 hosted zone is properly configured
```

#### **DNS Propagation Issues:**

```bash
# Check nameservers at registrar
whois yourdomain.com | grep "Name Server"

# Test from different locations
# Use: https://www.whatsmydns.net/

# Wait 24-48 hours for full propagation
```

---

## 🎯 **Production Checklist**

### **Before Production:**

- ✅ Domain verified in SES
- ✅ SPF, DKIM, DMARC records configured
- ✅ SSL certificate issued and valid
- ✅ Test email sending works
- ✅ No emails going to spam
- ✅ SES sending limits reviewed (default: 200/day)

### **SES Limits:**

```bash
# Check current sending limits
aws sesv2 get-send-quota --region us-east-1

# Request limit increase for production
# AWS Support → Service limit increase → SES
```

### **Monitoring:**

```bash
# Set up CloudWatch alarms for:
# - Bounce rate > 5%
# - Complaint rate > 0.1%
# - Daily sending approaching limit
```

---

## 📊 **Cost Estimate**

### **AWS Services:**

- **Route53 Hosted Zone:** $0.50/month
- **SES Email Sending:** $0.10 per 1000 emails
- **ACM Certificate:** Free
- **CloudWatch Metrics:** ~$0.30/month

**Total:** ~$1-5/month depending on email volume

---

## 🔗 **Next Steps After Domain Setup**

1. **Test full auth flow** with real email addresses
2. **Configure custom Cognito domain** (auth.yourdomain.com)
3. **Set up API Gateway custom domain** (api.yourdomain.com)
4. **Deploy web dashboard** to app.yourdomain.com
5. **Monitor email reputation** in SES console

**Your domain is now ready for production-grade email delivery!** 🎉
