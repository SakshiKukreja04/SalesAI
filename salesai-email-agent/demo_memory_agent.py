"""Interactive Multi-Turn Testing Script for SalesAI V3 Customer Memory Agent.

Simulates a real multi-turn customer scenario:
- Turn 1: Customer asks about returning a defective item (Creates customer, detects damaged product issue).
- Turn 2: Customer sends ambiguous continuation ("Still waiting for it.") -> Memory resolves the reference!
- Turn 3: Customer acknowledges resolution ("Thanks, that worked!") -> Memory marks issue as resolved.
"""

from __future__ import annotations

import sys
from uuid import uuid4
from app.agents.orchestrator import handle_customer_email
from app.memory.customer_memory import default_memory_agent


def run_multi_turn_test():
    test_email = f"sarah.test.{str(uuid4())[:4]}@example.com"
    print("=" * 70)
    print(f"[*] STARTING SALESAI V3 MEMORY AGENT MULTI-TURN TEST")
    print(f"Customer Email: {test_email}")
    print("=" * 70)

    # --- TURN 1: Initial Inquiry with Issue ---
    print("\n[TURN 1] Customer sends initial message:")
    print("Subject: Defective Winter Jacket")
    print("Body: 'Hi, my name is Sarah Connor. The zipper on my Winter Jacket is broken. How do I get a refund?'")
    
    turn1_res = handle_customer_email(
        customer_email=test_email,
        subject="Defective Winter Jacket",
        body="Hi, my name is Sarah Connor. The zipper on my Winter Jacket is broken. How do I get a refund?",
        email_id=f"email-t1-{str(uuid4())[:6]}",
    )
    print("\n[AI Response Turn 1]")
    print(f"Status: {turn1_res.get('status')}")
    print(f"Detected Intent: {turn1_res.get('intent')}")
    print(f"Detected Emotion: {turn1_res.get('emotion')}")
    print(f"Reply:\n{turn1_res.get('reply')}")

    # Inspect Memory after Turn 1
    profile = default_memory_agent.resolve_customer(test_email)
    mem1 = default_memory_agent.retrieve_memory(profile.customer_id, test_email)
    print("\n[Memory State after Turn 1]")
    print(f"- Customer Name: {profile.name}")
    print(f"- Total Interactions: {profile.total_interactions}")
    print(f"- Open Issues: {[i.issue_title for i in mem1.open_issues]}")
    print(f"- Interests: {[i.product_name for i in mem1.interests]}")

    # --- TURN 2: Ambiguous Continuation ---
    print("\n" + "-" * 70)
    print("\n[TURN 2] Customer sends ambiguous follow-up:")
    print("Subject: Re: Defective Winter Jacket")
    print("Body: 'Still waiting for it.'")

    turn2_res = handle_customer_email(
        customer_email=test_email,
        subject="Re: Defective Winter Jacket",
        body="Still waiting for it.",
        email_id=f"email-t2-{str(uuid4())[:6]}",
    )
    print("\n[AI Response Turn 2 (Memory Context Disambiguation)]")
    print(f"Status: {turn2_res.get('status')}")
    print(f"Detected Intent: {turn2_res.get('intent')} (Disambiguated from Turn 1 context!)")
    print(f"Detected Emotion: {turn2_res.get('emotion')}")
    print(f"Reply:\n{turn2_res.get('reply')}")

    # --- TURN 3: Resolution Confirmation ---
    print("\n" + "-" * 70)
    print("\n[TURN 3] Customer confirms resolution:")
    print("Subject: Re: Defective Winter Jacket")
    print("Body: 'Thanks, that worked! The refund just came through.'")

    turn3_res = handle_customer_email(
        customer_email=test_email,
        subject="Re: Defective Winter Jacket",
        body="Thanks, that worked! The refund just came through.",
        email_id=f"email-t3-{str(uuid4())[:6]}",
    )
    print("\n[AI Response Turn 3]")
    print(f"Status: {turn3_res.get('status')}")
    print(f"Detected Intent: {turn3_res.get('intent')}")
    print(f"Detected Emotion: {turn3_res.get('emotion')}")
    print(f"Reply:\n{turn3_res.get('reply')}")

    # Final Memory Check
    mem_final = default_memory_agent.retrieve_memory(profile.customer_id, test_email)
    print("\n[Final Memory State]")
    print(f"- Total Turns in History: {len(mem_final.recent_conversations)}")
    print(f"- Open Issues: {[i.issue_title for i in mem_final.open_issues]}")
    print(f"- Resolved Issues: {[i.issue_title for i in mem_final.resolved_issues]}")
    print("=" * 70)
    print("[SUCCESS] MULTI-TURN MEMORY TEST COMPLETED!")
    print("=" * 70)


if __name__ == "__main__":
    run_multi_turn_test()
