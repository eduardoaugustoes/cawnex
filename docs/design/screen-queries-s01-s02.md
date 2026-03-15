# Screen Query Analysis — S01 Splash & S02 Sign In

> DynamoDB single-table mapping for auth screens.

---

## S01 — Splash

**Purpose:** App launch brand moment; auto-transitions to S02.

### Data Needed

None. Pure client-side animation.

### DynamoDB Queries

None.

### Write Operations

None.

### Real-Time Needs

None.

### Snapshot Model Notes

S01 is entirely offline. No tenant context exists yet — the user has not authenticated. No PK/SK access of any kind.

---

## S02 — Sign In

**Purpose:** Authentication entry point (Apple Sign In or email/password via Cognito).

### Data Needed

| Field            | Source      | Notes                     |
| ---------------- | ----------- | ------------------------- |
| Email            | User input  | Passed to Cognito         |
| Password         | User input  | Passed to Cognito         |
| Apple credential | Apple OAuth | Federated through Cognito |

No data is read from DynamoDB to render this screen. Auth is handled entirely by Cognito.

### DynamoDB Queries

**On screen render:** None.

**Post-authentication (server-side, not client-initiated):**

The Cognito post-confirmation Lambda (sign-up, first login) may need to bootstrap tenant records:

| Purpose                    | PK                       | SK     | Operation                 |
| -------------------------- | ------------------------ | ------ | ------------------------- |
| Check/create dynasty       | `T#{tenant_id}#DYNASTY`  | `META` | `GetItem` / `PutItem`     |
| Create project list anchor | `T#{tenant_id}#PROJECTS` | `META` | `PutItem` (if new tenant) |

These are backend-triggered, not client-initiated. The iOS app never queries DynamoDB directly from S02.

### Write Operations

| Operation            | Where                              | Details                                                  |
| -------------------- | ---------------------------------- | -------------------------------------------------------- |
| `POST /auth/sign-in` | Cognito                            | Returns JWT with `custom:tenant_id`                      |
| Tenant bootstrap     | Lambda (post-confirmation trigger) | Creates `DYNASTY` and `PROJECTS` records for new tenants |
| Store tokens         | iOS Keychain                       | Access token, refresh token, id token                    |

### Real-Time Needs

None. Auth is request/response. The app waits for the Cognito response, then navigates to S10.

### Snapshot Model Notes

- S02 operates **outside** the snapshot model. No tenant context exists until authentication succeeds.
- The JWT returned by Cognito carries `custom:tenant_id`, which becomes the `T#{tenant_id}` prefix for all subsequent DynamoDB access.
- Tenant bootstrap (dynasty + project list creation) happens exactly once per tenant, triggered by Cognito post-confirmation hook — not by the client.
- After auth succeeds, the app transitions to S10 (Dashboard), which is the first screen that touches the snapshot table.
