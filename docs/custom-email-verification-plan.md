# Custom Domain Email Verification Plan for Cawnex

## 🎯 **Objective**

Implement custom domain email verification for Cawnex similar to the caioo system, using `noreply@cawnex.ai` instead of AWS's default verification emails.

## 📧 **Current State Analysis**

### **What's Already Built**

The infrastructure is **already prepared** for custom domain email verification:

#### **✅ Domain Stack (`CawnexDomainStack`)**

- **SES Domain Identity** with DKIM signing enabled
- **SPF Record:** `v=spf1 include:amazonses.com ~all`
- **DMARC Policy** with appropriate security settings
- **Email sender addresses** pre-configured:
  ```typescript
  noreply: `noreply@${domainName}`;
  support: `support@${domainName}`;
  security: `security@${domainName}`;
  admin: `admin@${domainName}`;
  ```

#### **✅ Auth Stack (`CawnexAuthStack`)**

- **Conditional SES integration** already implemented (lines 67-76)
- **Custom verification message** configured:
  ```typescript
  emailSubject: "Verify your Cawnex account";
  emailBody: "Thanks for signing up! Your verification code is {####}. This code expires in 24 hours.";
  ```

### **🔍 Current Issue**

The email shown (`no-reply@verificationemail.com`) suggests the system is either:

1. **Using Cognito default emails** (domain params not provided during deployment)
2. **Using a third-party service** like MailerSend for custom domain emails

## 🛠️ **Implementation Plan**

### **Phase 1: Domain Setup & Verification**

#### **1.1 Deploy Domain Stack with Custom Domain**

```bash
# Deploy with domain configuration
cd infra
npx cdk deploy CawnexDomainStack-prod \
  --context domainName=cawnex.ai \
  --context hostedZoneId=Z1043464P7MAZULFOWWY \
  --context stage=prod
```

#### **1.2 Verify SES Domain Setup**

```bash
# Check domain verification status
aws ses get-identity-verification-attributes \
  --identities cawnex.ai \
  --region us-east-1

# Verify DKIM configuration
aws ses get-identity-dkim-attributes \
  --identities cawnex.ai \
  --region us-east-1
```

#### **1.3 Test Email Sending**

```bash
# Send test email from noreply@cawnex.ai
aws ses send-email \
  --source noreply@cawnex.ai \
  --destination ToAddresses=test@example.com \
  --message Subject={Data="Test Email"},Body={Text={Data="Testing custom domain"}} \
  --region us-east-1
```

### **Phase 2: Auth Stack Integration**

#### **2.1 Deploy Auth Stack with SES Integration**

```bash
# Deploy auth stack with domain parameters
npx cdk deploy CawnexAuthStack-prod \
  --context domainName=cawnex.ai \
  --context stage=prod
```

#### **2.2 Verify Cognito Configuration**

Check the deployed Cognito configuration:

```typescript
// Expected configuration after deployment
email: cognito.UserPoolEmail.withSES({
  fromEmail: "noreply@cawnex.ai",
  fromName: "Cawnex",
  sesRegion: "us-east-1",
  sesVerifiedDomain: "cawnex.ai",
});
```

### **Phase 3: Email Template Enhancement**

#### **3.1 Custom Email Templates (Optional)**

Create enhanced email templates beyond the basic code format:

```typescript
// Enhanced verification email
userVerification: {
  emailSubject: "🔐 Verify your Cawnex account",
  emailBody: `
    <h2>Welcome to Cawnex!</h2>
    <p>Thanks for signing up for Cawnex - the autonomous development platform.</p>
    <p><strong>Your verification code is: {####}</strong></p>
    <p>This code expires in 24 hours.</p>
    <p>If you didn't create this account, please ignore this email.</p>
    <hr>
    <p><small>© 2024 Cawnex AI - Autonomous Software Development</small></p>
  `,
  emailStyle: cognito.VerificationEmailStyle.CODE,
}
```

#### **3.2 Additional Email Templates**

Configure templates for other user flows:

```typescript
// Password reset email
accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
userInvitation: {
  emailSubject: "Welcome to Cawnex - Complete your account",
  emailBody: "Your temporary password is {####}. Please sign in and change it.",
}
```

### **Phase 4: Advanced Email Features**

#### **4.1 Custom Lambda Email Sender (Optional)**

For maximum control, create a custom Lambda function for email sending:

```python
# lambdas/custom-email-sender/handler.py
import boto3
import json
from typing import Dict, Any

ses = boto3.client('ses', region_name='us-east-1')

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Custom email sender for enhanced verification emails."""

    trigger_source = event['triggerSource']

    if trigger_source == 'CustomMessage_SignUp':
        # Customize signup verification email
        code = event['request']['codeParameter']
        email = event['request']['userAttributes']['email']

        # Send via SES with custom template
        response = ses.send_templated_email(
            Source='noreply@cawnex.ai',
            Destination={'ToAddresses': [email]},
            Template='CawnexVerification',
            TemplateData=json.dumps({
                'verification_code': code,
                'user_email': email
            })
        )

        # Suppress Cognito's default email
        event['response']['emailSubject'] = ""
        event['response']['emailMessage'] = ""

    return event
```

#### **4.2 SES Email Templates**

Create reusable SES templates:

```json
{
  "TemplateName": "CawnexVerification",
  "Subject": "🔐 Verify your Cawnex account",
  "HtmlPart": "<!DOCTYPE html><html>...",
  "TextPart": "Welcome to Cawnex!\n\nYour verification code is: {{verification_code}}"
}
```

### **Phase 5: Monitoring & Analytics**

#### **5.1 Email Delivery Monitoring**

Set up CloudWatch monitoring for email delivery:

```typescript
// Add to Domain Stack
const emailMetrics = new cloudwatch.Dashboard(this, "EmailMetrics", {
  dashboardName: `cawnex-email-${stage}`,
  widgets: [
    [
      new cloudwatch.GraphWidget({
        title: "SES Email Metrics",
        left: [ses.metric("Send"), ses.metric("Delivery")],
        right: [ses.metric("Bounce"), ses.metric("Complaint")],
      }),
    ],
  ],
});
```

#### **5.2 Email Event Tracking**

Configure SES event publishing:

```typescript
// Add event destinations for detailed tracking
const configSet = new ses.ConfigurationSet(this, "EmailConfigSet", {
  configurationSetName: `cawnex-${stage}`,
  sendingEnabled: true,
});

// Track bounces, complaints, deliveries
configSet.addEventDestination("CloudWatchEvents", {
  destination: ses.EventDestination.cloudWatchDestination([
    ses.CloudWatchDimensionSource.messageTag("campaign"),
    ses.CloudWatchDimensionSource.emailAddress(),
  ]),
});
```

## 🚀 **Quick Implementation (Immediate)**

### **Option A: Enable Existing SES Integration**

The fastest path is to simply deploy with domain parameters:

```bash
# 1. Deploy domain stack (if not already done)
npx cdk deploy CawnexDomainStack-prod --context domainName=cawnex.ai

# 2. Redeploy auth stack with domain integration
npx cdk deploy CawnexAuthStack-prod --context domainName=cawnex.ai

# Result: Verification emails will come from noreply@cawnex.ai
```

### **Option B: Use Third-Party Service (Current)**

If the `no-reply@verificationemail.com` is intentional, it might be using:

- **MailerSend** - Custom domain support for Cognito
- **SendGrid** - SMTP integration with Cognito
- **Amazon WorkMail** - Full email hosting solution

## 📋 **Domain Requirements Checklist**

### **DNS Configuration**

- [ ] **Domain ownership** verified in Route53
- [ ] **SPF record** configured: `v=spf1 include:amazonses.com ~all`
- [ ] **DKIM signatures** enabled and DNS records added
- [ ] **DMARC policy** configured for email authentication

### **SES Setup**

- [ ] **Domain verified** in SES (us-east-1 region)
- [ ] **Sending limits** reviewed and requested if needed
- [ ] **IAM permissions** for Cognito to send via SES
- [ ] **Configuration set** created for monitoring

### **Cognito Integration**

- [ ] **Custom domain** configured in UserPool email settings
- [ ] **Verification templates** customized with branding
- [ ] **Sender identity** set to `noreply@cawnex.ai`
- [ ] **Email style** configured (CODE vs LINK)

## 🔒 **Security Considerations**

### **Email Authentication**

- **SPF:** Prevents email spoofing
- **DKIM:** Ensures email integrity
- **DMARC:** Provides policy for failed authentication

### **Rate Limiting**

- **SES sending limits:** Monitor daily/hourly quotas
- **Cognito limits:** Respect verification attempt limits
- **Abuse prevention:** Monitor bounce/complaint rates

### **Privacy & Compliance**

- **GDPR compliance:** Email consent and opt-out mechanisms
- **CAN-SPAM:** Include physical address and unsubscribe options
- **Data retention:** Configure appropriate email log retention

## 📊 **Success Metrics**

### **Email Deliverability**

- **Delivery rate:** >95% successful delivery
- **Bounce rate:** <2% bounces
- **Complaint rate:** <0.1% spam complaints
- **Open rates:** Track verification email engagement

### **User Experience**

- **Verification completion rate:** % of users who verify
- **Time to verification:** Average time from signup to verification
- **Support tickets:** Reduction in email-related issues

## 🎯 **Next Steps**

### **Immediate (This Week)**

1. **Verify current domain setup** - Check if cawnex.ai is already configured in SES
2. **Deploy with domain context** - Redeploy auth stack with domain parameters
3. **Test verification flow** - Create test account and verify email experience

### **Short Term (Next Sprint)**

1. **Enhance email templates** - Add branding and improved messaging
2. **Set up monitoring** - CloudWatch dashboards for email metrics
3. **Configure advanced features** - DMARC, event tracking, analytics

### **Long Term (Next Quarter)**

1. **Custom email templates** - SES templating system
2. **Advanced automation** - Welcome series, onboarding emails
3. **International domains** - Multi-region SES setup for global users

---

**This plan leverages the existing infrastructure investments and provides a clear path to professional, branded email verification that matches the caioo experience.** 🚀
