# CogniMail API Documentation

## Overview

CogniMail provides a comprehensive REST API for managing anti-phishing and spam filtering operations. This document details all available endpoints, authentication methods, request/response formats, and integration examples.

**Base URL:** `https://cognimail.zenime.my.id/api`  
**Version:** 1.0  
**Protocol:** HTTPS only

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [Error Handling](#error-handling)
4. [Core Endpoints](#core-endpoints)
5. [Admin Endpoints](#admin-endpoints)
6. [WebSocket API](#websocket-api)
7. [Code Examples](#code-examples)

---

## Authentication

CogniMail supports two authentication methods:

### 1. JWT Bearer Token (Recommended for API clients)

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "admin@example.com",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "username": "admin@example.com",
    "role": "admin",
    "email": "admin@example.com"
  }
}
```

**Usage:**
```http
GET /api/emails
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### 2. API Key (For programmatic access)

```http
GET /api/emails
X-API-Key: your-api-key-here
```

**Generate API Key:**
```http
POST /api/admin/api-keys
Authorization: Bearer <jwt-token>
Content-Type: application/json

{
  "name": "Production API Key",
  "rate_limit": 100
}
```

**Response:**
```json
{
  "key": "ak_live_1234567890abcdef",
  "name": "Production API Key",
  "rate_limit": 100,
  "created_at": "2026-07-29T10:00:00Z"
}
```

⚠️ **Important:** Store API keys securely. They cannot be retrieved after creation.

---

## Rate Limiting

All endpoints are rate-limited to prevent abuse:

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Authentication | 20 requests | 1 minute |
| Sensitive Operations | 10 requests | 1 minute |
| Standard API | 20 requests | 1 minute |

**Rate Limit Headers:**
```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1627584000
```

**Rate Limit Exceeded Response:**
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "Error message here",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2026-07-29T10:00:00Z"
}
```

### HTTP Status Codes

| Status | Meaning | Description |
|--------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required or failed |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

---

## Core Endpoints

### Health Check

Check system health and service status.

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "classifier": "ready",
    "spamassassin": "ready"
  },
  "timestamp": "2026-07-29T10:00:00Z"
}
```

### List Emails

Retrieve quarantined emails with filtering and pagination.

```http
GET /api/emails?folder=inbox&page=1&per_page=20&category=phishing
Authorization: Bearer <token>
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| folder | string | inbox | Folder: inbox, sent, quarantine, trash |
| page | integer | 1 | Page number |
| per_page | integer | 20 | Items per page (max 100) |
| category | string | all | Filter: spam, phishing, clean |
| search | string | - | Search in subject/sender |
| starred | boolean | - | Show only starred |

**Response:**
```json
{
  "emails": [
    {
      "id": 1234,
      "subject": "Urgent: Verify Your Account",
      "sender": "noreply@suspicious-domain.com",
      "recipient": "user@zenime.my.id",
      "received_at": "2026-07-29T09:30:00Z",
      "category": "phishing",
      "confidence": 0.95,
      "status": "quarantine",
      "starred": false,
      "has_attachments": true,
      "detection_methods": ["ML", "Content Analysis", "URL Reputation"]
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

### Get Email Details

Retrieve detailed information about a specific email.

```http
GET /api/emails/{email_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1234,
  "subject": "Urgent: Verify Your Account",
  "sender": "noreply@suspicious-domain.com",
  "recipient": "user@zenime.my.id",
  "received_at": "2026-07-29T09:30:00Z",
  "category": "phishing",
  "confidence": 0.95,
  "status": "quarantine",
  "body_text": "Email body content...",
  "body_html": "<html>...</html>",
  "headers": {
    "From": "noreply@suspicious-domain.com",
    "To": "user@zenime.my.id",
    "Subject": "Urgent: Verify Your Account",
    "Date": "Mon, 29 Jul 2026 09:30:00 +0000"
  },
  "attachments": [
    {
      "filename": "invoice.pdf",
      "size": 102400,
      "content_type": "application/pdf",
      "is_safe": false
    }
  ],
  "analysis": {
    "ml_score": 0.95,
    "spamassassin_score": 12.5,
    "anomaly_score": 0.88,
    "fusion_score": 0.93,
    "threat_indicators": [
      "Suspicious sender domain",
      "Urgent language detected",
      "Phishing URL found",
      "Spoofed sender"
    ]
  },
  "authentication": {
    "spf": "fail",
    "dkim": "none",
    "dmarc": "fail"
  }
}
```

### Release Email from Quarantine

Release a quarantined email to the inbox.

```http
POST /api/emails/{email_id}/release
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "False positive - legitimate email"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email released to inbox",
  "email_id": 1234
}
```

### Delete Email

Permanently delete an email.

```http
DELETE /api/emails/{email_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Email deleted permanently"
}
```

### Report Feedback

Submit feedback for false positives/negatives to improve detection.

```http
POST /api/feedback
Authorization: Bearer <token>
Content-Type: application/json

{
  "email_id": 1234,
  "feedback_type": "false_positive",
  "comment": "This was a legitimate email from our bank"
}
```

**Feedback Types:**
- `false_positive`: Clean email marked as threat
- `false_negative`: Threat email marked as clean
- `correct`: Confirmation that detection was correct

**Response:**
```json
{
  "success": true,
  "message": "Feedback submitted successfully",
  "training_sample_id": 5678
}
```

---

## Admin Endpoints

Admin endpoints require `ADMIN` or `SUPERADMIN` role.

### User Management

#### List Users

```http
GET /api/admin/users
Authorization: Bearer <admin-token>
```

**Response:**
```json
{
  "users": [
    {
      "id": 1,
      "username": "john.doe",
      "email": "john@example.com",
      "role": "user",
      "is_active": true,
      "created_at": "2026-01-15T10:00:00Z",
      "organization_id": 1
    }
  ],
  "total": 25
}
```

#### Create User

```http
POST /api/admin/users
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "username": "jane.doe",
  "email": "jane@example.com",
  "password": "SecurePassword123!",
  "role": "user",
  "organization_id": 1
}
```

**Response:**
```json
{
  "id": 2,
  "username": "jane.doe",
  "email": "jane@example.com",
  "role": "user",
  "created_at": "2026-07-29T10:00:00Z"
}
```

### Statistics & Analytics

#### Get Dashboard Statistics

```http
GET /api/admin/stats?period=7d
Authorization: Bearer <admin-token>
```

**Query Parameters:**
- `period`: `1d`, `7d`, `30d`, `90d`

**Response:**
```json
{
  "period": "7d",
  "emails_processed": 15420,
  "threats_detected": 3245,
  "spam_detected": 2100,
  "phishing_detected": 1045,
  "malware_detected": 100,
  "false_positive_rate": 0.02,
  "detection_accuracy": 0.98,
  "average_processing_time_ms": 125,
  "top_threat_domains": [
    {
      "domain": "suspicious-site.com",
      "count": 245
    }
  ],
  "threat_trend": [
    {
      "date": "2026-07-22",
      "count": 450
    },
    {
      "date": "2026-07-23",
      "count": 480
    }
  ]
}
```

#### Export Threat Report

Generate and download threat reports in various formats.

```http
POST /api/admin/reports/export
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "format": "pdf",
  "date_from": "2026-07-01",
  "date_to": "2026-07-29",
  "categories": ["phishing", "spam"],
  "include_details": true
}
```

**Supported Formats:** `pdf`, `xlsx`, `csv`

**Response:**
```http
Content-Type: application/pdf
Content-Disposition: attachment; filename="threat_report_20260729.pdf"

<binary PDF data>
```

### Audit Logs

```http
GET /api/admin/audit?user=admin&action=release&page=1
Authorization: Bearer <admin-token>
```

**Response:**
```json
{
  "logs": [
    {
      "id": 1001,
      "user": "admin@example.com",
      "action": "release_email",
      "email_id": 1234,
      "ip_address": "192.168.1.100",
      "details": "Email released from quarantine",
      "timestamp": "2026-07-29T10:00:00Z"
    }
  ],
  "total": 5420,
  "page": 1
}
```

---

## WebSocket API

Real-time updates for email processing and threat detection.

### Connect

```javascript
const ws = new WebSocket('wss://cognimail.zenime.my.id/ws');

ws.onopen = () => {
  // Authenticate
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'your-jwt-token'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};
```

### Message Types

#### Email Processed

```json
{
  "type": "email_processed",
  "data": {
    "email_id": 1234,
    "subject": "New Email",
    "category": "phishing",
    "confidence": 0.95,
    "timestamp": "2026-07-29T10:00:00Z"
  }
}
```

#### System Alert

```json
{
  "type": "system_alert",
  "data": {
    "severity": "high",
    "message": "Spike in phishing attempts detected",
    "count": 50,
    "timestamp": "2026-07-29T10:00:00Z"
  }
}
```

---

## Code Examples

### Python

```python
import requests

# Authentication
response = requests.post(
    'https://cognimail.zenime.my.id/api/auth/login',
    json={
        'username': 'admin@example.com',
        'password': 'your-password'
    }
)
token = response.json()['access_token']

# Get quarantined emails
headers = {'Authorization': f'Bearer {token}'}
response = requests.get(
    'https://cognimail.zenime.my.id/api/emails',
    headers=headers,
    params={'folder': 'quarantine', 'category': 'phishing'}
)
emails = response.json()['emails']

# Release email
email_id = emails[0]['id']
response = requests.post(
    f'https://cognimail.zenime.my.id/api/emails/{email_id}/release',
    headers=headers,
    json={'reason': 'False positive'}
)
print(response.json())
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_BASE = 'https://cognimail.zenime.my.id/api';

// Authentication
async function authenticate() {
  const response = await axios.post(`${API_BASE}/auth/login`, {
    username: 'admin@example.com',
    password: 'your-password'
  });
  return response.data.access_token;
}

// Get emails
async function getEmails(token) {
  const response = await axios.get(`${API_BASE}/emails`, {
    headers: { Authorization: `Bearer ${token}` },
    params: { folder: 'quarantine', category: 'phishing' }
  });
  return response.data.emails;
}

// Usage
(async () => {
  const token = await authenticate();
  const emails = await getEmails(token);
  console.log(`Found ${emails.length} phishing emails`);
})();
```

### cURL

```bash
# Authentication
TOKEN=$(curl -X POST https://cognimail.zenime.my.id/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin@example.com","password":"your-password"}' \
  | jq -r '.access_token')

# Get emails
curl -X GET "https://cognimail.zenime.my.id/api/emails?folder=quarantine" \
  -H "Authorization: Bearer $TOKEN"

# Release email
curl -X POST "https://cognimail.zenime.my.id/api/emails/1234/release" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"False positive"}'
```

---

## Best Practices

1. **Security:**
   - Always use HTTPS
   - Store tokens securely (never in client-side code)
   - Rotate API keys regularly
   - Use short-lived JWT tokens

2. **Performance:**
   - Implement pagination for large datasets
   - Cache responses when appropriate
   - Use WebSockets for real-time updates instead of polling

3. **Error Handling:**
   - Always check HTTP status codes
   - Implement retry logic with exponential backoff
   - Log errors for debugging

4. **Rate Limiting:**
   - Implement client-side rate limiting
   - Handle 429 responses gracefully
   - Use bulk endpoints when available

---

## Support

**Documentation:** https://docs.cognimail.zenime.my.id  
**API Status:** https://status.cognimail.zenime.my.id  
**Support Email:** support@yourcompany.com  
**GitHub:** https://github.com/wi5nuu/ML-Powered-Anti-Phishing-and-Spam-Filtering

---

**Last Updated:** 2026-07-29  
**API Version:** 1.0  
**Status:** Production
