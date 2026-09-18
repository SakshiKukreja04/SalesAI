"""Live test script for Knowledge Graph and Memory integration scenarios."""

import sys
from typing import Dict, Any

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.memory.memory_retriever import retrieve_customer_memory
from app.memory.memory_formatter import format_customer_memory
from app.neo4j_retrieval import get_salesai_context, search_products_graph, format_graph_context


def run_scenario(title: str, email: str, subject: str, message: str, intent: str, emotion: str = "neutral"):
    print("=" * 80)
    print(f"SCENARIO: {title}")
    print(f"Customer Email : {email}")
    print(f"Subject        : {subject}")
    print(f"Message        : \"{message}\"")
    print(f"Intent/Emotion : {intent} ({emotion})")
    print("-" * 80)

    # 1. Direct Neo4j context check
    graph_ctx = get_salesai_context(email, intent=intent, query_text=message)
    print(f"1. Neo4j Graph Lookup:")
    print(f"   - Customer Found : {graph_ctx.get('customer_found')}")
    print(f"   - Orders Count   : {len(graph_ctx.get('orders', []))}")
    print(f"   - Matching Prods : {len(graph_ctx.get('matching_products', []))}")

    # 2. End-to-End Customer Memory Assembly
    memory = retrieve_customer_memory(
        customer_id=0,
        customer_email=email,
        intent=intent,
        emotion=emotion,
        query_text=message,
    )
    formatted = format_customer_memory(memory, current_intent=intent, current_message=message)

    print(f"\n2. Memory & Graph Context fed to LLM Generator:")
    print(formatted.full_context_text if formatted.full_context_text else "[Empty Context]")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\n🚀 RUNNING SALESAI KNOWLEDGE GRAPH LIVE SCENARIOS\n")

    # Scenario 1: Existing customer checking order status
    run_scenario(
        title="Test Case 1: Order Status & Tracking (Customer in Graph)",
        email="2023.sakshi.kukreja@ves.ac.in",
        subject="Where is my order?",
        message="Hi, can you give me an update on my order ORD-1001?",
        intent="order_status",
    )

    # Scenario 2: Product inquiry on newly synchronized product
    run_scenario(
        title="Test Case 2: Product Inquiry (NovaTech FitBand 3)",
        email="buyer@example.com",
        subject="NovaTech FitBand 3 Inquiry",
        message="Can you tell me the price, rating and features of NovaTech FitBand 3?",
        intent="product_inquiry",
    )

    # Scenario 3: Product recommendation / Air Fryer lookup
    run_scenario(
        title="Test Case 3: Category Recommendation (Air Fryers)",
        email="home_chef@example.com",
        subject="Looking for an Air Fryer",
        message="Do you have any KitchenPro Air Fryers available?",
        intent="product_recommendation",
    )

    # Scenario 4: New customer with general inquiry
    run_scenario(
        title="Test Case 4: Brand New Customer (No History)",
        email="brand_new_customer_99@gmail.com",
        subject="Return Policy Question",
        message="What is your return policy window?",
        intent="return_policy",
    )
