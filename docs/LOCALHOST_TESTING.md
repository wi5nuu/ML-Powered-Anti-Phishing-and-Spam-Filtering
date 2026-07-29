# CogniMail Localhost Testing & Security Hardening Guide

## Overview

This guide provides a comprehensive localhost testing environment to validate security before production deployment. We implement **defense-in-depth** with multiple security layers.

## Prerequisites

```bash
# Python environment
python --version  # 3.11+

# Install additional security dependencies
pip install transformers torch yara-python pyclamd python-magic virustotal-api

# Start required services for localhost
docker-compose up -d redis postgres spamassassin
```

## Testing Environment Setup

### 1. Localhost Configuration

Create `.env.local`:

```bash
# Localhost testing environment
ENV=development
DEBUG=true

# Local services
REDIS_URL=redis://localhost:6379/0
DB_SYNC_URL=postgresql+psycopg://cogniuser:password@localhost:5432/cognimail_test
CLASSIFIER_URL=http://localhost:8001

# Security testing
SECURITY_TEST_MODE=true
ENABLE_ADVANCED_DETECTION=true
ENABLE_THREAT_INTELLIGENCE=true
ENABLE_MALWARE_SCAN=true

# API Keys for testing (use test keys only)
VIRUSTOTAL_API_KEY=your_test_key
URLHAUS_API_KEY=your_test_key
PHISHTANK_API_KEY=your_test_key
```

### 2. Start Services Locally

```bash
# Start minimal services
docker-compose up -d redis postgres spamassassin

# Run classifier locally for testing
cd classifier
python -m predict

# Run dashboard locally
cd dashboard
uvicorn app:app --reload --port 8000

# Run worker locally
cd worker
python pipeline_worker.py
```

## Security Test Suite

### Test Categories

1. **Basic Phishing Detection**
   - Standard phishing emails
   - Spearphishing attempts
   - Brand impersonation

2. **Advanced Evasion Techniques**
   - Homograph attacks (lοokalike.com vs lookalike.com)
   - Zero-width characters
   - HTML obfuscation
   - Base64 encoding
   - URL shorteners + redirects
   - Image-based phishing (OCR evasion)

3. **Malware & Attachments**
   - Macro-enabled documents
   - Executable files (renamed extensions)
   - Archive bombs
   - Polyglot files

4. **Zero-Day & Unknown Threats**
   - Never-before-seen patterns
   - AI-generated phishing
   - Polymorphic attacks

### Running Tests

```bash
# Run comprehensive test suite
python tests/security/test_advanced_evasion.py

# Run specific test category
python tests/security/test_homograph_attacks.py
python tests/security/test_malware_detection.py
python tests/security/test_zero_day.py

# Run penetration testing
python tests/security/penetration_test.py

# Generate test report
python tests/security/generate_report.py
```

## Security Layers Testing

### Layer 1: ML Ensemble Testing

```bash
# Test individual models
python tests/ml/test_xgboost.py
python tests/ml/test_random_forest.py
python tests/ml/test_bert_classifier.py

# Test ensemble voting
python tests/ml/test_ensemble.py

# Adversarial robustness test
python tests/ml/test_adversarial.py
```

### Layer 2: Threat Intelligence Testing

```bash
# Test URL reputation
python tests/threat_intel/test_url_reputation.py

# Test IP reputation
python tests/threat_intel/test_ip_reputation.py

# Test domain analysis
python tests/threat_intel/test_domain_analysis.py
```

### Layer 3: Content Analysis Testing

```bash
# Test attachment scanning
python tests/content/test_malware_scan.py

# Test sandbox execution
python tests/content/test_sandbox.py

# Test OCR detection
python tests/content/test_ocr_phishing.py
```

### Layer 4: Evasion Detection Testing

```bash
# Test homograph detection
python tests/evasion/test_homograph.py

# Test obfuscation detection
python tests/evasion/test_obfuscation.py

# Test encoding tricks
python tests/evasion/test_encoding_evasion.py
```

## Performance Benchmarks

```bash
# Throughput test
python tests/performance/test_throughput.py

# Latency test
python tests/performance/test_latency.py

# Load test
python tests/performance/test_load.py

# Resource usage
python tests/performance/test_resource_usage.py
```

## Expected Test Results

### Minimum Requirements for Production

- **Detection Rate:** ≥ 99.5%
- **False Positive Rate:** ≤ 0.1%
- **Evasion Resistance:** ≥ 98%
- **Malware Detection:** ≥ 99%
- **Throughput:** ≥ 1000 emails/minute
- **Latency:** ≤ 500ms per email

### Test Metrics Dashboard

```bash
# Start test dashboard
python tests/dashboard/app.py

# View at http://localhost:9000
```

## Debugging Failed Tests

### Common Issues

1. **High False Positives**
   - Check feature importance
   - Review model thresholds
   - Analyze false positive patterns

2. **Missed Threats**
   - Review detection layers
   - Check threat intelligence freshness
   - Analyze evasion techniques used

3. **Performance Issues**
   - Profile code bottlenecks
   - Optimize feature extraction
   - Check database query performance

## Security Audit Checklist

- [ ] All tests pass with > 99% accuracy
- [ ] Zero critical vulnerabilities
- [ ] Evasion techniques detected
- [ ] Malware scanning working
- [ ] Threat intelligence updated
- [ ] No exposed secrets in code
- [ ] Input validation everywhere
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] CSRF tokens implemented
- [ ] Rate limiting works
- [ ] Authentication secure
- [ ] Authorization correct
- [ ] Logging comprehensive
- [ ] Error handling safe

## Git Commit Strategy

### After All Tests Pass

```bash
# 1. Check status
git status

# 2. Stage security improvements
git add worker/ml_retraining_worker.py
git add tests/security/
git add docs/SECURITY_TESTING.md

# 3. Commit with detailed message
git commit -m "feat: implement advanced ML retraining system with comprehensive security

- Add production-ready ML retraining worker with continuous learning
- Implement multi-layer security detection (ensemble ML + threat intel)
- Add comprehensive test suite for localhost validation
- Integrate VirusTotal, URLhaus, PhishTank APIs
- Add malware scanning and sandbox execution
- Implement adversarial training and evasion detection
- Add performance benchmarks and security audit tools

Tests: All security tests pass with 99.5%+ detection rate
Security: Zero critical vulnerabilities, evasion-resistant
Performance: 1000+ emails/min, <500ms latency

Breaking changes: None
Migration required: Run database migrations before deploy"

# 4. Create feature branch
git checkout -b feature/advanced-security-ml-retraining

# 5. Push to remote
git push -u origin feature/advanced-security-ml-retraining

# 6. Create pull request for review
gh pr create --title "Advanced ML Retraining & Security Hardening" \
  --body "Comprehensive security improvements with localhost testing validation"
```

## Next Steps

1. Run all tests: `python tests/run_all.py`
2. Fix any failures
3. Run security audit: `python tests/security/audit.py`
4. Generate report: `python tests/security/generate_report.py`
5. Review report with team
6. Commit only after 100% pass rate
7. Create PR for code review
8. Deploy to staging after PR approval

## Emergency Rollback

If issues found after deployment:

```bash
# Revert to previous version
git revert HEAD

# Or restore specific commit
git checkout <previous_commit_hash>

# Redeploy
docker-compose restart
```

---

**Remember: Security first, production later!**
