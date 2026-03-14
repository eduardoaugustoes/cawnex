# 📖 Cawnex Documentation

_Comprehensive documentation for the Cawnex autonomous AI platform_

## 📋 **Quick Reference**

### **Active Development:**

- 📊 **[Enhancement Backlog](./ENHANCEMENT-BACKLOG.md)** - Organized improvements and feature requests
- 🏗️ **[Architecture V2](./ARCHITECTURE-V2.md)** - Dynasty/Court/Murder system design
- 📱 **[API Monarch Chat](./API-MONARCH-CHAT.md)** - Conversational project management API

### **Implementation Guides:**

- 🔐 **[Claude SDK](./CLAUDE-SDK.md)** - Python + Swift/iOS API reference
- 📋 **[POC 6 Plan](./POC6-PLAN.md)** - Worker Lambda + EFS + Worktrees

---

## 🎯 **Development Workflow**

### **Planning & Backlog:**

1. **Check backlog:** Review `ENHANCEMENT-BACKLOG.md` for prioritized items
2. **Weekly planning:** Pick P1 items for sprint planning
3. **Add new items:** Use the template in the backlog document
4. **Update status:** Track progress from Backlog → In Progress → Done

### **Architecture Decisions:**

- **Reference:** `ARCHITECTURE-V2.md` for system design
- **Updates:** Document major architectural changes
- **Patterns:** Extract reusable patterns to skills/scaffolds

### **Quality Standards:**

- **Security:** Follow industry best practices (current Cognito: 9.3/10)
- **Testing:** Protocol-based design for mockability
- **Performance:** Measure and optimize critical paths
- **UX:** Mobile-first, accessible design

---

## 🚀 **Current Focus Areas**

### **✅ Completed (High Quality):**

- Multi-tenant Cognito authentication (9.3/10 industry score)
- Protocol-based iOS architecture with dependency injection
- Infrastructure as Code with CDK (comprehensive)
- Dynasty/Court conceptual framework

### **🔄 Active Development:**

- API implementation for iOS service contracts
- Real-time project management features
- Agent spawning and orchestration

### **📋 Next Quarter:**

- Biometric authentication (AUTH-001)
- Session analytics & security monitoring (AUTH-002)
- Offline capability for iOS app (IOS-001)
- Enhanced monitoring & observability (INFRA-002)

---

## 🔗 **Related Resources**

### **Repositories:**

- **Main:** [eduardoaugustoes/cawnex](https://github.com/eduardoaugustoes/cawnex)
- **Skills:** [ClawHub](https://clawhub.com) for reusable patterns

### **Infrastructure:**

- **AWS Account:** 961454950210 (us-east-1)
- **Deployment:** GitHub Actions with OIDC
- **Environments:** dev, staging, prod

### **Development:**

- **iOS:** Xcode with SwiftUI + async/await patterns
- **Backend:** AWS CDK + TypeScript + Python
- **AI:** Anthropic Claude integration via REST APIs

---

## 📝 **Documentation Standards**

### **When to Document:**

- ✅ **Major architectural decisions** (update ARCHITECTURE-V2.md)
- ✅ **New API designs** (create API-\*.md files)
- ✅ **Enhancement requests** (add to ENHANCEMENT-BACKLOG.md)
- ✅ **Infrastructure patterns** (extract to skills if reusable)

### **Documentation Templates:**

- **API Design:** Follow `API-MONARCH-CHAT.md` structure
- **Architecture:** Follow `ARCHITECTURE-V2.md` patterns
- **Enhancements:** Use backlog item template with priority/effort/criteria

---

_Keep documentation current, concise, and actionable. Update this README when adding new documentation categories._
