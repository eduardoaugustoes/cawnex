# 🚀 Cawnex Deployment Process

**Current approach:** Two-stack deployment + Post-deployment trigger setup

---

## 🎯 **Why This Architecture?**

### **Circular Dependency Challenge:**

```
UserPool → PostConfirmation Lambda → IAM permissions → UserPool
```

CDK cannot resolve this dependency cycle automatically.

### **Solution: Deploy + Configure Pattern:**

1. ✅ **Deploy infrastructure** without trigger attachment
2. ✅ **Add trigger manually** via AWS CLI after deployment
3. ✅ **Fully automated** in GitHub Actions workflow

---

## 🏗️ **Architecture Overview**

### **CawnexAuthStack-dev** 🔐

```typescript
✅ DynamoDB Table (multi-tenant)
✅ Cognito User Pool + iOS/Web clients
✅ PostConfirmation Lambda (with DynamoDB permissions)
✅ User Pool Domain
✅ CloudFormation exports
❌ NO trigger attachment (done post-deployment)
```

### **Cawnex-dev** 🚀

```typescript
✅ API Gateway + Lambda + JWT Authorizer
✅ S3 + SQS + ECS infrastructure
✅ CloudFront CDN
✅ Imports DynamoDB table from AuthStack
```

### **Post-Deployment Setup** 🔧

```bash
✅ PostConfirmation trigger attachment
✅ Lambda invoke permissions for Cognito
✅ Verification of trigger functionality
```

---

## 🚀 **Deployment Steps (Automated)**

### **GitHub Actions Workflow:**

#### **Step 1: Deploy AuthStack**

```bash
npx cdk deploy CawnexAuthStack-dev
# Creates: Cognito + DynamoDB + Lambda (no trigger)
```

#### **Step 2: Deploy MainStack**

```bash
npx cdk deploy Cawnex-dev
# Creates: API + Infrastructure (imports table)
```

#### **Step 3: Setup PostConfirmation Trigger**

```bash
./scripts/setup-post-confirmation-trigger.sh dev
# Configures: Lambda trigger + permissions
```

#### **Step 4: Update iOS Configuration**

```bash
# Automatically updates AppConfiguration.swift
# with deployed UserPoolId, ClientId, ApiUrl
```

---

## 📋 **Manual Deployment (Local)**

### **Prerequisites:**

```bash
# AWS credentials configured
aws configure list

# CDK installed and bootstrapped
npx cdk --version
```

### **Deploy:**

```bash
cd infra

# Deploy both stacks
npx cdk deploy CawnexAuthStack-dev --context stage=dev
npx cdk deploy Cawnex-dev --context stage=dev

# Setup trigger
cd ..
./scripts/setup-post-confirmation-trigger.sh dev

# Update iOS config
./scripts/update-ios-config.sh dev
```

---

## ✅ **Verification Steps**

### **1. Check Stack Status:**

```bash
aws cloudformation describe-stacks \
    --stack-name CawnexAuthStack-dev \
    --query 'Stacks[0].StackStatus'
# Expected: CREATE_COMPLETE

aws cloudformation describe-stacks \
    --stack-name Cawnex-dev \
    --query 'Stacks[0].StackStatus'
# Expected: CREATE_COMPLETE
```

### **2. Verify PostConfirmation Trigger:**

```bash
USER_POOL_ID=$(aws cloudformation describe-stacks \
    --stack-name CawnexAuthStack-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
    --output text)

aws cognito-idp describe-user-pool \
    --user-pool-id $USER_POOL_ID \
    --query 'UserPool.LambdaConfig.PostConfirmation'
# Expected: Lambda function ARN
```

### **3. Test API Health:**

```bash
API_URL=$(aws cloudformation describe-stacks \
    --stack-name Cawnex-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontUrl`].OutputValue' \
    --output text)

curl -sf "$API_URL/health"
# Expected: {"status": "healthy"}
```

---

## 🔧 **Troubleshooting**

### **Common Issues:**

#### **PostConfirmation trigger not working:**

```bash
# Re-run trigger setup
./scripts/setup-post-confirmation-trigger.sh dev

# Check Lambda logs
aws logs describe-log-groups \
    --log-group-name-prefix "/aws/lambda/cawnex-post-confirmation"
```

#### **iOS config not updated:**

```bash
# Manually update iOS configuration
./scripts/update-ios-config.sh dev
```

#### **API returns 403 Forbidden:**

```bash
# Check JWT authorizer configuration
aws apigatewayv2 get-authorizers --api-id <API_ID>
```

---

## 🎯 **End Result**

**Complete working system:**

- ✅ **Multi-tenant Cognito** with email verification
- ✅ **Automatic tenant creation** on first signup
- ✅ **JWT authentication** with tenant_id claims
- ✅ **iOS app configured** to connect to deployed backend
- ✅ **API Gateway** with proper authorization
- ✅ **Full infrastructure** ready for development

**Total deployment time:** ~10-12 minutes (automated)

**Manual steps:** **0** (everything automated in GitHub Actions)

---

## 📱 **Next Steps After Deployment**

1. **Open Xcode:** `open apps/ios/Cawnex.xcodeproj`
2. **Build and run** the iOS app
3. **Test signup:** Create new user → verify email → login
4. **Verify tenant creation:** Check DynamoDB table for tenant records
5. **Test API calls:** Verify JWT tokens contain tenant_id

**The complete authentication system is ready for production use!** 🎉
