"""Guide: Configuring and Using Real SMTP Email Sending with SalesAI

This document provides step-by-step instructions for setting up real SMTP email
sending using Gmail's SMTP server.

================================================================================

## STEP 1: Generate Gmail App Password

Gmail doesn't allow direct access with regular passwords. You must use an
"App Password" for SMTP connections.

Prerequisites:
- Gmail account
- 2-Factor Authentication enabled on your Google account

Steps:
1. Go to: https://myaccount.google.com/security
2. Click "App passwords" (if not visible, ensure 2FA is enabled)
3. Select "Mail" and "Windows Computer" (or your OS)
4. Google will generate a 16-character password
5. Copy this password (it has spaces, you may need to remove them)

Example App Password: abcd efgh ijkl mnop
Use as: abcdefghijklmnop

================================================================================

## STEP 2: Update .env Configuration

Edit `.env` file and fill in SMTP credentials:

```
# SMTP Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password

# Disable mock mode to send real emails
SMTP_MOCK_MODE=false
```

Example:
```
SMTP_EMAIL=support@shopifyx.com
SMTP_PASSWORD=abcdefghijklmnop
SMTP_MOCK_MODE=false
```

⚠️ Important:
- SMTP_PASSWORD is the App Password, NOT your Gmail password
- Do NOT commit .env file to version control (it's in .gitignore)
- Keep credentials secure

================================================================================

## STEP 3: Usage Examples

### Option 1: Using send_email_reply() - Recommended

```python
from app.email.send_email import send_email_reply

# Send a reply
success = send_email_reply(
    to="customer@example.com",
    subject="Your Order Status",
    body="Your order #12345 is being processed and will ship tomorrow."
)

if success:
    print("Email sent successfully!")
else:
    print("Failed to send email - check logs")
```

Function automatically:
- Adds "Re: " to subject
- Formats body with greeting and signature
- Handles SMTP connection and TLS
- Logs all activity

### Option 2: Using send_email() - Flexible

```python
from app.email.send_email import send_email

success = send_email(
    to_email="customer@example.com",
    subject="Your Order Status",
    body="Your order #12345 is being processed.",
    use_reply_prefix=True  # Adds "Re: " to subject
)
```

This function:
- Tries Gmail API first (if configured)
- Falls back to SMTP automatically
- Adds signature from config
- Supports mock mode for testing

================================================================================

## STEP 4: Testing the Setup

### Test 1: Verify Configuration

```python
import os
from dotenv import load_dotenv

load_dotenv()

smtp_email = os.getenv("SMTP_EMAIL")
smtp_password = os.getenv("SMTP_PASSWORD")
mock_mode = os.getenv("SMTP_MOCK_MODE", "false").lower()

print(f"SMTP Email: {smtp_email}")
print(f"Password configured: {bool(smtp_password)}")
print(f"Mock mode: {mock_mode}")
```

### Test 2: Send Test Email

```python
from app.email.send_email import send_email_reply

result = send_email_reply(
    to="your-test-email@gmail.com",
    subject="Test Email from SalesAI",
    body="This is a test email to verify SMTP configuration."
)

print(f"Email sent: {result}")
```

### Test 3: Check Logs

```bash
# Watch application logs for email sending
# Should see: INFO: Email sent successfully to your-test-email@gmail.com
```

================================================================================

## STEP 5: Integration with Orchestrator

The orchestrator automatically sends emails when processing customer messages:

```python
# In app/agents/orchestrator.py
result = handle_customer_email(
    customer_email="customer@example.com",
    subject="Help with order",
    body="I have a question about my order..."
)

# Result includes:
# - status: "replied", "escalated", or "failed"
# - reply: generated reply (or escalation email)
# - confidence: confidence score
```

If status is "replied", the email has been sent to the customer.
If status is "escalated", email has been sent to support@shopifyx.com.

================================================================================

## STEP 6: Troubleshooting

### Error: "SMTP credentials not configured"
Solution: Make sure SMTP_EMAIL and SMTP_PASSWORD are set in .env

### Error: "SMTP authentication failed"
Solution: 
- Verify you're using an App Password, not your regular Gmail password
- Check that 2FA is enabled on your Google account
- Remove any spaces from the password

### Error: "SMTPServerDisconnected"
Solution:
- Check internet connection
- Verify firewall allows port 587
- Try again after a short delay

### Emails not being sent in production
Solution:
- Set SMTP_MOCK_MODE=false in .env
- Check that SMTP credentials are configured
- Verify logs for error messages
- Enable debug logging for detailed connection info

### Gmail marks emails as spam
Solution:
- Add a footer/signature to emails
- Use consistent branding
- Implement SPF/DKIM records on your domain
- Monitor Gmail Postmaster Tools

================================================================================

## IMPLEMENTATION DETAILS

### send_email_reply() Function

Location: app/email/send_email.py

**Parameters:**
- to (str): Recipient email address
- subject (str): Email subject (without "Re:" prefix)
- body (str): Email body text

**Returns:**
- True: Email sent successfully
- False: Failed to send (check logs)

**Email Format:**

From: (your SMTP_EMAIL)
To: (customer email)
Subject: Re: (original subject)

Hi,

(your message body)

Best regards,
ShopiFyX Support Team

### Logging

The function provides comprehensive logging:

```
DEBUG: Connecting to SMTP server smtp.gmail.com:587
DEBUG: TLS connection established
DEBUG: SMTP authentication successful
INFO: Email sent successfully to customer@example.com
```

Error logging:
```
ERROR: SMTP authentication failed: Invalid email or password
ERROR: Failed to send email reply to customer@example.com: <error details>
```

================================================================================

## STEP 7: Environment Configuration Examples

### Development Setup (Mock Mode)
```
SMTP_MOCK_MODE=true
SMTP_EMAIL=
SMTP_PASSWORD=
```
Emails print to console instead of being sent.

### Staging Setup (Real SMTP)
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=staging@shopifyx.com
SMTP_PASSWORD=<app-password>
SMTP_MOCK_MODE=false
```

### Production Setup (Real SMTP)
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=support@shopifyx.com
SMTP_PASSWORD=<app-password>
SMTP_MOCK_MODE=false
```

================================================================================

## Alternative SMTP Servers

If not using Gmail, you can configure other SMTP servers:

### SendGrid
```
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_EMAIL=apikey
SMTP_PASSWORD=SG._____
```

### AWS SES
```
SMTP_SERVER=email-smtp.<region>.amazonaws.com
SMTP_PORT=587
SMTP_EMAIL=<verified sender>
SMTP_PASSWORD=<session token>
```

### Office 365
```
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_EMAIL=your-email@company.com
SMTP_PASSWORD=<your password>
```

================================================================================

## Security Best Practices

1. ✅ Never commit .env to version control
2. ✅ Use App Passwords, not regular account passwords
3. ✅ Rotate passwords periodically
4. ✅ Store credentials in .env (never hardcode)
5. ✅ Use TLS/STARTTLS (port 587, not 25 or 465 unencrypted)
6. ✅ Enable logging for audit trails
7. ✅ Monitor for failed delivery attempts
8. ✅ Validate email addresses before sending

================================================================================

## Support

For issues or questions:
1. Check the logs in the terminal/console
2. Verify SMTP credentials in .env
3. Test Gmail App Password generation
4. Enable debug logging in send_email.py
5. Review SMTP server documentation

Last updated: March 23, 2026
"""
