"""Response-generation and email-decision prompt builders for SalesAI V3."""

from typing import Any, List, Optional


def build_response_prompt(
    customer_message: str,
    intent: str,
    intent_confidence: float,
    emotion: str,
    emotion_intensity: float,
    context_chunks: List[str],
    history: str = "",
    customer_memory_context: str = "",
    strategy: str = "",
) -> str:
    """Build the grounded V3 response prompt with strict source-of-truth hierarchy and JSON return contract."""
    kb_block = "\n\n".join(context_chunks) if context_chunks else "No relevant ShopiFyX policy context found."
    history_block = history.strip()
    history_text = f"\n4. PREVIOUS AI REPLIES & CONVERSATION HISTORY:\n{history_block}\n" if history_block else ""
    
    memory_block = customer_memory_context.strip()
    memory_text = f"\n3. CUSTOMER MEMORY CONTEXT:\n{memory_block}\n" if memory_block else ""
    strategy_text = f"\nSELECTED RESPONSE STRATEGY: {strategy}\n" if strategy else ""

    return (
        "You are the ShopiFyX Customer Support Response Generator.\n\n"
        "Your task is to generate a professional, accurate, empathetic, and policy-grounded email response.\n\n"
        "SOURCE OF TRUTH HIERARCHY (in order of strict priority):\n"
        "1. CURRENT CUSTOMER MESSAGE (Primary request and emotional state)\n"
        "2. CURRENT SHOPIFYX KNOWLEDGE BASE AND POLICIES (Strict factual authority - overrides older conversation statements)\n"
        "3. CUSTOMER MEMORY (Provides historical context, open issues, preferences, not policy)\n"
        "4. PREVIOUS AI REPLIES (Provides tone/pattern context; do NOT blindly duplicate)\n\n"
        "1. CURRENT CUSTOMER MESSAGE:\n"
        f"{customer_message}\n\n"
        f"DETECTED INTENT: {intent} (Confidence: {intent_confidence:.2f})\n"
        f"DETECTED EMOTION: {emotion} (Intensity: {emotion_intensity:.2f})\n"
        f"{strategy_text}\n"
        "2. CURRENT SHOPIFYX KNOWLEDGE BASE & POLICIES:\n"
        f"{kb_block}\n"
        f"{memory_text}"
        f"{history_text}\n"
        "STRICT GENERATION RULES:\n"
        "1. ACCURACY & POLICY AUTHORITY:\n"
        "   - Never invent policy information, prices, timelines, order details, or commitments.\n"
        "   - Knowledge-base policy ALWAYS has priority over customer memory.\n"
        "   - Current ShopiFyX KB policy ALWAYS overrides older conversation statements or memory.\n"
        "   - Customer memory provides context, NOT policy overrides.\n"
        "   - Never claim an action (e.g. refund processed, replacement shipped) was completed unless supported by available system data.\n\n"
        "2. CUSTOMER MEMORY & CONTINUITY:\n"
        "   - Use customer memory to maintain continuity and avoid repetitive questions.\n"
        "   - Avoid asking for information the customer has already provided in prior interactions.\n"
        "   - If the customer already provided details (e.g. order number, item size), do not ask for them again.\n"
        "   - If there is an active open issue, acknowledge it naturally when relevant.\n"
        "   - Do NOT reopen issues that are already resolved unless the customer explicitly reports a new problem.\n"
        "   - Never expose internal/sensitive memory details, customer profile metadata, database IDs, or algorithms.\n\n"
        "3. EMOTION & TONE ADAPTATION:\n"
        "   - Adapt tone to the detected emotion (angry/frustrated -> calm, deeply empathetic, solution-focused; happy/satisfied -> warm, appreciative; urgent -> direct and actionable).\n\n"
        "4. BOUNDARIES & ESCALATION:\n"
        "   - If required information is unavailable in the KB, clearly state what the customer needs to provide.\n"
        "   - If the issue requires human intervention or policy exception, set 'requires_escalation': true.\n"
        "   - Do not mention 'memory', 'database', 'customer profile', 'LLM', 'AI', 'RAG', prompts, or internal systems.\n"
        "   - Never expose confidence scores or internal documents.\n\n"
        "5. EMAIL TEMPLATE & STRICT PLAIN-TEXT FORMATTING RULES:\n"
        "   - You are generating a customer-facing ShopiFyX support email.\n"
        "   - The output must be pure PLAIN TEXT.\n"
        "   - Do NOT use Markdown formatting of any kind (NO bold **, NO italics *, NO headings #, NO bullet points -, *, •, NO numbered lists 1., 2., NO tables, NO emojis, NO HTML, NO code blocks, NO decorative lines ---).\n"
        "   - Write naturally and professionally in clean, cohesive paragraphs separated by blank lines.\n"
        "   - Follow this standard structure:\n"
        "     Hi {customer_name},\n\n"
        "     {acknowledgement or brief empathy sentence}\n\n"
        "     {main response directly addressing the request using verified facts}\n\n"
        "     {action, next step, or timeline if applicable}\n\n"
        "     Best regards,\n"
        "     Customer Support Team\n"
        "     ShopiFyX\n\n"
        "   - If no customer name is provided, start with 'Hi,'\n"
        "   - Do NOT add artificial or empty sections like 'Next Steps: None'. If no timeline/action is needed, omit it.\n"
        "   - Do NOT add explanations outside the email body.\n"
        "   - Do NOT mention internal agents, memory, RAG, confidence scores, prompts, or internal tools.\n\n"
        "OUTPUT FORMAT:\n"
        "Return ONLY valid JSON matching this exact structure with NO surrounding markdown or extra text:\n"
        "{\n"
        '  "reply": "<complete customer-facing plain-text email>",\n'
        '  "confidence": 0.0,\n'
        '  "requires_escalation": false,\n'
        '  "escalation_reason": null\n'
        "}"
    )


def build_final_email_prompt(customer_name: str, original_message: str, intent: str, emotion: str, approved_response: str) -> str:
    """Create the final customer-facing email prompt."""
    return (
        "You are the final ShopiFyX Customer Support Email Generator.\n"
        "Create a professional, plain-text customer-facing email from the approved response.\n"
        "Do not introduce new facts, make promises, or modify policy details.\n"
        "Do not use markdown formatting, bold text, bullets, numbered lists, or headings.\n"
        "Follow the standard structure:\n"
        "Hi {customer_name},\n\n"
        "{acknowledgement}\n\n"
        "{resolution / answer}\n\n"
        "Best regards,\n"
        "Customer Support Team\n"
        "ShopiFyX\n\n"
        f"Customer name: {customer_name}\n"
        f"Original customer message: {original_message}\n"
        f"Detected intent: {intent}\n"
        f"Detected emotion: {emotion}\n"
        f"Approved response: {approved_response}\n\n"
        "Return JSON only with: {\"subject\": \"...\", \"body\": \"...\"}"
    )


def build_email_decision_prompt(
    customer_message: str,
    intent: str,
    intent_confidence: float,
    emotion: str,
    emotion_intensity: float,
    generated_response: str,
    retrieved_context: List[str],
    customer_risk_level: str = "LOW",
) -> str:
    """Build the backend email decision prompt described in the V3 workflow."""
    kb_block = "\n\n".join(retrieved_context) if retrieved_context else "No relevant KB context found."
    return (
        "You are the Email Decision module of ShopiFyX SalesAI.\n\n"
        "Determine whether the generated response is safe and appropriate\n"
        "to send to the customer automatically.\n\n"
        "INPUT:\n\n"
        "Customer message:\n"
        + customer_message + "\n\n"
        + "Intent:\n"
        + intent + "\n\n"
        + "Intent confidence:\n"
        + str(intent_confidence) + "\n\n"
        + "Emotion:\n"
        + emotion + "\n\n"
        + "Emotion intensity:\n"
        + str(emotion_intensity) + "\n\n"
        + "Customer Risk Level:\n"
        + customer_risk_level + "\n\n"
        + "Generated response:\n"
        + generated_response + "\n\n"
        + "Retrieved KB:\n"
        + kb_block + "\n\n"
        + "Rules:\n\n"
        + "AUTO_SEND when:\n"
        + "- The response is directly supported by the KB.\n"
        + "- Intent confidence >= 0.80.\n"
        + "- Customer Risk Level is LOW or MEDIUM.\n"
        + "- No important information is missing.\n"
        + "- No exceptional/manual intervention is required.\n"
        + "- The response does not make an unsupported commitment.\n\n"
        + "HUMAN_REVIEW when:\n"
        + "- Intent confidence < 0.80.\n"
        + "- Customer Risk Level is HIGH or ESCALATE_IMMEDIATELY.\n"
        + "- The customer has a complex or ambiguous request.\n"
        + "- The customer is highly angry or repeatedly dissatisfied.\n"
        + "- The response requires a decision not defined in the KB.\n"
        + "- The response involves an exception to policy.\n"
        + "- The model is uncertain about the correct action.\n\n"
        + "DO_NOT_SEND when:\n"
        + "- The response contains unsupported claims.\n"
        + "- Required information is missing.\n"
        + "- The response could mislead the customer.\n"
        + "- The message is unsafe or inappropriate to send.\n\n"
        + "Return ONLY valid JSON:\n\n"
        + "{\n"
        + '  "decision": "AUTO_SEND | HUMAN_REVIEW | DO_NOT_SEND",\n'
        + '  "confidence": 0.0,\n'
        + '  "reason": "<short reason>",\n'
        + '  "requires_human": true\n'
        + "}"
    )
