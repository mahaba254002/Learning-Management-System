I'll give you both as plain text you can copy directly — no file creation.

---

# BACKEND DOCUMENTATION

## Stack

- **Framework:** FastAPI (Python 3.12)
- **Database:** PostgreSQL, database name `learningSystem`
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **Auth:** Custom JWT (access + refresh) stored in httpOnly cookies, argon2 password hashing via passlib
- **CSRF Protection:** Double-submit cookie pattern
- **Cache / Rate limiting:** Redis (via Memurai on Windows)
- **Email:** Resend (transactional email provider)

## Core Architectural Principles

### Multi-tenancy
- Shared tables + `institution_id` column on every tenant-owned table
- Enforced via `get_current_context` dependency (`app/core/deps.py`) — never trusts `institution_id` from client input, always derives it from the verified JWT
- Re-checks user AND institution `status` on every single request (not just at login) — a suspension takes effect immediately

### Identity / Usernames
- Fully system-generated: `{first_name}.{last_name}.{institution_code}` (e.g. `bakari.alex.khs`)
- Auto-disambiguated on collision within an institution (`bakari2.alex.khs`)
- Globally unique by construction
- Never user-chosen

### Account Creation — three paths, zero self-registration
1. **Institution Admin** — created directly by Platform Super Admin
2. **Teacher** — invitation link (public, token-based) → self-submits profile → Institution Admin reviews → approves/rejects
3. **Student** — not yet built (planned: direct creation by Institution Admin)

Every account gets: auto-generated username, system-generated temp password, `must_change_password=true` flag forcing a password change on first login.

### Email Policy
- Required and globally unique for every user, no exceptions

### Password Policy (user-chosen passwords only)
- Minimum 8 characters, must contain uppercase, lowercase, digit, and symbol
- Enforced in `app/core/password_policy.py`

### Soft Delete
- Institutions are never hard-deleted — "delete" = `status = ARCHIVED`
- Tenant guard already checks `status != ACTIVE`, so archiving instantly locks out all of that institution's users with zero extra code
- Audit fields: `archived_at`, `archived_by`

### Step-up Email Verification
- Used for: institution create, institution archive, password reset
- Flow: `request-*` generates a 6-digit code (hashed, 10-min expiry, max 5 attempts) and emails it → `confirm-*` verifies and performs the action
- If email sending fails during `request-*`, the whole request fails and rolls back (code is useless if never delivered) — **except** `forgot-password`, which always returns the same generic response regardless of email success, to preserve enumeration safety
- Teacher invitations and credential-delivery emails use a **different** pattern: the underlying record (invitation, or new user account) is NOT rolled back if email fails, since it's already a valid, useful record — failures are just logged

### Email Failures
- Recorded in the `email_failures` table (recipient, subject, email_type, error_message, context, resolved)
- Intended to feed a future Super Admin "Audit Logs" page

### Rate Limiting
- Redis-backed, fixed-window algorithm (`app/core/rate_limit.py`)
- Environment-aware: multiplies limits ×20 automatically when `ENVIRONMENT=development` so manual testing isn't blocked; production limits apply automatically otherwise
- Applied to: login, change-password, forgot-password, reset-password, institution verification endpoints, invitation send/submit

### CSRF Protection (double-submit cookie pattern)
- Three cookies set at login: `access_token` (httpOnly), `refresh_token` (httpOnly), `csrf_token` (NOT httpOnly — must be readable by frontend JS)
- Every mutating request (non-GET/HEAD) must include header `X-CSRF-Token` matching the `csrf_token` cookie value
- Verified inside `get_current_context` — applies automatically to every route using `require_platform_admin`/`require_tenant_user`/`require_role`
- **Known limitation:** Swagger UI (`/docs`) cannot attach this header automatically — testing mutating endpoints requires curl with the header set manually

### Security Headers
- `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` on every response
- `Strict-Transport-Security` added automatically outside development

### Global Exception Handling
- Unhandled exceptions return generic `{"detail": "...", "error_id": "..."}` to client, full traceback logged server-side only

## Database Tables (exist, migrated)

| Table | Purpose |
|---|---|
| `institutions` | Tenant root. `code` globally unique. `status`: ACTIVE / SUSPENDED / ARCHIVED |
| `users` | All accounts, all roles. `username` + `email` globally unique |
| `verification_codes` | Step-up verification (hashed code, JSON payload, expiry, attempts) |
| `invitations` | Teacher onboarding. Token-based public access, JSON `submitted_data` |
| `teachers` | Teacher profile fields, linked to `users` |
| `email_failures` | Failed email delivery log |

**Not yet built:** `students`, `academic_units`, `courses`, `academic_years`, `terms`, `enrollments`, `teacher_assignments`, `assignments`, `submissions`, `learning_materials`, `attendance_sessions`, `attendance_records`, `assessments`, `results`, `grading_scales`.

## Known Alembic Gotcha

Postgres `ENUM` value additions (e.g., adding `ARCHIVED` to an existing enum) are **not** detected by `alembic revision --autogenerate`. Must be hand-added to the migration:
```python
op.execute("ALTER TYPE some_enum_name ADD VALUE IF NOT EXISTS 'NEW_VALUE'")
```
This has come up twice already and will recur.

## API Endpoints (built and tested)

### Auth — `/api/auth/*`
- `POST /login` — sets cookies, returns `{must_change_password, user}`
- `POST /logout` — requires auth, clears cookies
- `POST /change-password` — requires current_password + new_password + confirm_password, policy-enforced
- `POST /forgot-password` — enumeration-safe, always generic response
- `POST /reset-password` — verification_id + code + new_password + confirm_password

### Platform Admin — `/api/platform/*` (require_platform_admin only)
- `POST /institutions/request-create` → `POST /institutions/confirm-create` (step-up verified)
- `POST /institutions/{id}/request-archive` → `POST /institutions/confirm-archive` (step-up verified)
- `GET /institutions` (supports `?include_archived=true`)
- `POST /institutions/{id}/admins` — creates Institution Admin
- `GET /stats` — platform-wide counts

### Invitations
- `POST /api/institution/invitations/teachers` — Institution Admin only, sends invite + email
- `GET /api/institution/invitations` — Institution Admin only, own institution's invites
- `POST /api/institution/invitations/{id}/approve` — creates Teacher account, emails credentials
- `POST /api/institution/invitations/{id}/reject`
- `GET /api/invitations/{token}` — **public**
- `POST /api/invitations/{token}/submit` — **public**, rate limited

### Misc
- `GET /health`
- `GET /api/me` — returns current user (UserSummary shape)

## Key Reusable Backend Files

```
app/core/
  config.py              — typed settings from .env
  security.py            — password hashing, JWT create/decode
  deps.py                — AuthContext, get_current_context, require_platform_admin,
                            require_tenant_user, require_role (THE tenant-isolation mechanism)
  csrf.py                — CSRF token generation/verification
  verification.py        — step-up email code generate/confirm (now sends real email)
  invitation_token.py     — secure random token for invite links
  password_policy.py     — validate_password_policy()
  rate_limit.py           — Redis-backed, environment-aware rate limiter
  redis_client.py         — shared Redis connection
  security_headers.py     — SecurityHeadersMiddleware
  exception_handlers.py   — global unhandled-exception handler

app/services/
  username_service.py     — generate_username() with collision handling
  password_service.py     — generate_temporary_password()
  email_service.py         — send_email() — the ONE place that knows about Resend
  email_failure_service.py — record_email_failure()

app/models/               — institution, user, verification_code, invitation, teacher, email_failure
app/schemas/               — auth, institution, invitation (Pydantic request/response shapes)
app/api/routes/            — auth.py, platform.py, invitations.py
```

## Environment Variables (.env)

```
DATABASE_URL
JWT_SECRET_KEY
JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS
REDIS_URL
ENVIRONMENT (development/production)
ALLOWED_ORIGINS
RESEND_API_KEY
EMAIL_FROM_ADDRESS
FRONTEND_BASE_URL
```

**Note:** `.env` files use plain `KEY=value` syntax — no Python type annotations, no quotes needed around values.

## Local Setup Notes

- Windows/PowerShell: `curl` is aliased to `Invoke-WebRequest` — use `curl.exe` for real curl behavior
- When passing JSON bodies via curl, write to a file first (`'...' | Out-File -Encoding ascii file.json`, then `-d "@file.json"`) — inline quote-escaping is unreliable in PowerShell, and `Out-File -Encoding utf8` can add a BOM that breaks JSON parsing
- Redis via Memurai (Windows-compatible Redis alternative)
- First Platform Super Admin created via one-off script `backend/seed_super_admin.py` — the one deliberate exception to "no self-registration"
- Resend sandbox mode restricts sending to only the account owner's own verified email until a domain is verified at resend.com/domains

---

# FRONTEND DOCUMENTATION

## Stack

- **Framework:** React (Vite)
- **Routing:** React Router v7
- **Server state:** TanStack Query (`useQuery`/`useMutation`)
- **Forms:** React Hook Form + Zod (`@hookform/resolvers/zod`)
- **Styling:** Vanilla CSS with a design-token system (CSS custom properties) — no Tailwind
- **Auth state:** React Context (`AuthContext`)

## Design System

Defined in `src/styles/tokens.css`:
- Colors: ink (`#1a2332`), paper (`#faf9f6`), canvas (`#f0eee7`), accent (muted green `#2d5f4c`), accent-warm (brass `#b8863e`)
- Fonts: Source Serif 4 (display/headlines), Inter (body/UI) — loaded via Google Fonts link in `index.html`
- Spacing scale: `--space-1` through `--space-24`
- **No gradients anywhere** — flat solid colors only, per explicit product requirement

## Folder Structure

```
src/
├── api/
│   └── client.js              — central apiRequest() function, handles cookies + CSRF header
├── context/
│   ├── AuthContext.jsx        — AuthProvider (user state, login/logout)
│   └── useAuth.js             — useAuth() hook (separate file for Fast Refresh compatibility)
├── routes/
│   ├── ProtectedRoute.jsx     — auth + role-based route guard
│   └── roleRoutes.js          — ROLE_HOME_PATH map, getRoleHomePath()
├── components/
│   ├── common/
│   │   ├── Modal.jsx / .css       — reusable modal (Escape key, overlay click, focus trap basics)
│   │   ├── PasswordInput.jsx/.css — password field with show/hide toggle
│   │   └── ComingSoon.jsx          — honest placeholder for unbuilt sections
│   └── layout/
│       └── DashboardLayout.jsx/.css — shared sidebar+topbar shell, used by every role's dashboard
├── pages/
│   ├── LandingPage.jsx/.css
│   ├── RoleHoldingPage.jsx      — shown to roles without a real dashboard yet
│   ├── auth/
│   │   ├── LoginPage.jsx/.css (+ loginSchema.js)
│   │   ├── ForgotPasswordPage.jsx (+ forgotPasswordSchema.js)
│   │   ├── ResetPasswordPage.jsx (+ resetPasswordSchema.js)
│   │   └── ChangePasswordPage.jsx (+ changePasswordSchema.js)
│   ├── invite/
│   │   └── InvitePage.jsx/.css (+ inviteSubmissionSchema.js) — PUBLIC page, no auth
│   ├── platform/                — Platform Admin pages
│   │   ├── PlatformLayout.jsx, platformNavItems.js
│   │   ├── PlatformDashboardPage.jsx/.css
│   │   ├── PlatformInstitutionsPage.jsx
│   │   ├── CreateAdminModal.jsx (+ createAdminSchema.js)
│   │   └── CreateInstitutionModal.jsx (+ createInstitutionSchema.js)
│   └── institution/              — Institution Admin pages
│       ├── InstitutionLayout.jsx, institutionNavItems.js
│       ├── InstitutionDashboardPage.jsx
│       └── InstitutionInvitationsPage.jsx
├── App.jsx                       — all route definitions
└── main.jsx                      — AuthProvider + QueryClientProvider setup
```

## Key Architectural Patterns

### API Client (`src/api/client.js`)
- Single `apiRequest(path, {method, body})` function used for every network call
- Automatically sends `credentials: 'include'` (cookies)
- Automatically attaches `X-CSRF-Token` header (read from `csrf_token` cookie) on any non-GET/HEAD request
- Throws `ApiError` (with `.status` and `.message`) on non-2xx responses — components catch this one consistent shape

### Auth Context (`src/context/AuthContext.jsx`)
- On mount, calls `GET /api/me` to check session validity (httpOnly cookies are invisible to JS, so this is the only way to know if logged in)
- Exposes `{user, isLoading, isAuthenticated, login, logout}`
- `useAuth()` hook lives in a **separate file** (`useAuth.js`) from the provider component — required for Vite Fast Refresh to work correctly (a file must export only components to hot-reload properly)

### Role-Based Routing
- `ProtectedRoute` takes an optional `allowedRoles` prop — blocks access at the routing layer, not just via redirect-after-login
- **Critical:** this guards against direct URL access too (e.g., an Institution Admin typing `/platform/dashboard` manually gets redirected away before any data-fetching even starts)
- `roleRoutes.js`'s `getRoleHomePath(role)` is the single source of truth for "where does this role belong" — used by both login redirect and change-password redirect, so they can never disagree

### Dashboard Shell Pattern
- One `DashboardLayout` component (sidebar + topbar + content area), reused by every role
- Each role has its own `{role}NavItems.js` config array and a thin `{Role}Layout.jsx` wrapper that renders `<DashboardLayout navItems={...}><Outlet /></DashboardLayout>`
- Routing uses React Router nested routes — parent route renders the layout, child routes render inside via `<Outlet />`
- Mobile: sidebar fully hides below 720px, replaced by a hamburger-triggered full-width dropdown drawer (not a narrowed icon rail — that caused horizontal overflow)
- Logout is anchored at the bottom of the sidebar (not the topbar), separated from nav by a border

### Tables
- Every `<table>` must be wrapped in `<div className="table-wrapper">` (has `overflow-x: auto`) with `min-width: 500px` on the table itself — prevents mobile horizontal-scroll/clipping bugs

### Modals
- Two-step flows (like institution creation, which needs a verification code) use **one modal component with internal step state**, not two separate modals — preserves context for the user

## Known Gotchas / Lessons Learned

1. **`localhost` vs `127.0.0.1` mismatch breaks CSRF entirely.** Browsers treat them as different origins. If `VITE_API_BASE_URL` and `ALLOWED_ORIGINS` don't match the hostname actually typed into the browser address bar, the non-httpOnly `csrf_token` cookie becomes unreadable by JS (`document.cookie` returns empty for it) even though httpOnly cookies still work fine — causing confusing "logout works via curl but not in the browser" symptoms. **Always use the same hostname everywhere.**
2. **Swagger UI (`/docs`) cannot test CSRF-protected mutations** — it doesn't manage the `X-CSRF-Token` header. Use curl with cookies saved to a file (`-c cookies.txt` / `-b cookies.txt`) instead.
3. **Flex children need `min-width: 0`** to shrink properly — without it, sidebar layouts can force horizontal page overflow on mobile even with correct-looking CSS elsewhere.
4. **Global email uniqueness** means test data cleanup can hit cascading foreign key errors (e.g., deleting a test user requires first deleting their `verification_codes`, `invitations.created_user_id` references, etc.) — Postgres will name the exact blocking table each time.

## Pages Still Needed (not yet built)

- Real Institution Admin dashboard content (currently a stub)
- Teachers list page (Institution Admin)
- Students list page + Student direct-creation flow
- Student and Teacher dashboards (currently show `RoleHoldingPage`)
- Platform Users, Revenue, Audit Logs, Settings (currently `ComingSoon` placeholders)
- Institution archive UI (backend exists, no frontend button yet)