"""REAL SMTP EMAIL IMPLEMENTATION - QUICK START GUIDE

================================================================================
IN 5 MINUTES
================================================================================

1️⃣ GENERATE GMAIL APP PASSWORD
   Visit: https://myaccount.google.com/security
   - Enable "2-Step Verification"
   - Click "App passwords"
   - Select "Mail" and "Windows Computer"
   - Copy the 16-character password (e.g., abcd efgh ijkl mnop)

2️⃣ UPDATE .env FILE
   Edit: .env
   
   Change from:
   SMTP_EMAIL=
   SMTP_PASSWORD=
   
   To:
   SMTP_EMAIL=your-email@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop
   SMTP_MOCK_MODE=false

3️⃣ TEST CONFIGURATION
   Run: python test_smtp.py
   
   This verifies:
   ✓ Credentials loaded from .env
   ✓ SMTP connection works
   ✓ Authentication succeeds
   ✓ Email can be sent

4️⃣ START APPLICATION
   Run: uvicorn app.main:app --reload
   
   Application will:
   - Process incoming emails
   - Generate AI replies
   - Send emails via SMTP
   - Log results to database

5️⃣ MONITOR LOGS
   Watch for:
   ✓ "Email sent successfully to customer@example.com"
   ✗ "SMTP authentication failed" (credentials issue)
   ✗ "Failed to send email reply" (other error)

================================================================================
COMPLETE IMPLEMENTATION FLOW
================================================================================

EMAIL ARRIVES:
    └─→ Gmail API fetches email
        └─→ app/email/fetch_emails.py

EMAIL PROCESSING:
    └─→ handle_customer_email()
        ├─→ Preprocess text
        ├─→ Classify intent
        ├─→ Detect emotion
        ├─→ Retrieve knowledge context
        ├─→ Retrieve similar user messages
        ├─→ Generate reply
        └─→ Calculate confidence score

DECISION POINT:
    ├─→ IF confidence < 0.6 OR angry complaint
    │   └─→ ESCALATE
    │       ├─→ escalate_to_human()
    │       │   └─→ send_email_reply() ← USES SMTP
    │       │       └─→ support@shopifyx.com
    │       └─→ save_email_record(status="escalated")
    │
    └─→ ELSE (confidence high & not angry)
        └─→ SEND REPLY
            ├─→ send_email_reply() ← USES SMTP
            │   └─→ customer@example.com
            ├─→ store_reply_memory()
            └─→ save_email_record(status="replied")

LOGGING:
    └─→ Supabase database (email_records table)
        ├─→ sender
        ├─→ subject
        ├─→ body
        ├─→ intent
        ├─→ emotion
        ├─→ reply
        ├─→ confidence
        ├─→ status ("replied", "escalated", "failed")
        └─→ timestamp

================================================================================
FUNCTION: send_email_reply()
================================================================================

Location: app/email/send_email.py

>>> from app.email.send_email import send_email_reply
>>> 
>>> success = send_email_reply(
...     to="customer@example.com",
...     subject="Your Order",
...     body="Your order is being processed."
... )

WHAT HAPPENS INSIDE:

1. Validate inputs (to, subject, body)
2. Check if credentials exist (SMTP_EMAIL, SMTP_PASSWORD)
3. Format email:
   - Add "Re: " to subject if needed
   - Add "Hi," greeting
   - Add body text
   - Add signature
4. Create MIME message
5. Open SMTP connection to smtp.gmail.com:587
6. Start TLS encryption
7. Authenticate with credentials
8. Send email
9. Return success/failure

LOGGING:

Debug Messages:
    "Connecting to SMTP server smtp.gmail.com:587"
    "TLS connection established"
    "SMTP authentication successful"

Success Message:
    "Email sent successfully to customer@example.com"

Error Messages:
    "SMTP authentication failed"
    "SMTP error: [details]"
    "Failed to send email reply to customer@example.com"

================================================================================
EXAMPLE: FROM CUSTOMER EMAIL TO SENT REPLY
================================================================================

STEP 1: Customer sends email
    From: customer@example.com
    Subject: Can I return my order?
    Body: I received the wrong item. Can I return it?

STEP 2: Application processes
    ├─→ Preprocess: "i received wrong item can i return it"
    ├─→ Intent: "Refund Request" (confidence: 0.92)
    ├─→ Emotion: "frustrated" (confidence: 0.85)
    ├─→ Knowledge: Retrieves refund policy (2 chunks)
    ├─→ User memory: No similar past messages
    ├─→ Strategy: "policy_focused"
    └─→ Reply Generated: "We understand your frustration..."

STEP 3: Calculate confidence
    Base score: 0.5
    + Context docs quality: 0.25 (2 good matches)
    + User memory: 0.0 (no matches)
    + Reply length: 0.15 (200+ characters)
    = 0.9 (high confidence)

STEP 4: Check escalation
    Confidence 0.9 > 0.6 ✓
    Not an angry complaint ✓
    → NO ESCALATION, send reply

STEP 5: Send email
    send_email_reply(
        to="customer@example.com",
        subject="Can I return my order?",
        body="We understand your frustration..."
    )
    
    Generated email:
    
    From: support@shopifyx.com
    To: customer@example.com
    Subject: Re: Can I return my order?
    
    Hi,
    
    We understand your frustration and are here to help.
    Our refund policy allows returns within 30 days...
    [generated response]
    
    Best regards,
    ShopiFyX Support Team

STEP 6: Log result
    INSERT INTO email_records:
        sender: customer@example.com
        subject: Can I return my order?
        body: I received the wrong item...
        intent: Refund Request
        emotion: frustrated
        reply: We understand your frustration...
        confidence: 0.9
        status: replied
        timestamp: 2026-03-23T14:25:30Z

RESULT:
    ✓ Email sent to customer
    ✓ Reply stored in memory
    ✓ Logged to database
    ✓ Ready for next email

================================================================================
CONFIGURATION: .env SETUP
================================================================================

BEFORE (Development - Mock Mode):
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    SMTP_EMAIL=
    SMTP_PASSWORD=
    SMTP_MOCK_MODE=true

AFTER (Production - Real SMTP):
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    SMTP_EMAIL=support@shopifyx.com
    SMTP_PASSWORD=abcdefghijklmnop
    SMTP_MOCK_MODE=false

MOCK MODE (true):
    ├─→ Emails are printed to console
    ├─→ [MOCK EMAIL] prefix added
    ├─→ No real emails sent
    ├─→ Useful for development/testing
    └─→ No credentials needed

REAL MODE (false):
    ├─→ Emails sent via real SMTP
    ├─→ Credentials must be valid
    ├─→ TLS connection required
    ├─→ Gmail App Password needed
    └─→ Check logs for success/errors

================================================================================
ERROR HANDLING & RECOVERY
================================================================================

SCENARIO 1: SMTP credentials not configured
    Error: "SMTP credentials not configured. Set SMTP_EMAIL and SMTP_PASSWORD"
    Fix: Add values to .env and restart
    Time to fix: < 1 minute

SCENARIO 2: Wrong password
    Error: "SMTP authentication failed: Invalid email or password"
    Fix: Regenerate Gmail App Password, update .env
    Time to fix: 5 minutes

SCENARIO 3: Network issue
    Error: "SMTPServerDisconnected" or connection timeout
    Fix: Check internet, retry after 30 seconds
    Time to fix: 2-5 minutes

SCENARIO 4: Gmail rate limit
    Error: "Too many connections from your IP"
    Fix: Wait 1 hour, Gmail will lift the limit
    Time to fix: 1 hour

SCENARIO 5: Port blocked by firewall
    Error: Connection timeout on port 587
    Fix: Contact IT, open port 587 for SMTP
    Time to fix: Depends on IT

================================================================================
TESTING SCENARIOS
================================================================================

TEST 1: Credential Verification ✓
    Command: python test_smtp.py
    Expected: [✓ Credentials confirmed]
    Time: < 5 seconds

TEST 2: Connection Test ✓
    Command: python test_smtp.py
    Expected: [✓ SMTP connection test passed]
    Time: < 5 seconds

TEST 3: Send Test Email ✓
    Command: python test_smtp.py (choose interactive test)
    Expected: Email arrives in inbox
    Time: 5-30 seconds

TEST 4: Integration Test ✓
    Send POST to /process-email endpoint with sample email
    Expected: Reply sent to customer
    Time: 5-10 seconds

TEST 5: Escalation Test ✓
    Send email for angry complaint
    Expected: Escalation email to support@shopifyx.com
    Time: 5-10 seconds

================================================================================
MONITORING & LOGGING
================================================================================

WHERE TO CHECK:

1. Application Console/Terminal
   ├─→ INFO: "Email sent successfully to..."
   ├─→ ERROR: "Failed to send email reply..."
   └─→ DEBUG: Connection details

2. Database Logs
   Location: email_records table (Supabase)
   Fields:
   ├─→ status (replied, escalated, failed)
   ├─→ confidence (0.0-1.0)
   ├─→ timestamp
   └─→ created_at

3. Customer Inbox
   ├─→ From: support@shopifyx.com
   ├─→ Subject: Re: [original subject]
   └─→ Body: Generated reply with signature

4. Support Escalation Inbox
   ├─→ Escalated emails to support@shopifyx.com
   ├─→ With escalation reason
   └─→ Original + generated reply for reference

HEALTH CHECK QUERIES:

Total emails processed:
    SELECT COUNT(*) FROM email_records;

Success rate:
    SELECT status, COUNT(*) FROM email_records GROUP BY status;

Last email status:
    SELECT * FROM email_records ORDER BY created_at DESC LIMIT 1;

Escalations today:
    SELECT * FROM email_records 
    WHERE status='escalated' AND created_at >= NOW() - interval '1 day';

Emails by customer:
    SELECT sender, COUNT(*) FROM email_records GROUP BY sender;

================================================================================
PRODUCTION CHECKLIST
================================================================================

□ Gmail account created and configured
□ 2-Factor Authentication enabled
□ App Password generated (16 characters)
□ .env file updated with credentials
□ SMTP_MOCK_MODE=false in .env
□ test_smtp.py run successfully (all checks pass)
□ Test email received in inbox
□ Application started without errors
□ First production email sent and received
□ Logs reviewed for any errors
□ Monitoring dashboard accessed
□ Team notified of production readiness
□ Backup email account configured (optional)
□ Alert system set up for failures (optional)

================================================================================
NEXT STEPS
================================================================================

1. Run test_smtp.py to verify configuration
2. Send a test email to your email address
3. Check application logs for success message
4. Deploy to production
5. Monitor logs and email_records table
6. Set up alerts for sending failures
7. Configure backup SMTP server (optional)
8. Document production credentials in secure location
9. Set up periodic test emails
10. Monitor email delivery rates

================================================================================
SUPPORT & TROUBLESHOOTING
================================================================================

For detailed setup guide:
    See: SMTP_SETUP_GUIDE.md

For quick reference:
    See: SMTP_IMPLEMENTATION_SUMMARY.md

To verify configuration:
    Run: python test_smtp.py

To send test email:
    Run: python test_smtp.py (interactive option)

For issues:
    1. Check .env file has credentials
    2. Run test_smtp.py to diagnose
    3. Check application logs
    4. Verify Gmail App Password is valid
    5. Check internet connection

================================================================================
"""
