import unittest

from app.main import EmailRequest, process_email_endpoint


class ProcessEmailResponseContractTest(unittest.TestCase):
    def test_process_email_endpoint_returns_string_contract(self):
        def fake_orchestrator(email):
            return {
                "status": "replied",
                "reply": "Thanks for your message.",
                "intent": "refund_status",
                "intent_confidence": 0.93,
                "emotion": "neutral",
                "emotion_intensity": 0.5,
                "grounded": True,
                "email_decision": "AUTO_SEND",
                "human_review_required": False,
            }

        import app.main as main_module
        main_module.orchestrator_process_email = fake_orchestrator

        result = process_email_endpoint(
            EmailRequest(
                customer_email="customer@example.com",
                subject="Refund question",
                body="I want to know my refund status.",
            )
        )

        self.assertIsInstance(result["intent_confidence"], str)
        self.assertIsInstance(result["emotion_intensity"], str)
        self.assertIsInstance(result["grounded"], str)
        self.assertIsInstance(result["human_review_required"], str)
        self.assertEqual(result["intent_confidence"], "0.93")
        self.assertEqual(result["emotion_intensity"], "0.5")
        self.assertEqual(result["grounded"], "True")
        self.assertEqual(result["human_review_required"], "False")


if __name__ == "__main__":
    unittest.main()
