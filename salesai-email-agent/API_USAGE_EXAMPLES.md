"""API ENDPOINT USAGE EXAMPLES - SalesAI Email Agent

This document shows how to use the SalesAI email agent API with real SMTP
email sending.

================================================================================
ENDPOINT: POST /process-email
================================================================================

Endpoint: http://localhost:8000/process-email

Description:
    Process a customer email through the AI pipeline and send a reply.
    
    The system will:
    1. Analyze customer email (intent, emotion)
    2. Retrieve relevant knowledge
    3. Generate AI reply
    4. Send email to customer or escalate
    5. Log result to database

================================================================================
REQUEST FORMAT
================================================================================

URL:
    POST http://localhost:8000/process-email

Headers:
    Content-Type: application/json

Body:
    {
        "customer_email": "customer@example.com",
        "subject": "Question about my order",
        "body": "Hi, I ordered something last week but haven't received it yet..."
    }

Required Fields:
    - customer_email: Customer's email address
    - subject: Email subject line
    - body: Email body/message

================================================================================
RESPONSE FORMAT
================================================================================

Success Response:
    Status: 200 OK
    
    {
        "status": "replied",
        "reply": "Thank you for contacting us...",
        "confidence": "0.85",
        "intent": "Order Status",
        "emotion": "neutral",
        "escalation_reason": ""
    }

Escalation Response:
    Status: 200 OK
    
    {
        "status": "escalated",
        "reply": "We understand your concern...",
        "confidence": "0.45",
        "intent": "complaint",
        "emotion": "angry",
        "escalation_reason": "low_confidence (0.45)"
    }

Error Response:
    Status: 200 OK (still returns 200, but status field indicates error)
    
    {
        "status": "failed",
        "reply": "",
        "confidence": "0.00",
        "intent": "",
        "emotion": "",
        "escalation_reason": "processing_error"
    }

Response Fields:
    - status: "replied" (email sent), "escalated" (to support), "failed" (error)
    - reply: The generated reply text
    - confidence: Confidence score 0.00-1.00 as decimal string
    - intent: Detected customer intent
    - emotion: Detected emotion
    - escalation_reason: Why escalated (empty if not escalated)

================================================================================
EXAMPLES
================================================================================

EXAMPLE 1: Simple Inquiry (No Escalation)
───────────────────────────────────────

Request:
    POST /process-email
    Content-Type: application/json
    
    {
        "customer_email": "john@example.com",
        "subject": "Shipping address change",
        "body": "Can I change my shipping address? I ordered yesterday."
    }

Response:
    {
        "status": "replied",
        "reply": "Thank you for reaching out. For orders placed recently, you may be able to modify the shipping address within 24 hours. Please reply with your new address and order number, and we'll assist you immediately.",
        "confidence": "0.87",
        "intent": "account_change_request",
        "emotion": "neutral",
        "escalation_reason": ""
    }

What Happened:
    ✓ Email analyzed (intent, emotion)
    ✓ Knowledge base searched
    ✓ AI generated appropriate reply
    ✓ Confidence high (0.87)
    ✓ Email sent to john@example.com
    ✓ Status recorded in database

EXAMPLE 2: Angry Complaint (Escalation)
─────────────────────────────────────

Request:
    POST /process-email
    Content-Type: application/json
    
    {
        "customer_email": "jane@example.com",
        "subject": "Your product broke immediately!",
        "body": "This is unacceptable! The product broke after 2 days. I want a full refund NOW!"
    }

Response:
    {
        "status": "escalated",
        "reply": "We sincerely apologize for the product quality issue...",
        "confidence": "0.52",
        "intent": "complaint",
        "emotion": "angry",
        "escalation_reason": "angry_complaint"
    }

What Happened:
    ✓ Email analyzed (intent: complaint, emotion: angry)
    ✓ Escalation criteria met (angry + complaint)
    ✓ Email sent to support@shopifyx.com with:
        ├─ Original customer email
        ├─ Generated reply for reference
        └─ Escalation reason
    ✓ Status: escalated
    ✓ Human support team will review

EXAMPLE 3: Low Confidence (Escalation)
──────────────────────────────────────

Request:
    POST /process-email
    Content-Type: application/json
    
    {
        "customer_email": "bob@example.com",
        "subject": "Technical issue with app",
        "body": "The app crashes when I try to upload files. Error code: 0x12345"
    }

Response:
    {
        "status": "escalated",
        "reply": "We apologize for the technical issue...",
        "confidence": "0.55",
        "intent": "technical_support",
        "emotion": "frustrated",
        "escalation_reason": "low_confidence (0.55)"
    }

What Happened:
    ✓ Email analyzed (technical issue detected)
    ✓ Knowledge base searched but limited matches
    ✓ AI generated reply but confidence only 0.55
    ✓ Confidence < 0.60 threshold → Escalate
    ✓ Escalation email sent to support@shopifyx.com
    ✓ Technical support team will investigate

EXAMPLE 4: Successful Refund Request
──────────────────────────────────────

Request:
    POST /process-email
    Content-Type: application/json
    
    {
        "customer_email": "alice@example.com",
        "subject": "Request refund for order #12345",
        "body": "I'd like to request a refund for my recent purchase. It doesn't meet my expectations."
    }

Response:
    {
        "status": "replied",
        "reply": "Thank you for contacting us about your refund request. We understand this purchase didn't meet your expectations. Our refund policy allows returns within 30 days with original packaging. Please reply with your order number, and we'll process your return immediately.",
        "confidence": "0.88",
        "intent": "refund_request",
        "emotion": "neutral",
        "escalation_reason": ""
    }

What Happened:
    ✓ Intent detected: refund_request
    ✓ Emotion: neutral (polite request)
    ✓ Knowledge retrieved: Refund policy (high match)
    ✓ Confidence: 0.88 (high)
    ✓ Generated appropriate response
    ✓ Email sent to alice@example.com
    ✓ Stored in memory for future reference

================================================================================
USING WITH cURL
================================================================================

cURL Command:
    curl -X POST http://localhost:8000/process-email \
      -H "Content-Type: application/json" \
      -d '{
        "customer_email": "customer@example.com",
        "subject": "Help with my order",
        "body": "I received the wrong item. What should I do?"
      }'

Response:
    {
        "status": "replied",
        "reply": "We sincerely apologize for sending the wrong item...",
        "confidence": "0.89",
        "intent": "wrong_item_received",
        "emotion": "neutral",
        "escalation_reason": ""
    }

================================================================================
USING WITH POSTMAN
================================================================================

1. Create new POST request
   URL: http://localhost:8000/process-email

2. Set Headers
   Key: Content-Type
   Value: application/json

3. Set Body (raw, JSON)
   {
       "customer_email": "test@example.com",
       "subject": "Test email",
       "body": "This is a test message"
   }

4. Click Send

5. View Response in response panel

================================================================================
USING WITH Python
================================================================================

import requests
import json

url = "http://localhost:8000/process-email"

payload = {
    "customer_email": "customer@example.com",
    "subject": "Question about shipping",
    "body": "How long does standard shipping take?"
}

headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)
result = response.json()

print(f"Status: {result['status']}")
print(f"Reply: {result['reply']}")
print(f"Confidence: {result['confidence']}")
print(f"Intent: {result['intent']}")
print(f"Emotion: {result['emotion']}")

if result['status'] == 'escalated':
    print(f"Escalation Reason: {result['escalation_reason']}")

================================================================================
USING WITH JavaScript
================================================================================

const processEmail = async (customerEmail, subject, body) => {
  const response = await fetch('http://localhost:8000/process-email', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      customer_email: customerEmail,
      subject: subject,
      body: body
    })
  });

  const data = await response.json();
  return data;
};

// Usage:
const result = await processEmail(
  'customer@example.com',
  'Help with my order',
  'I have a question about my recent purchase'
);

console.log('Status:', result.status);
console.log('Reply:', result.reply);
console.log('Confidence:', result.confidence);

================================================================================
EMAIL FLOW WITH API
================================================================================

API Request:
    POST /process-email
    ├─ customer_email: email@example.com
    ├─ subject: Order Question
    └─ body: When will it arrive?

NLP Processing:
    ├─ Preprocess text
    ├─ Intent: order_status (92% confidence)
    └─ Emotion: neutral (88% confidence)

RAG Retrieval:
    ├─ Knowledge search: shipping policy (2 chunks found)
    └─ User memory: similar past questions (1 match)

Reply Generation:
    ├─ Strategy: policy_focused
    ├─ AI generates: "Orders typically arrive..."
    └─ Confidence: 0.89

Escalation Check:
    ├─ Confidence 0.89 > 0.60 ✓
    └─ Not an angry complaint ✓

Send Email:
    └─ send_email_reply()
        ├─ Connect to SMTP
        ├─ Start TLS
        ├─ Authenticate
        └─ Send email

Database Logging:
    └─ INSERT INTO email_records
        ├─ status: replied
        ├─ confidence: 0.89
        └─ timestamp: 2026-03-23...

API Response:
    {
        "status": "replied",
        "reply": "Orders typically arrive...",
        "confidence": "0.89",
        "intent": "order_status",
        "emotion": "neutral",
        "escalation_reason": ""
    }

================================================================================
MONITORING API REQUESTS
================================================================================

Check Application Logs:
    Look for messages like:
    - "[xxxxx] Processing email from customer@example.com"
    - "[xxxxx] Generated reply (confidence=0.85, strategy=policy_focused)"
    - "[xxxxx] Email processed successfully (status=replied)"

Query Database:
    SELECT * FROM email_records 
    WHERE sender = 'customer@example.com'
    ORDER BY created_at DESC;

Check Email Delivery:
    - Check customer's inbox
    - Verify subject line: "Re: [original subject]"
    - Check email signature: "Best regards, ShopiFyX Support Team"

Monitor Escalations:
    SELECT * FROM email_records WHERE status = 'escalated';
    
    Then check support@shopifyx.com inbox for escalation emails

================================================================================
ERROR RESPONSES & SOLUTIONS
================================================================================

Scenario 1:
    Response: status = "failed"
    Reason: Processing error or email sending failed
    Solution: Check application logs for error message, 
              verify SMTP credentials in .env

Scenario 2:
    Response: status = "escalated", confidence = very low
    Reason: AI couldn't generate confident response
    Solution: Human support team needs to review and respond

Scenario 3:
    Response: status = "escalated", emotion = "angry"
    Reason: Customer expressed anger or frustration
    Solution: Support team should prioritize this case

Scenario 4:
    No response (request times out)
    Reason: Processing taking too long or application crash
    Solution: Check if application is still running,
              check application logs for errors

================================================================================
PRODUCTION DEPLOYMENT
================================================================================

Pre-deployment Checklist:

□ SMTP credentials configured in .env
  SMTP_EMAIL=support@shopifyx.com
  SMTP_PASSWORD=<app-password>

□ SMTP_MOCK_MODE=false (not mock)

□ Database connection verified
  Supabase connection string working

□ test_smtp.py passed all checks

□ Test email sent and received

□ Application logs reviewed for errors

□ Health check endpoint: GET /health returns {"status": "ok"}

□ Email inbox monitored

□ Escalation inbox monitored (support@shopifyx.com)

□ Database queries tested

Deployment:
    # Build/test
    python test_smtp.py
    
    # Start application
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    
    # Test endpoint
    curl http://localhost:8000/health
    
    # Monitor logs
    # Watch: email_records table for results

================================================================================
RATE LIMITING & THROTTLING
================================================================================

Gmail SMTP has rate limits:
    - Default: ~100 emails per second
    - Burst: Can temporarily exceed

If hitting rate limits:
    - Error: "SMTPServerDisconnected"
    - Solution: Implement retry logic with exponential backoff
    - Example: retry after 1s, 2s, 4s, 8s...

Configuration (optional):
    Implement in app/email/send_email.py:
    
    import time
    
    for attempt in range(3):
        try:
            send_email_reply(...)
            break
        except:
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
            else:
                raise

================================================================================
"""
