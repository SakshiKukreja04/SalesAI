#!/usr/bin/env python
"""SMTP Configuration Verification and Testing Script

This script tests SMTP email sending configuration for SalesAI.

Usage:
    python test_smtp.py
    
    Or from Python:
    python -c "from test_smtp import verify_smtp_config; verify_smtp_config()"
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
LOGGER = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env"""
    load_dotenv()
    LOGGER.info("Environment variables loaded")


def check_credentials():
    """Verify SMTP credentials are configured"""
    LOGGER.info("\n=== CHECKING CREDENTIALS ===")
    
    smtp_server = os.getenv("SMTP_SERVER", "").strip()
    smtp_port = os.getenv("SMTP_PORT", "").strip()
    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_mock = os.getenv("SMTP_MOCK_MODE", "true").lower().strip()
    
    print(f"SMTP_SERVER:     {smtp_server}")
    print(f"SMTP_PORT:       {smtp_port}")
    print(f"SMTP_EMAIL:      {smtp_email if smtp_email else '❌ NOT SET'}")
    print(f"SMTP_PASSWORD:   {'✓ SET' if smtp_password else '❌ NOT SET'}")
    print(f"SMTP_MOCK_MODE:  {smtp_mock}")
    
    if not smtp_email:
        LOGGER.error("❌ SMTP_EMAIL is not configured. Set in .env file.")
        return False
    
    if not smtp_password:
        LOGGER.error("❌ SMTP_PASSWORD is not configured. Set in .env file.")
        return False
    
    if smtp_mock.lower() == "true":
        LOGGER.warning("⚠️  SMTP_MOCK_MODE is enabled. Real emails won't be sent.")
        return True
    
    LOGGER.info("✓ Core credentials configured")
    return True


def test_smtp_connection():
    """Test SMTP server connection"""
    LOGGER.info("\n=== TESTING SMTP CONNECTION ===")
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_email = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    
    if not smtp_email or not smtp_password:
        LOGGER.warning("⚠️  Skipping connection test - credentials not configured")
        return True
    
    try:
        import smtplib
        
        LOGGER.info(f"Connecting to {smtp_server}:{smtp_port}...")
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
            LOGGER.info("✓ Connection established")
            
            LOGGER.info("Starting TLS...")
            server.starttls()
            LOGGER.info("✓ TLS connection secured")
            
            LOGGER.info("Attempting authentication...")
            server.login(smtp_email, smtp_password)
            LOGGER.info("✓ Authentication successful")
        
        LOGGER.info("✓ SMTP connection test passed")
        return True
        
    except smtplib.SMTPAuthenticationError as exc:
        LOGGER.error("❌ Authentication failed - verify SMTP_EMAIL and SMTP_PASSWORD")
        LOGGER.error(f"   Details: {exc}")
        return False
        
    except smtplib.SMTPException as exc:
        LOGGER.error(f"❌ SMTP error: {exc}")
        return False
        
    except Exception as exc:
        LOGGER.error(f"❌ Connection failed: {exc}")
        return False


def test_email_sending():
    """Test sending a test email"""
    LOGGER.info("\n=== TESTING EMAIL SENDING ===")
    
    smtp_email = os.getenv("SMTP_EMAIL", "")
    smtp_mock = os.getenv("SMTP_MOCK_MODE", "true").lower() == "true"
    
    if not smtp_email:
        LOGGER.warning("⚠️  Skipping email test - SMTP_EMAIL not configured")
        return True
    
    if smtp_mock:
        LOGGER.info("ℹ️  Mock mode enabled - email will be printed to console")
    
    try:
        from app.email.send_email import send_email_reply
        
        test_email = "test-recipient@example.com"
        LOGGER.info(f"Sending test email to {test_email}...")
        
        success = send_email_reply(
            to=test_email,
            subject="SMTP Configuration Test",
            body="This is a test email to verify SMTP configuration is working."
        )
        
        if success:
            if smtp_mock:
                LOGGER.info("✓ Test email prepared (mock mode)")
            else:
                LOGGER.info("✓ Test email sent successfully")
            return True
        else:
            LOGGER.error("❌ Failed to send test email - check logs above")
            return False
            
    except Exception as exc:
        LOGGER.error(f"❌ Error during email test: {exc}")
        return False


def test_with_real_email():
    """Interactive test with a real email address"""
    LOGGER.info("\n=== INTERACTIVE TEST ===")
    
    smtp_mock = os.getenv("SMTP_MOCK_MODE", "true").lower() == "true"
    
    if smtp_mock:
        LOGGER.info("Mock mode is enabled - no real email will be sent")
    
    try:
        email = input("Enter your email address to send a test email (or press Enter to skip): ").strip()
        
        if not email:
            LOGGER.info("Skipping interactive test")
            return True
        
        if "@" not in email:
            LOGGER.error("❌ Invalid email address")
            return False
        
        from app.email.send_email import send_email_reply
        
        LOGGER.info(f"Sending test email to {email}...")
        
        success = send_email_reply(
            to=email,
            subject="SalesAI SMTP Test",
            body="This is a test email to verify that SalesAI can send emails successfully."
        )
        
        if success:
            LOGGER.info(f"✓ Test email sent to {email}")
            if not smtp_mock:
                LOGGER.info("Check your inbox for the email")
            return True
        else:
            LOGGER.error("❌ Failed to send test email")
            return False
            
    except KeyboardInterrupt:
        LOGGER.info("\n⚠️  Test cancelled by user")
        return True
    except Exception as exc:
        LOGGER.error(f"❌ Error: {exc}")
        return False


def verify_smtp_config():
    """Main verification function"""
    LOGGER.info("=" * 60)
    LOGGER.info("SalesAI SMTP Configuration Verification")
    LOGGER.info("=" * 60)
    
    load_env()
    
    # Run checks
    checks = [
        ("Credentials", check_credentials),
        ("SMTP Connection", test_smtp_connection),
        ("Email Sending", test_email_sending),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as exc:
            LOGGER.error(f"❌ {name} check failed: {exc}")
            results.append((name, False))
    
    # Summary
    LOGGER.info("\n" + "=" * 60)
    LOGGER.info("SUMMARY")
    LOGGER.info("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        LOGGER.info(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        LOGGER.info("\n✓ All checks passed!")
        
        # Offer interactive test
        try:
            if input("\nRun interactive test with your email? (y/n): ").lower() == "y":
                test_with_real_email()
        except EOFError:
            pass
    else:
        LOGGER.error("\n❌ Some checks failed. See details above.")
        return False
    
    return all_passed


if __name__ == "__main__":
    success = verify_smtp_config()
    sys.exit(0 if success else 1)
