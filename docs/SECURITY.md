# Security Policy

## Overview

CogniMail implements enterprise-grade security practices to protect against threats while processing sensitive email data. This document outlines our security architecture, best practices, and incident response procedures.

## Security Architecture

### 1. Authentication & Authorization

**JWT-Based Authentication:**
- HS256 algorithm for token signing
- HttpOnly cookies for browser sessions
- Token expiration: 480 minutes (configurable)
- API key support with SHA-256 hashing

**Role-Based Access Control (RBAC):**
- `SUPERADMIN`: Full system access
- `ADMIN`: Organization-scoped management
- `USER`: Personal mailbox access only

**Implementation:**
```python
# See: dashboard/auth.py
# See: dashboard/rbac.py
```

### 2. Data Protection

**Encryption:**
- TLS 1.2+ required for SMTP connections (SMTP_REQUIRE_TLS=true)
- HTTPS enforced in production
- Database connections use encrypted channels
- Secrets stored in environment variables, never in code

**Database Security:**
- PostgreSQL with parameterized queries (SQL injection protected)
- Connection pooling with secure credentials
- Database port not exposed publicly (Docker internal network only)
- Regular automated backups recommended

### 3. Network Security

**Port Exposure:**
```yaml
Redis: 127.0.0.1:6379 (local only)
PostgreSQL: internal Docker network only
Dashboard: 127.0.0.1:8080 (behind reverse proxy)
SMTP: 0.0.0.0:25 (required for MX records)
```

**Security Headers:**
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Content-Security-Policy with strict directives
- HSTS enabled in production

### 4. Rate Limiting & DoS Protection

**Implemented Limits:**
- Login endpoints: 20 requests/minute
- Sensitive operations: 10 requests/minute
- Standard API: 20 requests/minute
- Per-IP and per-user rate limiting

**Implementation:**
```python
# See: dashboard/app.py:201-203
@limiter.limit("20/minute")
```

### 5. Input Validation

**Protection Against:**
- SQL Injection: SQLAlchemy ORM with parameterized queries
- XSS: HTML sanitization, CSP headers
- CSRF: SameSite cookies, origin validation
- File Upload: MIME type validation, size limits
- Email Injection: Strict header validation

## Security Best Practices

### For Deployment

1. **Environment Variables:**
   ```bash
   # Generate strong secrets
   python -c "import secrets; print(secrets.token_hex(32))"
   
   # Required in .env:
   DASHBOARD_SECRET_KEY=<64-hex-chars>
   DB_PASSWORD=<strong-password>
   SMTP_REQUIRE_TLS=true
   ENV=production
   ```

2. **File Permissions:**
   ```bash
   chmod 600 .env
   chmod 600 certs/*.pem
   ```

3. **Docker Security:**
   - Services run as non-root users
   - Read-only volumes where possible
   - Health checks on all critical services
   - Network isolation via Docker internal network

4. **TLS/SSL Certificates:**
   ```bash
   # Using Let's Encrypt (recommended)
   certbot certonly --standalone -d cognimail.yourdomain.com
   
   # Update .env:
   SMTP_TLS_CERT=/certs/live/yourdomain/fullchain.pem
   SMTP_TLS_KEY=/certs/live/yourdomain/privkey.pem
   ```

### For Development

1. **Never commit secrets:**
   ```bash
   # Verify .env is in .gitignore
   git check-ignore .env
   
   # Check history for exposed secrets
   git log --all --full-history -- .env
   ```

2. **Use separate environments:**
   - Development: `.env.local`
   - Staging: `.env.staging`
   - Production: `.env` (never committed)

3. **Security testing:**
   ```bash
   # Dependency audit
   pip-audit
   
   # SAST scanning
   bandit -r . -ll
   
   # Run security tests
   pytest tests/ -k security
   ```

## Audit Logging

All security-relevant actions are logged:
- User authentication attempts
- Authorization failures
- Admin actions (user management, mailbox access)
- Email releases from quarantine
- Configuration changes
- API key usage

**Audit Trail:**
```python
# See: database/models.py:AuditLog, AuditTrail
# Access via: dashboard/admin_routes.py:/api/admin/audit
```

## Incident Response

### If Secrets Are Compromised

1. **Immediate Actions:**
   ```bash
   # Generate new secrets
   python -c "import secrets; print(secrets.token_hex(32))"
   
   # Update .env with new values
   # Restart all services
   docker-compose down
   docker-compose up -d
   
   # Invalidate all existing sessions
   redis-cli FLUSHALL
   ```

2. **Rotate Database Password:**
   ```bash
   # Connect to PostgreSQL
   docker exec -it postgres psql -U ltiuser -d lti_antiphishing
   
   # Change password
   ALTER USER ltiuser WITH PASSWORD 'new_strong_password';
   
   # Update .env and restart services
   ```

3. **Review Audit Logs:**
   ```sql
   SELECT * FROM audit_log 
   WHERE created_at > NOW() - INTERVAL '24 hours'
   ORDER BY created_at DESC;
   ```

### If System Is Breached

1. Isolate affected systems
2. Preserve logs for forensic analysis
3. Notify affected users if data was accessed
4. Conduct security review
5. Implement additional controls
6. Document lessons learned

## Vulnerability Reporting

If you discover a security vulnerability:

1. **DO NOT** open a public GitHub issue
2. Email: security@yourcompany.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

**Response Timeline:**
- Initial response: Within 24 hours
- Vulnerability assessment: Within 3 business days
- Fix deployment: Based on severity (Critical: 24h, High: 72h, Medium: 1 week)

## Security Checklist

### Pre-Deployment

- [ ] All secrets rotated from development/testing
- [ ] `SMTP_REQUIRE_TLS=true` in production
- [ ] Strong database password (32+ characters)
- [ ] TLS certificates valid and auto-renewal configured
- [ ] `.env` file permissions set to 600
- [ ] All ports properly firewalled except SMTP (25), HTTP (80), HTTPS (443)
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented
- [ ] Incident response plan documented

### Post-Deployment

- [ ] Penetration testing completed
- [ ] Security audit performed
- [ ] All tests passing (73/74 expected)
- [ ] Audit logging verified
- [ ] Rate limiting tested
- [ ] TLS/SSL grade A+ (test with ssllabs.com)
- [ ] Security headers validated (test with securityheaders.com)
- [ ] Dependency vulnerabilities scanned

### Ongoing Maintenance

- [ ] Weekly: Review audit logs
- [ ] Monthly: Update dependencies (`pip-audit`, `npm audit`)
- [ ] Monthly: Review user access and permissions
- [ ] Quarterly: Security assessment
- [ ] Quarterly: Penetration testing
- [ ] Annually: Full security audit
- [ ] Continuous: Monitor security advisories

## Compliance

This system implements security controls aligned with:
- **OWASP Top 10** protection
- **CIS Benchmarks** for Docker
- **NIST Cybersecurity Framework**
- **GDPR** data protection requirements (where applicable)

## Security Contact

For security concerns or questions:
- Email: security@yourcompany.com
- Security Team: Available 24/7 for critical issues

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)

---

**Last Updated:** 2026-07-29  
**Version:** 1.0  
**Status:** Production Ready
