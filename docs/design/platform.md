# 📱 Platform Architecture — Web + iOS + Android

> Full native. No cross-platform frameworks. Best UX on every surface.

---

## Principle

Each client is built with the best tools for its platform:

| Platform | Language | UI Framework | Why |
|----------|---------|-------------|-----|
| **Web** | TypeScript | React + Vite + shadcn/ui | Industry standard, SSR-ready, fastest to iterate |
| **iOS** | Swift 6 | SwiftUI | Native performance, Apple ecosystem (widgets, Siri, shortcuts) |
| **Android** | Kotlin | Jetpack Compose | Native performance, Material 3, Google ecosystem |
| **API** | Python 3.12 | FastAPI | Claude SDK is Python-first, async native |

---

## Unified API Contract

Three native clients means the API is the **single source of truth**. Every client is generated from the same OpenAPI spec.

```
FastAPI (auto-generates openapi.json)
        │
        ├──→ openapi-typescript    → packages/api-client/    (Web)
        ├──→ swift-openapi-generator → apps/ios/Generated/   (iOS)
        └──→ openapi-generator     → apps/android/generated/ (Android)
```

**Rule**: If it's not in the API spec, it doesn't exist. No client-side business logic.

---

## Shared Backend Services

All three clients consume the same endpoints:

### REST API
```
POST   /api/v1/auth/github          ← OAuth (all platforms)
POST   /api/v1/auth/apple           ← Sign in with Apple (iOS, web)
POST   /api/v1/auth/google          ← Sign in with Google (Android, web)
POST   /api/v1/auth/refresh         ← Refresh JWT

GET    /api/v1/dashboard/stats      ← Dashboard metrics
GET    /api/v1/executions           ← List (paginated, filtered)
GET    /api/v1/executions/:id       ← Detail
POST   /api/v1/executions/:id/cancel
POST   /api/v1/executions/:id/retry

GET    /api/v1/issues               ← Pending approvals
POST   /api/v1/issues/:id/approve   ← Approve refined issue
POST   /api/v1/issues/:id/reject    ← Reject with feedback

GET    /api/v1/repos                ← Connected repositories
GET    /api/v1/agents               ← Agent status + config
PATCH  /api/v1/agents/:id           ← Update agent config

GET    /api/v1/tenant/settings      ← BYOL config
PATCH  /api/v1/tenant/settings      ← Update BYOL config
POST   /api/v1/tenant/test-key      ← Test LLM API key

POST   /api/v1/devices/register     ← Register push token (mobile)
DELETE /api/v1/devices/:id          ← Unregister device
```

### WebSocket
```
WS /ws/executions/:id               ← Real-time execution events
WS /ws/dashboard                     ← Live dashboard updates
```

### Push Notifications
```
APNs (iOS)  ← Execution complete, PR ready, approval needed
FCM (Android) ← Same events
```

---

## Platform-Specific Features

### iOS Only
| Feature | Implementation |
|---------|---------------|
| **Widgets** | WidgetKit — execution count, success rate on home screen |
| **Live Activities** | Show running execution progress on lock screen |
| **Siri Shortcuts** | "Hey Siri, approve the latest Cawnex issue" |
| **Haptic feedback** | On approve/reject actions |
| **Face ID / Touch ID** | Biometric auth for sensitive actions |
| **Spotlight Search** | Search executions from iOS search |
| **App Clips** | Quick approve flow from push notification |

### Android Only
| Feature | Implementation |
|---------|---------------|
| **Widgets** | Glance widgets — execution stats on home screen |
| **Quick Settings Tile** | Toggle Cawnex agent status |
| **Material You** | Dynamic color from wallpaper |
| **Notification Actions** | Approve/reject directly from notification |
| **Fingerprint / Face Unlock** | Biometric auth |
| **Deep Links** | Open execution from any URL |
| **Picture-in-Picture** | Watch execution stream while using other apps |

### Web Only
| Feature | Implementation |
|---------|---------------|
| **Full dashboard** | Charts, tables, detailed analytics |
| **Code viewer** | Monaco editor for viewing agent output |
| **Diff viewer** | PR diff visualization |
| **Keyboard shortcuts** | Power user workflow |
| **Desktop notifications** | Browser notifications for events |

---

## Auth Strategy (Multi-Platform)

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│     Web      │  │     iOS      │  │   Android    │
│              │  │              │  │              │
│ GitHub OAuth │  │ GitHub OAuth │  │ GitHub OAuth │
│              │  │ Apple Sign-in│  │ Google Sign-in│
│              │  │ Face ID      │  │ Biometric    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────────┼──────────────────┘
                         │
                         ▼
              ┌─────────────────┐
              │   Cawnex API    │
              │                 │
              │ JWT (access +   │
              │  refresh token) │
              │                 │
              │ Same user, same │
              │ tenant, any     │
              │ device          │
              └─────────────────┘
```

All platforms use JWT. Platform-specific auth methods resolve to the same Cawnex user.

---

## Notification Architecture

```
Worker (execution completes)
    │
    ▼
Notification Service
    │
    ├──→ WebSocket (web dashboard — instant)
    ├──→ APNs (iOS push notification)
    ├──→ FCM (Android push notification)
    └──→ Slack/Discord webhook (integrations)
```

### Push Notification Types

| Event | Title | Body | Action |
|-------|-------|------|--------|
| Refinement complete | "Issue #42 refined" | "Ready for your approval" | Deep link to approve screen |
| Execution complete | "PR #7 ready" | "QA approved. View PR?" | Deep link to PR |
| Execution failed | "Execution failed" | "Dev crow failed on repo-api" | Deep link to detail |
| Budget warning | "Budget 80% used" | "$160 of $200 used this month" | Deep link to settings |

---

## iOS Tech Stack

| Concern | Tool | Version |
|---------|------|---------|
| Language | Swift | 6.0 |
| UI | SwiftUI | Latest |
| Min deployment | iOS 17 | |
| Architecture | MVVM + Repository | |
| Networking | URLSession + async/await | Native |
| WebSocket | URLSessionWebSocketTask | Native |
| JSON | Codable (generated from OpenAPI) | Native |
| Auth | AuthenticationServices (Apple), ASWebAuthenticationSession (GitHub) | Native |
| Push | UserNotifications + APNs | Native |
| Storage | SwiftData (local cache) | Native |
| Keychain | Keychain Services (tokens, API keys) | Native |
| Widgets | WidgetKit | Native |
| Live Activities | ActivityKit | Native |
| Testing | XCTest + Swift Testing | Native |
| CI/CD | Xcode Cloud or Fastlane + GitHub Actions | |

### iOS Architecture

```
Cawnex/
├── App/
│   └── CawnexApp.swift              ← App entry, deep links, push setup
├── Core/
│   ├── Network/
│   │   ├── APIClient.swift          ← Generated from OpenAPI
│   │   ├── WebSocketManager.swift   ← Real-time events
│   │   └── AuthInterceptor.swift    ← JWT refresh, retry 401s
│   ├── Auth/
│   │   ├── AuthService.swift        ← Login, logout, token management
│   │   ├── KeychainManager.swift    ← Secure token storage
│   │   └── BiometricAuth.swift      ← Face ID / Touch ID
│   ├── Push/
│   │   ├── PushService.swift        ← Register, handle notifications
│   │   └── NotificationHandler.swift← Route to correct screen
│   └── Models/                      ← Generated from OpenAPI
│       ├── Execution.swift
│       ├── Issue.swift
│       ├── Tenant.swift
│       └── DashboardStats.swift
├── Features/
│   ├── Dashboard/
│   │   ├── DashboardView.swift
│   │   ├── DashboardViewModel.swift
│   │   ├── StatsCard.swift
│   │   └── ExecutionChart.swift
│   ├── Executions/
│   │   ├── ExecutionListView.swift
│   │   ├── ExecutionListViewModel.swift
│   │   ├── ExecutionDetailView.swift
│   │   ├── ExecutionDetailViewModel.swift
│   │   └── EventTimelineView.swift
│   ├── Issues/
│   │   ├── IssueListView.swift
│   │   ├── ApproveRejectView.swift
│   │   └── IssueViewModel.swift
│   ├── Settings/
│   │   ├── SettingsView.swift
│   │   ├── BYOLSetupView.swift
│   │   └── AgentConfigView.swift
│   └── Onboarding/
│       ├── OnboardingView.swift
│       └── GitHubConnectView.swift
├── Components/
│   ├── CrowStatusBadge.swift
│   ├── CostLabel.swift
│   ├── LiveStreamView.swift
│   └── ApproveButton.swift          ← Haptic feedback
├── Widgets/
│   ├── CawnexWidget.swift           ← Home screen widget
│   └── LiveActivityView.swift       ← Lock screen execution progress
└── Resources/
    ├── Assets.xcassets
    └── Localizable.strings
```

---

## Android Tech Stack

| Concern | Tool | Version |
|---------|------|---------|
| Language | Kotlin | 2.1 |
| UI | Jetpack Compose | Latest |
| Min SDK | API 28 (Android 9) | |
| Architecture | MVVM + Repository (Clean Architecture) | |
| Networking | Retrofit + OkHttp | |
| WebSocket | OkHttp WebSocket | |
| JSON | kotlinx.serialization (generated from OpenAPI) | |
| Auth | Credential Manager (Google), Custom Tab (GitHub) | |
| Push | Firebase Cloud Messaging (FCM) | |
| Storage | Room (local cache) | |
| Secure Storage | EncryptedSharedPreferences / Keystore | |
| Widgets | Glance (Jetpack) | |
| DI | Hilt (Dagger) | |
| Navigation | Compose Navigation (type-safe) | |
| Testing | JUnit5 + Compose Testing + Turbine (flows) | |
| CI/CD | Fastlane + GitHub Actions | |

### Android Architecture

```
app/src/main/java/ai/cawnex/
├── CawnexApp.kt                     ← Application class, Hilt setup
├── MainActivity.kt                  ← Single activity, Compose host
├── core/
│   ├── network/
│   │   ├── CawnexApi.kt             ← Retrofit interface (generated)
│   │   ├── WebSocketClient.kt       ← Real-time events
│   │   ├── AuthInterceptor.kt       ← JWT refresh, retry 401s
│   │   └── NetworkModule.kt         ← Hilt DI module
│   ├── auth/
│   │   ├── AuthRepository.kt
│   │   ├── TokenManager.kt          ← EncryptedSharedPreferences
│   │   └── BiometricManager.kt
│   ├── push/
│   │   ├── CawnexFirebaseService.kt ← FCM handler
│   │   └── NotificationRouter.kt    ← Deep link to correct screen
│   └── models/                      ← Generated from OpenAPI
│       ├── Execution.kt
│       ├── Issue.kt
│       ├── Tenant.kt
│       └── DashboardStats.kt
├── features/
│   ├── dashboard/
│   │   ├── DashboardScreen.kt
│   │   ├── DashboardViewModel.kt
│   │   ├── StatsCard.kt
│   │   └── ExecutionChart.kt
│   ├── executions/
│   │   ├── ExecutionListScreen.kt
│   │   ├── ExecutionListViewModel.kt
│   │   ├── ExecutionDetailScreen.kt
│   │   ├── ExecutionDetailViewModel.kt
│   │   └── EventTimeline.kt
│   ├── issues/
│   │   ├── IssueListScreen.kt
│   │   ├── ApproveRejectScreen.kt
│   │   └── IssueViewModel.kt
│   ├── settings/
│   │   ├── SettingsScreen.kt
│   │   ├── BYOLSetupScreen.kt
│   │   └── AgentConfigScreen.kt
│   └── onboarding/
│       ├── OnboardingScreen.kt
│       └── GitHubConnectScreen.kt
├── components/
│   ├── CrowStatusBadge.kt
│   ├── CostLabel.kt
│   ├── LiveStreamView.kt
│   └── ApproveButton.kt
├── widgets/
│   ├── CawnexWidget.kt              ← Glance widget
│   └── CawnexWidgetReceiver.kt
├── navigation/
│   ├── CawnexNavHost.kt
│   └── Routes.kt
└── di/
    ├── AppModule.kt
    ├── NetworkModule.kt
    └── RepositoryModule.kt
```

---

## Updated Monorepo Structure

```
cawnex/
│
├── README.md
├── CAWNEX.md
├── LICENSE
├── docker-compose.yml
├── .github/
│   └── workflows/
│       ├── api-ci.yml               ← Python lint + test
│       ├── web-ci.yml               ← TS lint + test + build
│       ├── ios-ci.yml               ← Swift build + test (Xcode Cloud or GH Actions)
│       ├── android-ci.yml           ← Kotlin build + test
│       └── deploy.yml               ← Deploy API + web
│
├── packages/                        ← Shared Python packages
│   ├── core/                        ← Models, schemas, enums
│   ├── providers/                   ← BYOL abstraction
│   └── git-ops/                     ← Git operations
│
├── apps/
│   ├── api/                         ← 🐍 FastAPI backend
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── alembic/
│   │   └── src/cawnex_api/
│   │       ├── main.py
│   │       ├── routes/
│   │       │   ├── auth.py          ← GitHub + Apple + Google OAuth
│   │       │   ├── webhooks.py
│   │       │   ├── executions.py
│   │       │   ├── issues.py
│   │       │   ├── dashboard.py
│   │       │   ├── devices.py       ← Push token registration
│   │       │   └── ws.py            ← WebSocket endpoints
│   │       ├── services/
│   │       │   ├── push.py          ← APNs + FCM unified
│   │       │   ├── auth.py
│   │       │   └── queue.py
│   │       └── middleware/
│   │
│   ├── worker/                      ← ⚙️ Agent runtime
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── src/cawnex_worker/
│   │       ├── murder.py
│   │       ├── guard.py
│   │       ├── retry.py
│   │       ├── crows/
│   │       └── tools/
│   │
│   ├── web/                         ← 🌐 React web app
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── pages/
│   │       ├── components/
│   │       ├── lib/
│   │       │   ├── api/             ← Generated from OpenAPI
│   │       │   ├── ws.ts
│   │       │   └── auth.ts
│   │       └── styles/
│   │
│   ├── ios/                         ← 🍎 Native iOS (Swift + SwiftUI)
│   │   ├── Cawnex.xcodeproj/
│   │   ├── Cawnex/
│   │   │   ├── App/
│   │   │   ├── Core/
│   │   │   │   ├── Network/
│   │   │   │   ├── Auth/
│   │   │   │   ├── Push/
│   │   │   │   └── Models/         ← Generated from OpenAPI
│   │   │   ├── Features/
│   │   │   │   ├── Dashboard/
│   │   │   │   ├── Executions/
│   │   │   │   ├── Issues/
│   │   │   │   ├── Settings/
│   │   │   │   └── Onboarding/
│   │   │   ├── Components/
│   │   │   ├── Widgets/
│   │   │   └── Resources/
│   │   ├── CawnexTests/
│   │   ├── CawnexWidgetExtension/
│   │   └── Gemfile                  ← Fastlane
│   │
│   └── android/                     ← 🤖 Native Android (Kotlin + Compose)
│       ├── app/
│       │   ├── build.gradle.kts
│       │   └── src/
│       │       ├── main/
│       │       │   ├── java/ai/cawnex/
│       │       │   │   ├── core/
│       │       │   │   │   ├── network/
│       │       │   │   │   ├── auth/
│       │       │   │   │   ├── push/
│       │       │   │   │   └── models/   ← Generated from OpenAPI
│       │       │   │   ├── features/
│       │       │   │   │   ├── dashboard/
│       │       │   │   │   ├── executions/
│       │       │   │   │   ├── issues/
│       │       │   │   │   ├── settings/
│       │       │   │   │   └── onboarding/
│       │       │   │   ├── components/
│       │       │   │   ├── widgets/
│       │       │   │   ├── navigation/
│       │       │   │   └── di/
│       │       │   ├── res/
│       │       │   └── AndroidManifest.xml
│       │       └── test/
│       ├── build.gradle.kts
│       ├── settings.gradle.kts
│       ├── gradle.properties
│       └── Gemfile                  ← Fastlane
│
├── prompts/                         ← Agent system prompts
│   ├── refinement.md
│   ├── dev.md
│   ├── qa.md
│   └── docs.md
│
├── specs/                           ← 🆕 API spec (source of truth for all clients)
│   ├── openapi.json                 ← Auto-generated from FastAPI
│   └── generate.sh                  ← Regenerate all client types
│
├── docs/                            ← Documentation (already done ✅)
│
├── scripts/
│   ├── setup.sh
│   ├── seed.py
│   ├── generate-clients.sh          ← 🆕 Generate TS + Swift + Kotlin from OpenAPI
│   └── benchmark.py
│
├── tests/                           ← Integration tests
│
├── pyproject.toml                   ← Python workspace (uv)
├── uv.lock
├── pnpm-workspace.yaml              ← Node workspace (web only)
├── .gitignore
├── .pre-commit-config.yaml
├── ruff.toml
└── mypy.ini
```

---

## Client Code Generation Pipeline

```bash
#!/bin/bash
# scripts/generate-clients.sh

# 1. Export OpenAPI spec from running API
curl http://localhost:8000/openapi.json > specs/openapi.json

# 2. Generate TypeScript types (web)
npx openapi-typescript specs/openapi.json \
  -o apps/web/src/lib/api/types.ts

# 3. Generate Swift types (iOS)
swift-openapi-generator generate specs/openapi.json \
  --output-directory apps/ios/Cawnex/Core/Models/Generated/

# 4. Generate Kotlin types (Android)
openapi-generator-cli generate \
  -i specs/openapi.json \
  -g kotlin \
  -o apps/android/app/src/main/java/ai/cawnex/core/models/generated/ \
  --additional-properties=library=jvm-retrofit2,serializationLibrary=kotlinx_serialization
```

**One command, all three clients stay in sync.** Change the API → run script → type errors tell you what to update.

---

## Build & Deploy Summary

| App | Build | Deploy | CI |
|-----|-------|--------|-----|
| **API** | Docker | AWS ECS / Fly.io | GitHub Actions |
| **Worker** | Docker | AWS ECS / Fly.io | GitHub Actions |
| **Web** | Vite build → static | Cloudflare Pages | GitHub Actions |
| **iOS** | Xcode | TestFlight → App Store | Xcode Cloud / Fastlane |
| **Android** | Gradle | Play Console (internal → prod) | GitHub Actions / Fastlane |

---

## Development Requirements

| Platform | You Need | On This VPS? |
|----------|---------|-------------|
| API + Worker | Python 3.12, Docker | ✅ Yes |
| Web | Node 22, pnpm | ✅ Yes |
| iOS | Mac with Xcode 16 | ❌ Needs Mac |
| Android | Android Studio + JDK 21 | ⚠️ Can build on VPS but no emulator |

### iOS Development Reality
You **need a Mac** for iOS. Options:
- Physical Mac (MacBook, Mac Mini)
- **MacStadium** / **AWS Mac instances** (cloud Mac, ~$1/hr)
- **Codemagic** (CI/CD that includes Mac build machines)
- GitHub Actions has macOS runners for CI

### Android Development
Can build on Linux (Gradle + JDK). But for UI development:
- **Android Studio** on a local machine (emulator)
- Or use a physical Android device connected via ADB

---

## Timeline Impact

| Phase | Without Mobile | With Native Mobile |
|-------|---------------|-------------------|
| Phase 0 (Foundation) | 2 weeks | 2 weeks (no change — API only) |
| Phase 1 (Core Loop) | 3 weeks | 3 weeks (no change — web + API) |
| Phase 2 (The Murder) | 4 weeks | 4 weeks (no change) |
| **Phase 3 (SaaS)** | **4 weeks** | **+6 weeks** (iOS: 4w, Android: 4w, parallel = 6w) |
| **Total** | **13 weeks** | **19 weeks** |

Mobile adds ~6 weeks but can be parallelized with Phase 3 web work.

---

Want me to commit this updated structure to the repo?