import unittest
from app.agents.generator import sanitize_customer_reply


class TestGeneratorOutputSanitization(unittest.TestCase):
    def test_sanitizes_prompt_trace_and_keeps_final_customer_email(self):
        raw = '''*   User Query: "hello, i ordered winter jacket..."

*   Role: Customer support assistant.

*   Constraint 1: Answer using only provided context.

I understand your concern regarding the payment deduction for your winter jacket while your order remains unconfirmed. To resolve this, please contact our support team so they can investigate the transaction.

When you reach out, please provide your Order ID if available, the transaction reference, your payment method, the approximate transaction time, and the amount charged. You can contact us via email at support@shopifyx.com.'''

        cleaned = sanitize_customer_reply(raw)

        self.assertNotIn('User Query:', cleaned)
        self.assertNotIn('Role:', cleaned)
        self.assertNotIn('Constraint', cleaned)
        self.assertIn('I understand your concern', cleaned)
        self.assertIn('support@shopifyx.com', cleaned)

    def test_extracts_json_response_field(self):
        raw = '{"response": "Thanks for reaching out. We will review it soon.", "grounded": true}'

        cleaned = sanitize_customer_reply(raw)

        self.assertIn("Thanks for reaching out. We will review it soon.", cleaned)
        self.assertTrue(cleaned.startswith("Hi,"))
        self.assertTrue(cleaned.endswith("Best regards,\nCustomer Support Team\nShopiFyX"))

    def test_strips_self_correction_and_final_draft_noise(self):
        raw = '''Hi Sakshikukreja,

I understand you're looking for information regarding the conditions for a refund.

(Self-Correction during drafting): The prompt asks for a direct answer, next action, and brief empathetic statement when appropriate.

[Direct Answer + Empathy/Acknowledgment]

I understand you are inquiring about the necessary conditions for a refund. To be eligible, you may request a refund within 7 days of the product's delivery, provided that the item is unused and remains in its original packaging. You must also have the invoice available, and the product must not have been damaged through any misuse.

Please note that additional product-specific restrictions may apply, and certain categories such as personal care products, opened electronics, clearance sale items, and gift cards are currently non-refundable. If you believe your product meets these criteria, the next step is to contact our support team to initiate the review and verification process.

Best regards,
Customer Support Team'''

        cleaned = sanitize_customer_reply(raw, customer_name="Sakshi Kukreja")

        self.assertNotIn("Self-Correction", cleaned)
        self.assertNotIn("Direct Answer", cleaned)
        self.assertIn("refund within 7 days", cleaned)
        self.assertIn("contact our support team", cleaned)
        self.assertTrue(cleaned.startswith("Hi Sakshi,"))
        self.assertTrue(cleaned.endswith("Best regards,\nCustomer Support Team\nShopiFyX"))


if __name__ == "__main__":
    unittest.main()
