# Cognito + MFA + Multi-Tenant Authorization

> Milestone: Auth & Onboarding
> Status: Planning
> Last updated: 2026-03-13

---

## Executive Summary

**Elevator Pitch**: Make the Cawnex iOS app know who you are, what tenant you belong to, and keep you securely signed in.

**Problem Statement**: The iOS app currently has a hardcoded user (`seedData()`) and a fake auth flow (tapping "Sign In" bypasses everything). No real authentication exists, no tenant isolation is enforced, and no session management is in place. Every feature built on top of this — API calls, data scoping, billing — is blocked until real auth works.

**Target Audience**: Cawnex founders/early users who need to sign in, have their data isolated per tenant, and stay signed in across app launches.

**Unique Selling Proposition**: Multi-tenant from day one. Every token carries a `tenant_id`. Every API request is scoped. No afterthought bolt-on.

**Success Metrics**:

- User can sign up, sign in, and sign out with email/password via Cognito
- JWT contains `custom:tenant_id`, verified on every API request
- Session persists across app launches (Keychain-stored refresh token)
- MFA enrollment and verification works (TOTP)
- Apple Sign In works through Cognito federation
- Auth state machine prevents any unauthenticated access to the main app

---

## Current State Assessment

### What exists (CDK — `infra/lib/cawnex-stack.ts`)

- Cognito User Pool with email sign-in, self-signup, email auto-verify
- iOS app client with SRP auth flow + OAuth authorization code grant
- Callback URL: `cawnex://auth/callback`
- Cognito domain prefix: `cawnex-{stage}`
- Apple Sign In commented out (provider not configured)
- **Missing**: `custom:tenant_id` attribute, MFA config, JWT authorizer on API GW, post-confirmation trigger

### What exists (iOS app)

- `SignInScreen` — email/password form + Apple Sign In button (UI only, no Cognito calls)
- `SplashScreen` — animation, then navigates to sign-in
- `AppRouter` — three states: `.splash`, `.signIn`, `.main` (hardcoded transitions)
- `AppStore` — `seedData()` creates a fake user, no real auth
- `User` model — `id`, `name`, `email` (no `tenantId`)
- `Core/Auth/` directory — exists but empty
- Service pattern established: Protocol + InMemory implementation (e.g., `ProjectService`)

### What exists (Architecture docs)

- Multi-tenant isolation documented: DynamoDB `T#<tenant_id>`, S3 `tenants/<tenant_id>/`, Cognito `custom:tenant_id`
- Auth flow diagram: iOS -> Cognito -> JWT -> API GW (JWT authorizer) -> Lambda
- Security section specifies: short-lived access tokens, refresh rotation

---

## Goal 1: Working Cognito Sign-In with Multi-Tenant Context

**Objective**: A user can sign up, sign in, and sign out using email/password. On first sign-up, a tenant is automatically created. The JWT carries `tenant_id`. The iOS app has a real auth state machine. Session persists across launches.

**Timeline**: ~2 weeks (4 MVIs, each 2-3 days)

---

### MVI 1.1: CDK Auth Infrastructure

**Value**: Backend is ready to issue tenant-scoped JWTs and authorize API requests.

**Increment**: CDK stack gains `custom:tenant_id` attribute, post-confirmation Lambda trigger for tenant initialization, and JWT authorizer on API Gateway.

**Verification**:

- [ ] `cdk deploy` succeeds with all new resources
- [ ] New user sign-up in Cognito Console triggers post-confirmation Lambda
- [ ] Lambda creates `T#<tenant_id> / PROFILE` record in DynamoDB
- [ ] Lambda writes `custom:tenant_id` back to the Cognito user
- [ ] JWT authorizer rejects requests without valid token (returns 401)
- [ ] JWT authorizer passes `tenant_id` claim to Lambda context

**Tasks**:

| #   | Task                                    | Human Est | Description                                                                                                                                                                                                                                                                                             |
| --- | --------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Add `custom:tenant_id` to User Pool     | 2h        | Add custom string attribute to Cognito User Pool in CDK. Mutable, required after first write.                                                                                                                                                                                                           |
| 2   | Create post-confirmation Lambda trigger | 4h        | Python Lambda: on `PostConfirmation_ConfirmSignUp`, generate `tenant_id` (ULID), write `T#<tid> / PROFILE` to DynamoDB with user email + name, call `adminUpdateUserAttributes` to set `custom:tenant_id` on the Cognito user. Grant Lambda `cognito-idp:AdminUpdateUserAttributes` and DynamoDB write. |
| 3   | Add JWT authorizer to HTTP API          | 3h        | Create `HttpJwtAuthorizer` on API GW v2 pointing to the Cognito User Pool. Attach to the catch-all route. Configure `authorizationScopes`. Extract `custom:tenant_id` from JWT claims and pass to Lambda via `event.requestContext.authorizer`.                                                         |
| 4   | Add health endpoint exemption           | 1h        | Ensure `/health` route is unauthenticated (no authorizer). Needed for monitoring and deployment verification.                                                                                                                                                                                           |
| 5   | Output iOS client ID                    | 1h        | Add `CfnOutput` for `iOSClientId` (currently missing from outputs). The iOS app needs this value.                                                                                                                                                                                                       |

**Dependencies**: None (pure infra)
**Priority**: P0 — everything else depends on this

---

### MVI 1.2: iOS Auth Service + Keychain Token Storage

**Value**: iOS app can authenticate against Cognito and securely store tokens.

**Increment**: Auth service protocol, Cognito implementation using AWS SDK for Swift (not Amplify — too heavy), Keychain wrapper for token persistence, token refresh logic.

**Verification**:

- [ ] `AuthService` protocol defined with `signUp`, `signIn`, `signOut`, `refreshSession`, `currentSession` methods
- [ ] `CognitoAuthService` calls Cognito `InitiateAuth` (SRP) and `SignUp` APIs
- [ ] Tokens (access, refresh, id) stored in Keychain via `KeychainService`
- [ ] `refreshSession` uses refresh token to get new access token
- [ ] `currentSession` returns cached session or `nil` if expired and unrefreshable
- [ ] `tenant_id` extracted from ID token claims
- [ ] Unit tests for token parsing and session state logic

**Tasks**:

| #   | Task                           | Human Est | Description                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --- | ------------------------------ | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Define `AuthService` protocol  | 2h        | Protocol in `Core/Auth/AuthService.swift`. Methods: `signUp(email:password:name:) async throws -> AuthResult`, `signIn(email:password:) async throws -> AuthSession`, `signOut() async`, `refreshSession() async throws -> AuthSession`, `currentSession() async -> AuthSession?`. Define `AuthSession` (accessToken, idToken, refreshToken, tenantId, expiresAt) and `AuthResult` (`.confirmed`, `.confirmationRequired`). |
| 2   | Create `KeychainService`       | 3h        | Wrapper around Security framework. Methods: `save(key:data:)`, `load(key:) -> Data?`, `delete(key:)`. Keys: `cawnex.accessToken`, `cawnex.idToken`, `cawnex.refreshToken`. No third-party dependencies.                                                                                                                                                                                                                     |
| 3   | Implement `CognitoAuthService` | 6h        | Uses `AWSCognitoIdentityProvider` SDK (SPM: `aws-sdk-swift`). Implements SRP auth flow via `InitiateAuth` + `RespondToAuthChallenge`. Handles `SignUp` + `ConfirmSignUp`. Parses JWT to extract `custom:tenant_id` from ID token. Stores tokens via `KeychainService`. Implements refresh using `REFRESH_TOKEN_AUTH` flow.                                                                                                  |
| 4   | Create `InMemoryAuthService`   | 2h        | For SwiftUI previews and tests. Returns fake sessions with configurable tenant_id. Simulates delays.                                                                                                                                                                                                                                                                                                                        |
| 5   | Add JWT parsing utility        | 2h        | `JWTParser.swift` — decode base64url JWT payload, extract claims (sub, email, custom:tenant_id, exp). No signature verification needed (Cognito handles that server-side).                                                                                                                                                                                                                                                  |

**Dependencies**: MVI 1.1 deployed (need User Pool ID and iOS Client ID)
**Priority**: P0

---

### MVI 1.3: Auth State Machine + Sign-In Flow

**Value**: The app navigates based on real auth state. Sign-in and sign-up work end-to-end.

**Increment**: `AppRouter` becomes auth-aware with a proper state machine. `SignInScreen` connects to `CognitoAuthService`. Sign-up screen added. Email confirmation screen added. Error handling for auth failures.

**Verification**:

- [ ] App launch checks Keychain for existing session -> auto-signs in if valid
- [ ] App launch with expired token attempts refresh -> signs in if refresh succeeds
- [ ] App launch with no session -> shows sign-in screen
- [ ] Sign-in with valid credentials -> navigates to main app
- [ ] Sign-in with wrong password -> shows error inline
- [ ] Sign-up -> confirmation code screen -> confirms -> navigates to main app
- [ ] Sign-out -> clears Keychain -> shows sign-in screen
- [ ] `User` model now has `tenantId` field, populated from JWT
- [ ] `AppStore.currentUser` set from auth session, not `seedData()`

**Tasks**:

| #   | Task                                           | Human Est | Description                                                                                                                                                                                                                                             |
| --- | ---------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Expand `AppRouter` state machine               | 3h        | New states: `.checking` (launch, verifying session), `.signedOut`, `.signingIn`, `.signUp`, `.confirmEmail(email)`, `.signedIn`. Add `checkSession(authService:)` method that runs on launch. Remove hardcoded `splashFinished` -> `signIn` transition. |
| 2   | Connect `SignInScreen` to `CognitoAuthService` | 4h        | Create `SignInViewModel` (@Observable). Takes `AuthService`. Handles `signIn(email:password:)`. Manages loading state, error messages. On success, updates `AppRouter` to `.signedIn`. On failure, shows inline error.                                  |
| 3   | Create `SignUpScreen` + `SignUpViewModel`      | 4h        | Email, password, name fields. Calls `authService.signUp()`. On `.confirmationRequired`, navigates to `.confirmEmail`. Validates password requirements client-side before submit.                                                                        |
| 4   | Create `ConfirmEmailScreen`                    | 3h        | 6-digit code input. Calls `confirmSignUp(email:code:)`. On success, auto-signs in and navigates to `.signedIn`. Resend code button.                                                                                                                     |
| 5   | Update `User` model and `AppStore`             | 2h        | Add `tenantId: String` to `User`. Remove `seedData()` user creation. Add `func setUser(from session: AuthSession)` to `AppStore`. Update `ContentView` to use new router states.                                                                        |
| 6   | Wire `ContentView` to auth-aware router        | 2h        | `ContentView` shows: `.checking` -> splash, `.signedOut` -> sign-in, `.signUp` -> sign-up, `.confirmEmail` -> confirm, `.signedIn` -> main tabs. Inject `AuthService` via environment.                                                                  |

**Dependencies**: MVI 1.2 (AuthService implementation)
**Priority**: P0

---

### MVI 1.4: Tenant Context Propagation + API Client Foundation

**Value**: Every API call from the iOS app carries the JWT. Tenant context flows through the entire app.

**Increment**: API client that attaches JWT to all requests. Tenant-aware service layer. Auto-refresh on 401. Foundation for all future API calls.

**Verification**:

- [ ] `APIClient` attaches `Authorization: Bearer <accessToken>` to every request
- [ ] On 401 response, `APIClient` attempts token refresh and retries once
- [ ] On refresh failure, `APIClient` triggers sign-out flow
- [ ] `TenantContext` available as environment object throughout the app
- [ ] Existing `InMemory*Service` implementations still work for previews
- [ ] Integration test: sign in -> call `/health` (authed) -> verify 200

**Tasks**:

| #   | Task                            | Human Est | Description                                                                                                                                                                                                                                                                                                                                                                            |
| --- | ------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Create `APIClient`              | 4h        | `Core/Network/APIClient.swift`. Uses `URLSession`. Methods: `get<T: Decodable>(path:) async throws -> T`, `post<T: Decodable>(path:body:) async throws -> T`, etc. Reads access token from `AuthService.currentSession()`. On 401, calls `refreshSession()` and retries. On refresh failure, posts `Notification.signOutRequired`. Base URL configurable (CloudFront URL from config). |
| 2   | Create `TenantContext`          | 2h        | `Core/Auth/TenantContext.swift`. Observable object holding `tenantId: String`. Set from `AuthSession` on sign-in. Injected as environment. Available to all views and view models.                                                                                                                                                                                                     |
| 3   | Create `AppConfiguration`       | 2h        | `Core/Config/AppConfiguration.swift`. Holds `userPoolId`, `clientId`, `apiBaseUrl`. Values per environment (dev/staging/prod). Read from a plist or compile-time config. No secrets in code.                                                                                                                                                                                           |
| 4   | Update `ServiceFactory` pattern | 2h        | Create `ServiceFactory` protocol. `InMemoryServiceFactory` for previews. `LiveServiceFactory` creates services backed by `APIClient`. All existing ViewModels receive services via factory, not direct construction.                                                                                                                                                                   |
| 5   | Integration smoke test          | 2h        | End-to-end: launch app -> sign in with test credentials -> verify token attached to API call -> verify tenant_id in request. Can be a manual test plan documented in the MVI, with automated test for `APIClient` token attachment.                                                                                                                                                    |

**Dependencies**: MVI 1.3 (auth flow working), MVI 1.1 (JWT authorizer deployed)
**Priority**: P0

---

## Goal 2: MFA (TOTP) Enrollment and Verification

**Objective**: Users can enable TOTP-based MFA. Sign-in challenges for MFA code when enabled. Settings screen for MFA management.

**Timeline**: ~1 week (2 MVIs, each 2-3 days)

---

### MVI 2.1: CDK MFA Configuration + iOS MFA Challenge Handling

**Value**: Users who have MFA enabled are prompted for their TOTP code during sign-in.

**Increment**: Cognito configured with optional MFA (TOTP). iOS auth flow handles `SOFTWARE_TOKEN_MFA` challenge. New MFA verification screen in the auth flow.

**Verification**:

- [ ] Cognito User Pool configured with `mfaConfiguration: OPTIONAL`, `enabledMfas: [SOFTWARE_TOKEN_MFA]`
- [ ] Sign-in for MFA-enabled user returns `SOFTWARE_TOKEN_MFA` challenge
- [ ] iOS app shows MFA code entry screen on challenge
- [ ] Correct code completes sign-in
- [ ] Wrong code shows error, allows retry
- [ ] `AppRouter` handles new `.mfaRequired` state

**Tasks**:

| #   | Task                                         | Human Est | Description                                                                                                                                                                                                                            |
| --- | -------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Add MFA config to CDK User Pool              | 2h        | Set `mfa: cognito.Mfa.OPTIONAL`, add `enableSoftwareTokenMfa: true` to User Pool construct. Deploy and verify in Console.                                                                                                              |
| 2   | Handle MFA challenge in `CognitoAuthService` | 4h        | `InitiateAuth` returns `ChallengeName: SOFTWARE_TOKEN_MFA` with session. New method: `respondToMfaChallenge(session:code:) async throws -> AuthSession`. Update `signIn` to return `AuthResult.mfaRequired(session:)` when challenged. |
| 3   | Create `MFAVerifyScreen` + ViewModel         | 3h        | 6-digit TOTP input. Calls `respondToMfaChallenge`. On success, completes sign-in. On failure, shows error. Timer shows code validity window.                                                                                           |
| 4   | Update `AppRouter` for MFA state             | 2h        | Add `.mfaRequired(session: String)` state. Sign-in flow: `.signingIn` -> `.mfaRequired` -> `.signedIn`. Back button returns to sign-in.                                                                                                |

**Dependencies**: Goal 1 complete
**Priority**: P1

---

### MVI 2.2: MFA Enrollment Flow in Settings

**Value**: Users can enable MFA from Settings by scanning a QR code with their authenticator app.

**Increment**: Settings screen has "Enable MFA" option. Enrollment flow: associate TOTP -> show QR code -> verify code -> MFA enabled. Disable flow with re-authentication.

**Verification**:

- [ ] Settings shows MFA status (enabled/disabled)
- [ ] "Enable MFA" starts enrollment: calls `AssociateSoftwareToken`, generates QR code
- [ ] QR code displays with `otpauth://` URI (app name: Cawnex, account: user email)
- [ ] User enters code from authenticator -> calls `VerifySoftwareToken` -> MFA enabled
- [ ] "Disable MFA" requires password re-entry, then calls `SetUserMFAPreference`
- [ ] Next sign-in after enabling prompts for MFA code

**Tasks**:

| #   | Task                                          | Human Est | Description                                                                                                                                                                                  |
| --- | --------------------------------------------- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Add MFA methods to `AuthService` protocol     | 2h        | `associateMFA() async throws -> MFASetup` (returns secret + QR URI), `verifyMFASetup(code:) async throws`, `disableMFA(password:) async throws`, `getMFAStatus() async throws -> Bool`.      |
| 2   | Implement MFA methods in `CognitoAuthService` | 4h        | `AssociateSoftwareToken` -> parse secret -> generate `otpauth://` URI. `VerifySoftwareToken` -> confirm. `SetUserMFAPreference` -> disable. Use access token for all calls.                  |
| 3   | Create `MFAEnrollmentScreen`                  | 4h        | Step 1: Show QR code (generate from URI using CoreImage `CIQRCodeGenerator`). Step 2: Code verification input. Step 3: Success confirmation. Include "Can't scan? Show secret key" fallback. |
| 4   | Add MFA section to Settings screen            | 2h        | Card showing MFA status. Enable/Disable toggle. Navigates to enrollment flow or disables with confirmation.                                                                                  |

**Dependencies**: MVI 2.1 (MFA challenge handling works)
**Priority**: P1

---

## Goal 3: Apple Sign In via Cognito Federation

**Objective**: Users can sign in with Apple, federated through Cognito. Same tenant-scoped JWT, same multi-tenant isolation.

**Timeline**: ~1 week (2 MVIs, each 2-3 days)

---

### MVI 3.1: CDK Apple Sign In Provider + iOS ASAuthorization

**Value**: Users can tap "Continue with Apple" and get a real Cognito session.

**Increment**: Apple configured as Cognito identity provider. iOS uses `ASAuthorizationController` to get Apple token, exchanges it with Cognito for a session.

**Verification**:

- [ ] Apple Developer Console: App ID has Sign In with Apple capability, Service ID configured with Cognito callback
- [ ] CDK deploys `UserPoolIdentityProviderApple` with correct `clientId`, `teamId`, `keyId`, `privateKey`
- [ ] iOS app client includes `APPLE` in `supportedIdentityProviders`
- [ ] Tapping "Continue with Apple" triggers `ASAuthorizationController`
- [ ] Apple token exchanged with Cognito via hosted UI or token endpoint
- [ ] Post-confirmation trigger creates tenant for Apple users (same as email users)
- [ ] User lands in main app with valid session and `tenant_id`

**Tasks**:

| #   | Task                                            | Human Est | Description                                                                                                                                                                                                                                                                                                                   |
| --- | ----------------------------------------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Configure Apple Developer Console               | 3h        | Enable Sign In with Apple for App ID. Create Service ID pointing to Cognito domain callback. Generate private key for Cognito. Document the identifiers (Team ID, Key ID, Service ID).                                                                                                                                        |
| 2   | Add Apple IdP to CDK stack                      | 3h        | `UserPoolIdentityProviderApple` construct. Private key from Secrets Manager (not hardcoded). Update iOS client to include `APPLE` provider. Update Cognito domain callback URLs.                                                                                                                                              |
| 3   | Implement Apple Sign In in `CognitoAuthService` | 6h        | Use `ASAuthorizationController` to request Apple credential. Extract `identityToken` and `authorizationCode`. Exchange with Cognito token endpoint (`/oauth2/token`) using authorization code grant. Parse response for Cognito tokens. Handle "first time" vs "returning" Apple user (Apple only sends email on first auth). |
| 4   | Update `SignInScreen` Apple button              | 2h        | Replace dummy `onSignIn()` with real `ASAuthorizationController` trigger. Show loading state during token exchange. Handle errors (user cancelled, Apple unavailable).                                                                                                                                                        |
| 5   | Handle Apple user attribute mapping             | 2h        | Cognito attribute mapping: Apple `email` -> Cognito `email`, Apple `name` -> Cognito `name`. Verify post-confirmation trigger works for Apple-federated users. Test tenant creation for Apple sign-in path.                                                                                                                   |

**Dependencies**: Goal 1 complete, Apple Developer account access
**Priority**: P2 (can ship without this, email/password is sufficient for early access)

---

### MVI 3.2: Apple Sign In Edge Cases + Account Linking

**Value**: Apple Sign In works reliably for all edge cases including users who have both email and Apple accounts.

**Increment**: Handle "Hide My Email" relay, account linking (same email via Apple + direct), re-authentication for sensitive operations.

**Verification**:

- [ ] "Hide My Email" users get a working account (relay email stored, display name shown)
- [ ] User who signed up with email, then tries Apple with same email -> accounts linked
- [ ] User who signed up with Apple, then tries email with same email -> prompted to use Apple
- [ ] Sign-in method shown in Settings (Apple vs Email)
- [ ] Re-authentication for sensitive operations uses correct provider

**Tasks**:

| #   | Task                             | Human Est | Description                                                                                                                                                                        |
| --- | -------------------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Handle "Hide My Email" relay     | 3h        | Store Apple's relay email. Use Apple-provided name (or "Cawnex User" fallback if name not shared). Test email delivery to relay addresses for verification codes.                  |
| 2   | Implement account linking        | 4h        | On sign-in conflict (same email, different provider), call Cognito `AdminLinkProviderForUser`. UI: show "This email is already registered with [provider]. Link accounts?" dialog. |
| 3   | Add sign-in method indicator     | 2h        | Settings screen shows how user signed in (Apple icon or Email icon). If Apple, hide password change option. If email, show password change.                                        |
| 4   | Provider-aware re-authentication | 3h        | For sensitive operations (disable MFA, delete account), re-authenticate using the original provider. Apple users re-auth via `ASAuthorization`. Email users re-enter password.     |

**Dependencies**: MVI 3.1
**Priority**: P2

---

## Technical Decisions

### AWS SDK for Swift vs Amplify

**Decision**: Use `aws-sdk-swift` directly, NOT Amplify.

**Rationale**:

- Amplify iOS is a heavy framework (~20+ packages) that installs data, storage, analytics, etc.
- We only need Cognito auth calls (InitiateAuth, SignUp, ConfirmSignUp, token refresh)
- `aws-sdk-swift` gives us `AWSCognitoIdentityProvider` as a single focused package
- Aligns with the project's "minimize external dependencies" principle
- Full control over the auth flow, no magic
- Amplify's `Auth` category would fight with our custom state machine

### Token Storage

**Decision**: iOS Keychain via Security framework, no third-party wrapper.

**Rationale**:

- Tokens are sensitive credentials, Keychain is the OS-level secure store
- No need for KeychainAccess or similar libraries for our simple use case
- Three keys: `cawnex.accessToken`, `cawnex.idToken`, `cawnex.refreshToken`
- Keychain items persist across app installs (unless user resets device)

### Tenant Creation Timing

**Decision**: Post-confirmation Lambda trigger creates tenant on first sign-up.

**Rationale**:

- Guarantees tenant exists before the user's first API call
- Single atomic operation: create DynamoDB record + set Cognito attribute
- No race condition — Cognito blocks the confirmation flow until Lambda completes
- Works for both email and Apple sign-in paths (both trigger PostConfirmation)

### Auth State Machine

**Decision**: Explicit state enum in `AppRouter`, not implicit boolean flags.

**Rationale**:

- Prevents impossible states (e.g., "signed in but no token")
- Makes navigation deterministic — each state maps to exactly one screen
- Easy to extend for MFA, Apple Sign In, onboarding steps
- States: `.checking` -> `.signedOut` | `.signedIn` | `.mfaRequired` | `.signUp` | `.confirmEmail`

---

## Risk Assessment

| Risk                                                                     | Likelihood | Impact | Mitigation                                                                                                              |
| ------------------------------------------------------------------------ | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------- |
| `aws-sdk-swift` SRP implementation gaps                                  | Low        | High   | SRP is well-tested in the SDK. Fallback: use Cognito hosted UI for auth, parse callback.                                |
| Apple Sign In key rotation                                               | Low        | Medium | Store private key in Secrets Manager, rotate via CDK parameter update.                                                  |
| Cognito PostConfirmation Lambda cold start delays sign-up                | Medium     | Low    | Lambda is lightweight (DynamoDB write + admin API call). Provision concurrency if needed.                               |
| Token refresh race condition (multiple API calls hit 401 simultaneously) | Medium     | Medium | `APIClient` uses a serial refresh queue — first 401 triggers refresh, subsequent 401s wait for the same refresh result. |
| Keychain access denied on device                                         | Low        | High   | Graceful fallback: if Keychain unavailable, sign out and show error. Never store tokens in UserDefaults.                |

---

## Dependency Graph

```
MVI 1.1 (CDK Auth Infra)
    |
    v
MVI 1.2 (iOS Auth Service + Keychain)
    |
    v
MVI 1.3 (Auth State Machine + Sign-In Flow)
    |
    v
MVI 1.4 (Tenant Context + API Client) -----> Goal 2 & Goal 3
                                                |           |
                                                v           v
                                          MVI 2.1         MVI 3.1
                                          (MFA Challenge) (Apple Sign In)
                                                |           |
                                                v           v
                                          MVI 2.2         MVI 3.2
                                          (MFA Enroll)    (Edge Cases)
```

---

## What This Does NOT Cover

- **Password reset flow**: Cognito supports it, but not in scope for this milestone. Add when Settings screen gets "Change Password" feature.
- **User profile editing**: Name, avatar, etc. Separate feature.
- **Team/organization management**: Multi-user tenants (inviting team members). Future milestone.
- **Role-based access control (RBAC)**: All users are currently tenant admins. Roles come later.
- **Biometric unlock (Face ID / Touch ID)**: Enhancement after core auth is stable.
- **Rate limiting on auth endpoints**: Cognito has built-in throttling. Custom rate limiting is a production hardening task.

---

## Implementation Order Summary

| Order | MVI                             | Days | What Ships                                                              |
| ----- | ------------------------------- | ---- | ----------------------------------------------------------------------- |
| 1     | 1.1 CDK Auth Infra              | 2-3  | Backend ready: tenant_id attribute, post-confirm Lambda, JWT authorizer |
| 2     | 1.2 iOS Auth Service            | 2-3  | AuthService protocol + Cognito impl + Keychain storage                  |
| 3     | 1.3 Auth State Machine          | 2-3  | Real sign-in/sign-up works, auth-aware routing, no more seedData user   |
| 4     | 1.4 Tenant Context + API Client | 2-3  | JWT on every request, auto-refresh, tenant context in app               |
| 5     | 2.1 MFA Challenge               | 2-3  | MFA-enabled users prompted for TOTP on sign-in                          |
| 6     | 2.2 MFA Enrollment              | 2-3  | Enable/disable MFA from Settings with QR code                           |
| 7     | 3.1 Apple Sign In               | 3-4  | "Continue with Apple" works end-to-end                                  |
| 8     | 3.2 Apple Edge Cases            | 2-3  | Account linking, Hide My Email, provider-aware re-auth                  |

**Total estimated effort**: 17-25 days

**Critical path to first working sign-in**: MVIs 1.1 through 1.3 (~7-9 days)
