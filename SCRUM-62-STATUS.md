# SCRUM-62: Implement Role-Based Access Control (RBAC)

**Status:** In Review  
**Assignee:** MUHAMMAD BRILIANTAMA  
**Updated:** 8 July 2026

---

## Summary

Implemented granular Role-Based Access Control for Superadmin, Admin, and User roles across the entire dashboard API.

---

## Changes Made

### 1. `dashboard/rbac.py` — RBAC Module Enhancement
- Added `has_permission_dict(user_info, permission)` helper for cookie-based auth pattern
- Enables permission checks on routes using `get_authenticated_api_user()` (dict-based)

### 2. `dashboard/app.py` — Route Authorization Enforcement

#### Email Operations (replaced ad-hoc role checks with RBAC permissions)
| Endpoint | Permission Used |
|---|---|
| `POST /api/emails/{id}/release` | `RELEASE_EMAIL` |
| `POST /api/emails/{id}/confirm-spam` | `REVIEW_QUARANTINE` |
| `POST /api/emails/{id}/report-false-positive` | `REVIEW_QUARANTINE` |
| `DELETE /api/emails/{id}` | `DELETE_EMAIL` (with own-email fallback) |
| `POST /api/emails/{id}/restore` | `REVIEW_QUARANTINE` |

#### Admin & System Routes (replaced string comparisons with RBAC)
| Endpoint | Permission Used |
|---|---|
| `GET /api/audit-log` | `ACCESS_AUDIT_LOG` |
| `GET /api/settings` | `MANAGE_GLOBAL_SETTINGS` |
| `POST /api/settings` | `MANAGE_GLOBAL_SETTINGS` |
| `POST /api/settings/test-imap` | `MANAGE_GLOBAL_SETTINGS` |
| `GET /api/emails/export-csv` | `VIEW_ALL_REPORTS` / `VIEW_ORG_REPORTS` |
| `GET /api/admin/users` | `MANAGE_ALL_USERS` / `MANAGE_ORG_USERS` |
| `POST /api/admin/users` | `MANAGE_ALL_USERS` / `MANAGE_ORG_USERS` |
| `PUT /api/admin/users/{name}` | `MANAGE_ALL_USERS` / `MANAGE_ORG_USERS` |
| `DELETE /api/admin/users/{name}` | `MANAGE_ALL_USERS` / `MANAGE_ORG_USERS` |
| `GET /api/admin/mailboxes` | `MANAGE_ALL_MAILBOXES` |
| `POST /api/admin/mailboxes` | `MANAGE_ALL_MAILBOXES` |
| `DELETE /api/admin/mailboxes/{id}` | `MANAGE_ALL_MAILBOXES` |
| `GET /api/admin/audit-logs` | `ACCESS_AUDIT_LOG` |
| `GET /api/admin/stats` | `VIEW_ALL_REPORTS` / `VIEW_ORG_REPORTS` |
| `GET /api/admin/reports` | `VIEW_ALL_REPORTS` / `VIEW_ORG_REPORTS` |
| `PUT /api/admin/reports/{id}` | `VIEW_ALL_REPORTS` / `VIEW_ORG_REPORTS` |
| `GET /api/admin/user-stats` | `MANAGE_ALL_USERS` / `MANAGE_ORG_USERS` |
| `GET /api/admin/user-emails/{name}` | `MANAGE_ALL_USERS` / `MANAGE_ORG_USERS` |
| `GET /api/admin/track` | `ACCESS_SYSTEM_HEALTH` |
| `POST /api/admin/settings` | `MANAGE_GLOBAL_SETTINGS` |

### 3. Bug Fix: Global Settings Permission
- **`POST /api/settings`** previously allowed **Admin** to change global settings (incorrect)
- Fixed: Now requires `MANAGE_GLOBAL_SETTINGS` permission (**Superadmin only**)

### 4. `dashboard/admin_routes.py` — Already RBAC-compliant
- No changes needed; this module already uses the RBAC dependency injection pattern

---

## Permission Mapping

| Role | Permissions |
|---|---|
| **Superadmin** | All 17 permissions (full system access) |
| **Admin** | 12 permissions (org-level management) |
| **User** | 5 permissions (personal mailbox & reporting) |

See `dashboard/rbac.py:59-104` for the complete `ROLE_PERMISSIONS` mapping.

---

## Files Modified
- `dashboard/rbac.py` — Added `has_permission_dict()` helper
- `dashboard/app.py` — Updated 20+ routes to use RBAC permission checks

## Git Push Instructions

Hanya file yang berubah untuk SCRUM ini yang perlu di-stage:

```bash
# Stage hanya file yang dimodifikasi untuk SCRUM-62
git add dashboard/rbac.py dashboard/app.py SCRUM-62-STATUS.md

# Commit dengan referensi SCRUM
git commit -m "SCRUM-62: Implement RBAC for Superadmin, Admin, and User

- Added has_permission_dict() helper for cookie-based auth
- Replaced ad-hoc role checks with RBAC permissions across 20+ routes
- Fixed POST /api/settings to require superadmin only (was incorrectly allowing admin)
- Created SCRUM-62-STATUS.md for tracking

Status: In Review"

# Push manual
git push
```

> **Catatan:** Jangan gunakan `git add .` atau `-A` karena akan men staging file lain yang tidak terkait SCRUM ini.

## Future SCRUM Tasks
Setelah SCRUM ini selesai (status → **Done**), akan ada SCRUM berikutnya. Untuk setiap SCRUM baru:
1. Buat branch baru: `git checkout -b SCRUM-XXX`
2. Implementasi perubahan
3. Update file status `SCRUM-XXX-STATUS.md`
4. Stage hanya file yang relevan: `git add <file1> <file2> SCRUM-XXX-STATUS.md`
5. Commit dan push

## Verification
- [x] Syntax check passed (`py_compile` OK)
- [ ] Run `pytest tests/` to verify no regressions
- [ ] Manual testing of all role-specific endpoints
