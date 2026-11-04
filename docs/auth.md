# Authentication & Role-Based Access Control (RBAC)

This document outlines the authentication, authorization, and cryptographic security architecture implemented in Phase 3 of DARKTRACE.

---

## 1. Overview & Security Model

DARKTRACE enforces a secure, token-based authentication mechanism using **JSON Web Tokens (JWT)** and **Argon2id** password hashing. Access is strictly partitioned by Role-Based Access Control (**RBAC**), differentiating between forensic analysts (`investigator`) and system administrators (`admin`).

### Key Design Tenets
1. **Zero Trust Session Verification**: The backend validates the JWT cryptographic signature on every request *and* queries the database to verify the account is active. If an analyst is deactivated, their active tokens are rejected immediately.
2. **Anti-Enumeration Protection**: Login failures return identical generic responses (`401 INVALID_CREDENTIALS`) for both non-existent usernames/emails and incorrect passwords.
3. **Brute-Force & Lockout Defenses**: Accounts lock for 15 minutes after 5 consecutive failed login attempts, responding with `429 ACCOUNT_LOCKED`.
4. **Administrative Safeguards**: Administrators cannot deactivate or demote their own account, and the system prevents demoting or deactivating the last active administrator.
5. **No Password Exposure**: Password hashes are never returned across any API endpoint or logged.

---

## 2. Role-Based Permissions Matrix

| Endpoint | Method | Public | Investigator | Admin | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `/api/v1/health` | `GET` | ✅ | ✅ | ✅ | Healthcheck & DB ping |
| `/api/v1/auth/login` | `POST` | ✅ | ✅ | ✅ | Authenticate with identifier & password |
| `/api/v1/auth/me` | `GET` | ❌ | ✅ | ✅ | Inspect currently authenticated user session |
| `/api/v1/auth/change-password` | `POST` | ❌ | ✅ | ✅ | Change current user's password |
| `/api/v1/system/info` | `GET` | ❌ | ❌ | ✅ | Database schema revision & table row counts |
| `/api/v1/users` | `GET` | ❌ | ❌ | ✅ | Paginated list of users |
| `/api/v1/users` | `POST` | ❌ | ❌ | ✅ | Create new investigator or administrator |
| `/api/v1/users/{id}` | `GET` | ❌ | ❌ | ✅ | Get user details by ID |
| `/api/v1/users/{id}` | `PATCH` | ❌ | ❌ | ✅ | Update role, name, or active status |
| `/api/v1/users/{id}/reset-password` | `POST` | ❌ | ❌ | ✅ | Reset a user's password and clear lockouts |

---

## 3. JWT Token Specification

Tokens are issued upon successful authentication at `POST /api/v1/auth/login`.

- **Algorithm**: `HS256` (HMAC with SHA-256)
- **Token Type**: Bearer
- **Default Expiration**: 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)

### Payload Structure
```json
{
  "sub": "42",
  "role": "admin",
  "iat": 1730700000,
  "exp": 1730703600
}
```

- `sub`: User ID stored as a string.
- `role`: Role string (`admin` or `investigator`).
- `iat`: Unix timestamp (UTC) of issuance.
- `exp`: Unix timestamp (UTC) of expiration.

---

## 4. Cryptographic Standards & Password Policy

### Password Hashing
- **Algorithm**: `Argon2id` (via `argon2-cffi`)
- **Hash Prefix**: `$argon2id$v=19$m=65536,t=3,p=4$...`
- **Rehash Verification**: On successful login, `PasswordHasher.check_needs_rehash` checks whether cryptographic parameters have evolved, automatically updating the stored hash if necessary.

### Password Policy Rules
All user passwords (upon creation, change, or reset) must satisfy:
1. Minimum length of **10 characters**.
2. Must contain at least **one letter** (`[A-Za-z]`).
3. Must contain at least **one digit** (`[0-9]`).
4. Must not match the user's **username** (case-insensitive).
5. Must not match the user's **email address** (case-insensitive).

---

## 5. Brute-Force & Lockout Policy

To protect threat intelligence analyst credentials from dark web actor attacks:
- **Max Failed Logins**: 5 attempts (`MAX_FAILED_LOGINS`).
- **Lockout Duration**: 15 minutes (`LOCKOUT_MINUTES`).
- **Lockout Mechanism**:
  - Failed attempts increment `users.failed_login_attempts`.
  - When reaching 5, `users.locked_until` is set to `now() + 15 minutes`.
  - Subsequent requests return `429 ACCOUNT_LOCKED` detailing the remaining lockout window.
  - While locked, providing the correct password will **not** succeed and will **not** disclose that the password was correct.
  - Successful login resets `failed_login_attempts` to `0` and clears `locked_until`.

---

## 6. Admin Bootstrap Instructions

To provision the initial administrator account without relying on external seed files:

```bash
# Navigate to backend directory
cd darktrace/backend

# Activate the virtual environment
source venv/bin/activate

# Run interactive provisioning script
python -m app.scripts.create_admin
```

The script will prompt for:
- **Email**: Administrator email (e.g. `admin@darktrace.org`)
- **Username**: Unique handle (e.g. `admin`)
- **Full Name**: Investigator or admin title
- **Password**: Secure password prompted twice with hidden typing

Non-interactive flags (`--email`, `--username`, `--full-name`, `--password`) are also supported for automated setups.

---

## 7. Educational Prototype Security Disclaimer

> [!WARNING]
> **College Cybersecurity Lab Project Disclaimer**
> 
> DARKTRACE is developed as an academic threat-intelligence and correlation prototype. In a production government or enterprise deployment:
> 1. **Transport Security (HTTPS)**: Tokens must strictly traverse TLS 1.3 encrypted connections. Transmitting Bearer tokens over plaintext HTTP is susceptible to interception.
> 2. **Token Storage**: In the browser, Bearer tokens stored in `localStorage` or memory can be exposed to XSS. Production deployments should utilize `HttpOnly`, `SameSite=Strict`, `Secure` cookies with CSRF double-submit protection.
> 3. **Refresh Tokens**: Production systems should implement short-lived access tokens (e.g. 15 minutes) paired with rotating refresh tokens stored in secure server-side session stores.
> 4. **Multi-Factor Authentication (MFA)**: Intelligence analyst logins should require FIDO2 / WebAuthn hardware keys or TOTP authenticator codes.
> 5. **Network Rate Limiting**: An API gateway (e.g. Envoy, NGINX, Cloudflare) should enforce IP-level rate limiting and Tor exit node filtering.

