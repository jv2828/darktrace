# Frontend Architecture & Design Documentation

This document describes the React frontend architecture, design system, component hierarchy, routing, authentication state management, and testing setup for DARKTRACE Phase 4.

---

## 1. Directory Structure

```text
frontend/
  ├── src/
  │   ├── __tests__/                     # Vitest + React Testing Library suites
  │   │   ├── api.test.js                # Token attachment & 401 session expiry
  │   │   ├── AppShell.test.jsx          # Role-based sidebar navigation
  │   │   ├── DashboardPage.test.jsx     # Metrics rendering & empty states
  │   │   ├── LoginPage.test.jsx         # Validation, error handling, auth flow
  │   │   └── ProtectedRoute.test.jsx    # Guarding unauthenticated & non-admin routes
  │   ├── components/
  │   │   ├── investigations/
  │   │   │   └── NewInvestigationModal.jsx # Case workspace creation dialog
  │   │   ├── ui/                        # Reusable design system primitives
  │   │   │   ├── Badge.jsx              # Status indicators (draft, active, roles)
  │   │   │   ├── Button.jsx             # Primary, secondary, ghost, danger variants
  │   │   │   ├── Card.jsx               # Surface panel container
  │   │   │   ├── EmptyState.jsx         # Minimalistic empty state callout
  │   │   │   ├── ErrorState.jsx         # Structured error banner with retry
  │   │   │   ├── Input.jsx              # Form input with label & error text
  │   │   │   ├── Modal.jsx              # Accessible dialog with focus trap & Esc
  │   │   │   ├── PageHeader.jsx         # Title, description, action buttons
  │   │   │   ├── Spinner.jsx            # Animated loading indicator
  │   │   │   ├── StatCard.jsx           # High-visibility metric counter card
  │   │   │   ├── Table.jsx              # Responsive tabular data container
  │   │   │   └── Toast.jsx              # Toast notification provider & hook
  │   │   ├── AppShell.jsx               # Left sidebar + topbar responsive layout
  │   │   └── ProtectedRoute.jsx         # Authentication & RBAC route guard
  │   ├── context/
  │   │   └── AuthContext.jsx            # Authentication state, session restore
  │   ├── lib/
  │   │   └── api.js                     # Unified fetch client & envelope parser
  │   ├── pages/
  │   │   ├── DashboardPage.jsx          # Overview metrics, recent cases & runs
  │   │   ├── InvestigationDetailPage.jsx# Individual case inspector & data counts
  │   │   ├── InvestigationsPage.jsx     # Paginated cases, search, status filter
  │   │   ├── LoginPage.jsx              # Credentials form & security notice
  │   │   ├── NotFoundPage.jsx           # Clean 404 error fallback
  │   │   ├── SystemPage.jsx             # Admin infrastructure & schema audit
  │   │   └── UsersPage.jsx              # Admin user provisioning & deactivation
  │   ├── test/
  │   │   └── setup.js                   # Vitest testing setup & DOM cleanup
  │   ├── App.jsx                        # Root router configuration
  │   ├── index.css                      # Tailwind v4 @theme tokens & accessibility
  │   └── main.jsx                       # React DOM entry point
  ├── package.json
  └── vite.config.js
```

---

## 2. Design Tokens & Accessibility Guidelines

Defined via `@theme` in `src/index.css`:

| Category | Token | Value / Palette | Usage |
| :--- | :--- | :--- | :--- |
| **Typography** | `--font-sans` | `Inter`, system-ui | Primary UI copy |
| **Typography** | `--font-mono` | `ui-monospace`, Menlo | IDs, hashes, timestamps |
| **Background** | `--color-background`| `#090d16` (Deep Slate) | Application canvas |
| **Surface** | `--color-surface` | `#0f172a` (Slate-900) | Primary cards & tables |
| **Surface Raised**| `--color-surface-raised`| `#1e293b` (Slate-800) | Dialogs, elevated items |
| **Borders** | `--color-border` | `#1e293b` | Subtle structural dividers |
| **Borders** | `--color-border-strong` | `#334155` | Table boundaries, form inputs |
| **Focus Ring** | `--color-border-focus` | `#38bdf8` (Sky-400) | WCAG visible focus ring |
| **Text** | `--color-text` | `#f8fafc` (Slate-50) | High-contrast body text |
| **Text Muted** | `--color-text-muted` | `#94a3b8` (Slate-400) | WCAG AA compliant descriptions |
| **Accent** | `--color-accent` | `#2563eb` (Blue-600) | Primary actions & buttons |

### Accessibility & Interaction Standards
- **Contrast**: All text and icons meet or exceed WCAG AA 4.5:1 contrast against slate backgrounds.
- **Focus Rings**: `:focus-visible` renders a distinct 2px sky-400 ring with 2px offset.
- **No Decorative Excess**: No neon glow, complex gradients, or parallax animations.
- **Micro-Interactions**: Hover and focus transitions are strictly capped at $\le 150\text{ms}$.
- **Reduced Motion**: Full support for `@media (prefers-reduced-motion: reduce)` disabling all transitions and animations.

---

## 3. Routing & Permissions Matrix

All application routes are defined in [`src/App.jsx`](file:///Users/jaswandivichare/.gemini/antigravity/scratch/darktrace/frontend/src/App.jsx) and guarded by `ProtectedRoute`:

| Path | Access Level | Description |
| :--- | :--- | :--- |
| `/login` | Public | Credentials sign-in page |
| `/dashboard` | Authenticated | Threat intelligence overview & metrics |
| `/investigations` | Authenticated | Investigation case listing, search, and pagination |
| `/investigations/:id`| Authenticated | Detailed case workspace and entity counts |
| `/users` | Administrator | User directory, provisioning, and status toggle |
| `/system` | Administrator | Database schema inspection & system diagnostics |
| `/` | Authenticated | Redirects to `/dashboard` |
| `*` | Public | 404 Not Found fallback view |

---

## 4. Session Storage & Security Trade-off

The authentication system persists the access token and user claims in `sessionStorage` (`darktrace_token`, `darktrace_user`).

### Architectural Trade-off Analysis:
- **Advantages**:
  1. **Automatic Session Cleanup**: When the browser tab or window closes, credentials and tokens are wiped automatically from memory.
  2. **Multi-Tab Isolation**: Multiple browser tabs can evaluate independent analyst sessions if desired.
  3. **No Storage Leakage**: Unaffected by persistent disk storage vulnerabilities that affect `localStorage`.
- **Prototype Considerations**:
  - `sessionStorage` is readable via JavaScript, making it susceptible if an XSS flaw exists.
  - In an enterprise/production deployment, tokens should be transmitted inside `HttpOnly`, `SameSite=Strict`, `Secure` cookies with rotating refresh tokens and server-side state revocation.

---

## 5. Dashboard Metrics & Heuristic Calculations

The dashboard cards query `/api/v1/dashboard/summary`:

1. **Total Investigations**:
   - Investigators: Count of cases where `created_by == current_user.id`.
   - Administrators: Total count of cases across the system.
2. **Collected Posts**:
   - Distinct dark web posts associated with the user's investigations via `investigation_datasets -> datasets -> posts`.
3. **Extracted Indicators**:
   - Distinct atomic indicators (wallets, PGP fingerprints, onion domains) linked to collected posts.
4. **Potential Linkages**:
   - Count of `correlation_results` produced by pipeline runs associated with the user's investigations.
   - **Important Note**: Potential linkages are heuristic evidence scores for investigation, not confirmed real-world identities. They reflect aggregate algorithmic similarity across cryptographic, infrastructure, and stylometric dimensions.

---

## 6. Running Frontend Tests

Vitest and React Testing Library run with:

```bash
cd darktrace/frontend
npm test
```

To run tests in watch mode during development:
```bash
npx vitest
```

