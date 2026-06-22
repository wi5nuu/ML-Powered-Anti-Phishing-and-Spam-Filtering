import pytest
from classifier.features import EmailParser, ParsedEmail


def test_parse_simple_text_email():
    raw = """\
From: test@example.com
To: user@lodaya.id
Subject: Hello

This is a test email.
"""
    parser = EmailParser()
    parsed = parser.parse(raw)
    assert isinstance(parsed, ParsedEmail)
    assert parsed.sender == "test@example.com"
    assert parsed.subject == "Hello"
    assert "test email" in parsed.body_text


def test_parse_html_email():
    raw = """\
From: spam@phishing.xyz
To: victim@lodaya.id
Subject: Win Prize
Content-Type: text/html

<html><body><a href="http://evil.com">Click here</a></body></html>
"""
    parser = EmailParser()
    parsed = parser.parse(raw)
    assert len(parsed.urls) > 0
    assert "http://evil.com" in parsed.urls[0]


def test_parse_multipart():
    raw = """\
From: devops@lodaya.id
To: all@lodaya.id
Subject: Test
Content-Type: multipart/mixed; boundary="--boundary"

----boundary
Content-Type: text/plain

Plain text body
----boundary
Content-Type: text/html

<html><body>HTML body</body></html>
----boundary--
"""
    parser = EmailParser()
    parsed = parser.parse(raw)
    assert "Plain text body" in parsed.body_text
    assert "HTML body" in parsed.body_html


def test_parse_attachment():
    raw = """\
From: attacker@evil.com
To: user@lodaya.id
Subject: Invoice
Content-Type: multipart/mixed; boundary="--boundary"

----boundary
Content-Type: text/plain

Please see attached invoice.
----boundary
Content-Disposition: attachment; filename="invoice.exe"
Content-Type: application/octet-stream

fake-binary-content
----boundary--
"""
    parser = EmailParser()
    parsed = parser.parse(raw)
    assert len(parsed.attachments) > 0
    assert parsed.attachments[0]["filename"] == "invoice.exe"
    assert parsed.attachments[0]["is_executable"]
