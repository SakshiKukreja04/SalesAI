# ShopiFyX Payment Failures, Double Debits, and Transaction Disputes Policy

## 1. Overview of Payment Processing
ShopiFyX integrates with leading banking partners and payment gateways (including UPI, Credit/Debit Card networks, and Net Banking) to process transactions securely. During high network traffic or intermittent bank server downtime, payment discrepancies such as unconfirmed orders or duplicate debits may occasionally occur.

## 2. Payment Deducted but Order Not Confirmed
When money is deducted from the customer's bank account or digital wallet but no order confirmation email or order ID is generated on ShopiFyX:
- **Root Cause**: A temporary communication timeout between the customer's issuing bank and the ShopiFyX payment gateway.
- **Auto-Reconciliation**: The payment gateway runs an automated reconciliation cycle every 2 hours. In over 95% of cases, the order is automatically confirmed within 2 hours, or an automatic refund is triggered by the banking switch.
- **Resolution Timeline**: 
  - If the order is not confirmed within 2 hours, the deducted funds are automatically reversed by the issuing bank within **3 to 5 business days**.
  - No manual intervention is needed for the auto-reversal to complete.
- **Recommended Action for Customers**:
  - Wait 2 hours before placing a replacement order to avoid unintended duplicate purchases.
  - Check bank transaction reference or UTR (Unique Transaction Reference) number.

## 3. Double Charges / Duplicate Debits
If a customer clicks the payment button multiple times or experiences a network re-try resulting in multiple deductions for a single order:
- **Automatic Reversal**: ShopiFyX's payment gateway detects duplicate captures on the same merchant order session. The redundant transaction is automatically flagged and sent for voiding/reversal immediately.
- **Refund Timeline**: The duplicate charge will be credited back to the original payment source within **3 to 5 business days** (for Net Banking/Cards) or **24 to 48 hours** (for UPI).
- **Manual Assistance**: If the duplicate debit is not refunded within 5 business days, the customer should contact support with their bank statement and transaction reference (UTR) numbers.

## 4. Failed Transactions / Declined Payments
If an attempted transaction fails at the checkout stage:
- **Common Causes**:
  - Insufficient account balance or card limit.
  - Incorrect OTP, CVV, or 3D Secure authentication failure.
  - Bank server timeout or downtime.
  - Daily UPI transaction limit reached.
- **Action Required**:
  - Verify bank balance and retry with another payment method (e.g., alternative card, Net Banking, or UPI ID).
  - Check whether the bank has sent an SMS or notification regarding temporary security blocks.

## 5. Information Required for Payment Support Investigations
When a customer contacts ShopiFyX support regarding payment discrepancies, customer support will ask for:
- Registered email address and phone number.
- Date and approximate time of the transaction.
- Exact amount debited.
- Mode of payment used (e.g., HDFC Credit Card, Google Pay UPI, PhonePe).
- Bank Reference Number / UTR (12-digit reference provided in the bank transaction SMS).

## 6. Strict Security & AI Policy Guardrails
- **Zero Credential Sharing**: ShopiFyX customer support and SalesAI will **NEVER** ask for:
  - OTPs (One-Time Passwords)
  - Card PINs or ATM PINs
  - Full 16-digit Card Numbers or CVVs
  - Internet Banking Passwords or UPI MPINs
- **No Immediate Instant Refund Claims**: SalesAI must inform the customer of standard banking auto-reversal windows (3–5 business days) and must never promise an instantaneous refund without gateway confirmation.
