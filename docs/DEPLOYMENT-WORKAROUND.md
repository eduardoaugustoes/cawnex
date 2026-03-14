# 🚧 Deployment Workaround: Circular Dependency Fix

**Issue:** CDK has a circular dependency between Cognito, API Gateway, and Lambda that prevents deployment.

**Solution:** Two-step deployment process.

---

## 🔄 **Circular Dependency Details**

**The Problem:**
```
UserPool → PostConfirmation Lambda → API Function → JWT Authorizer → UserPool Clients → UserPool
```

CDK cannot resolve this dependency cycle, causing deployment failures.

---

## ✅ **Two-Step Deployment Process**

### **Step 1: Deploy Infrastructure (No Auth)** 🚀

**What gets deployed:**
- ✅ Cognito User Pool with clients
- ✅ API Gateway with Lambda integration  
- ✅ DynamoDB, S3, SQS, ECS infrastructure
- ✅ PostConfirmation Lambda for tenant creation
- ❌ **NO JWT Authentication** on API routes

**Deploy:**
```bash
# Via GitHub Actions
Go to: https://github.com/eduardoaugustoes/cawnex/actions
Run: "🚀 Deploy Dev + Update iOS Config (Complete)"

# OR locally
cd infra
cdk deploy Cawnex-dev
```

**Result:** Infrastructure deployed, iOS app configured, but API has **no authentication**.

### **Step 2: Add JWT Authentication** 🔐

**After Step 1 completes, run:**
```bash
cd cawnex
./scripts/add-api-auth.sh dev
```

**What this does:**
- Creates JWT Authorizer via AWS CLI
- Configures it to validate Cognito tokens
- Adds authorization to API proxy routes
- Leaves `/health` endpoint public (monitoring)

**Result:** API fully secured with Cognito JWT validation.

---

## 📱 **Full Deployment Process**

### **1. Deploy Infrastructure**
```bash
# GitHub Actions workflow runs automatically
# Takes ~8-10 minutes
# iOS config automatically updated
```

### **2. Add API Security**  
```bash
./scripts/add-api-auth.sh dev
# Takes ~30 seconds
# API now requires Cognito tokens
```

### **3. Build iOS App**
```bash
cd apps/ios
open Cawnex.xcodeproj
# Product → Run in Xcode
```

### **4. Test Complete Flow**
```
iOS app → Sign up → Email verification → Login → Authenticated API calls ✅
```

---

## 🔮 **Future Improvements**

### **Option A: Separate CDK Stacks**
```typescript
// Stack 1: Core infrastructure (User Pool, API, Lambda)
// Stack 2: Security layer (JWT Authorizer, route authorization)
```

### **Option B: CDK Custom Resources**
```typescript
// Use CDK Custom Resource to add JWT auth after deployment
// Eliminates manual script step
```

### **Option C: CloudFormation Nested Stacks**
```yaml
# Parent stack creates dependencies in correct order
# Child stacks handle specific components
```

---

## ⚠️ **Security Note**

**During Step 1 → Step 2 gap:**
- API endpoints are **temporarily unprotected**
- Only `/health` should be accessed during this window
- **Complete Step 2 immediately** after Step 1
- Consider running both steps in same CI/CD pipeline

---

## 🎯 **Summary**

**This workaround allows successful deployment while maintaining security:**

1. ✅ **Deploy infrastructure** without auth (avoids circular dependency)
2. ✅ **Add authentication** via AWS CLI (manual script)  
3. ✅ **Test full flow** with secure API

**Total time:** ~10 minutes automated + ~1 minute manual step

**Long-term:** Refactor to proper CDK stack structure to eliminate manual step.