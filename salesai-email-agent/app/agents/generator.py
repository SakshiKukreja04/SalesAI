"""Response generation module for SalesAI V3.

Builds customer-facing replies using selected strategy, retrieved KB policies,
customer memory, and previous replies following a strict source-of-truth hierarchy.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.prompts.response_prompt import build_response_prompt

LOGGER = logging.getLogger(__name__)


STANDARD_CLOSING = "Best regards,\nCustomer Support Team\nShopiFyX"


def _extract_json_block(text: str) -> str:
    """Extract JSON substring from generated text."""
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1]


def normalize_customer_response(response: str, customer_name: str = "") -> str:
    """Deterministically normalize and format a customer-facing support email.
    
    Enforces the single standard ShopiFyX plain-text template:
    Hi {customer_name}, / Hi,
    
    {acknowledgement}
    
    {resolution / answer}
    
    {action / next step if applicable}
    
    Best regards,
    Customer Support Team
    ShopiFyX
    """
    if not response:
        return ""

    text = str(response).strip()

    # 1. Handle JSON response payloads
    json_candidate = _extract_json_block(text)
    if json_candidate:
        try:
            parsed = json.loads(json_candidate)
            if isinstance(parsed, dict):
                candidate = parsed.get("reply") or parsed.get("response") or parsed.get("body") or parsed.get("text")
                if isinstance(candidate, str) and candidate.strip():
                    text = candidate.strip()
        except Exception:
            pass

    # 2. Strip code blocks and inline backticks
    text = re.sub(r"```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)```", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # 3. Strip accidental conversational prefixes
    preamble_patterns = [
        r"^(?:here(?:\s+is|\'s)\s+(?:the|your|a)?\s*(?:email|response|reply|message|draft)?\s*:?\s*)",
        r"^(?:sure,?\s*(?:here(?:\s+is|\'s)\s*(?:the|a)?\s*(?:email|response|reply|draft)?)?\s*:?\s*)",
        r"^(?:email\s*body\s*:?\s*)",
        r"^(?:email\s*:?\s*)",
        r"^(?:response\s*:?\s*)",
        r"^(?:subject\s*:[^\n]+\n+)",
    ]
    for pattern in preamble_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    # 4. Remove prompt traces & metadata line by line
    header_pattern = re.compile(
        r"^(?:[\*\#\_]{0,3})\s*(?:Next Steps|Action Required|What to do next|Refund Policy|Shipping Policy|Important|Note|Details|Instructions|Summary|Refund Status|Order Status|Exchange Status)\s*(?:[\:\*\#\_]{0,4})\s*$",
        re.IGNORECASE,
    )

    filtered_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            filtered_lines.append("")
            continue

        lower = line.lower()
        if any(line.startswith(prefix) for prefix in [
            "*   User Query:", "*   Role:", "*   Constraint", "*   Strategy:", "*   Intent:",
            "*   Emotion:", "*   Tone:", "*   Format:", "*Drafting Paragraph", "*Self-Correction:",
            "*Final", "*Revised", "*Wait", "*Check", "*   Does it", "*   Acknowledge",
            "*   Direct answer:", "*   Actionable", "*   How to contact:",
            "*   *customer_support.md*:", "*   *payment_policy.md*:", "*   *ai_response_guidelines.md*:",
            "*   *shopifyx_overview.md*:", "[Direct Answer", "[Next Steps", "[Action Required"
        ]):
            continue

        if lower.startswith("self-correction") or "self-correction during drafting" in lower:
            continue
        if "direct answer" in lower and ("empathy" in lower or "acknowledgment" in lower):
            continue
        if "next steps" in lower and "additional info" in lower:
            continue
        if lower.startswith("confidence score") or lower.startswith("intent:") or lower.startswith("emotion:"):
            continue
        if lower.startswith("---") or lower.startswith("===") or lower.startswith("___"):
            continue
        if lower.startswith("next steps: none") or lower.startswith("next step: none"):
            continue
        if header_pattern.match(line):
            continue

        filtered_lines.append(line)

    text = "\n".join(filtered_lines).strip()

    # 5. Strip markdown headers (# Header)
    text = re.sub(r"^#{1,6}\s*(.+)$", r"\1", text, flags=re.MULTILINE)

    # 6. Strip bullet points and list counters
    text = re.sub(r"^\s*[-*•+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # 7. Strip bold and italic markdown markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)

    # 8. Strip tables and decorative characters
    text = re.sub(r"^\s*\|.*\|\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)

    # 9. Strip ALL leading greetings and blank lines at top
    lines = text.splitlines()
    start_idx = 0
    while start_idx < len(lines):
        clean_line = lines[start_idx].strip()
        if not clean_line:
            start_idx += 1
            continue
        if re.match(r"^(?:hi|hello|dear|hey)\b.*,$", clean_line, re.IGNORECASE) or (
            re.match(r"^(?:hi|hello|dear|hey)\b.*$", clean_line, re.IGNORECASE) and len(clean_line.split()) <= 4
        ):
            start_idx += 1
            continue
        break

    text = "\n".join(lines[start_idx:]).strip()

    # 10. Strip ALL trailing sign-offs from bottom
    closing_patterns = [
        r"\n\s*(?:best regards|warm regards|kind regards|regards|sincerely|cheers|thanks and regards|thanks & regards|thanks|thank you),?\s*\n\s*(?:customer support team|shopifyx support team|support team|shopifyx team|shopifyx)?\s*\n?\s*(?:shopifyx)?\s*$",
        r"\n\s*(?:best regards|warm regards|kind regards|regards|sincerely|cheers),?\s*$",
        r"\n\s*(?:customer support team|shopifyx support team|support team|shopifyx team|shopifyx)\s*$",
    ]
    changed = True
    while changed:
        changed = False
        for pattern in closing_patterns:
            new_text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
            if new_text != text:
                text = new_text
                changed = True

    # 11. Normalize paragraphs
    raw_paras = re.split(r"\n\s*\n", text)
    clean_paras = []
    for p in raw_paras:
        lines_in_p = [l.strip() for l in p.splitlines() if l.strip()]
        p_clean = " ".join(lines_in_p).strip()
        p_clean = re.sub(r"\*\*|\*|__", "", p_clean).strip()
        if p_clean.startswith('"') and p_clean.endswith('"'):
            p_clean = p_clean[1:-1].strip()
        if p_clean.startswith("'") and p_clean.endswith("'"):
            p_clean = p_clean[1:-1].strip()
        if p_clean:
            clean_paras.append(p_clean)

    body_content = "\n\n".join(clean_paras).strip()
    if not body_content:
        body_content = "Thank you for contacting ShopiFyX. We have received your request and our support team will assist you shortly."

    # 12. Build greeting
    greeting_name = (customer_name or "").strip()
    if greeting_name and greeting_name.lower() not in {"valued customer", "customer", "support", "shopifyx", "user", "none", "null"}:
        first_name = greeting_name.split()[0].title()
        greeting = f"Hi {first_name},"
    else:
        greeting = "Hi,"

    return f"{greeting}\n\n{body_content}\n\n{STANDARD_CLOSING}"


def sanitize_customer_reply(raw_reply: str, customer_name: str = "") -> str:
    """Strip prompt traces, analysis text, and metadata, formatting into standard plain-text template."""
    return normalize_customer_response(raw_reply, customer_name=customer_name)


def _email_style_instructions(strategy: str, intent: str, emotion: str) -> str:
    """Return specific formatting and tone instructions based on strategy and emotion."""
    rules = [
        "- Answer the customer's question directly in the opening paragraph.",
        "- Follow internal ShopiFyX policy facts strictly.",
    ]

    if emotion in {"angry", "frustrated", "urgent", "disappointed", "worried"}:
        rules.append("- Acknowledge the customer's inconvenience with sincere empathy.")
    if strategy == "policy_focused":
        rules.append("- Provide clear step-by-step instructions.")
    if strategy == "tracking_focused":
        rules.append("- Give concrete delivery expectations based strictly on policy.")

    return "\n".join(rules)


def _extract_timeline_facts(context_docs: List[str]) -> List[str]:
    """Extract policy timeline details from context chunks."""
    facts = []
    combined = "\n".join(context_docs)
    for line in combined.splitlines():
        clean = line.strip()
        if any(kw in clean.lower() for kw in ["day", "hour", "business day", "within", "timeline"]):
            facts.append(clean)
    return facts[:3]


def _model_candidates() -> List[str]:
    """Model candidates for generation."""
    configured = getattr(settings, "gemini_model", None) or "gemini-2.0-flash"
    return [configured, "gemini-2.0-flash", "gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-flash"]


def _gemini_generate(prompt: str) -> str:
    """Generate content using Gemini with graceful model fallback."""
    api_key = getattr(settings, "gemini_api_key", None) or ""
    if not api_key:
        return ""

    try:
        try:
            # pyrefly: ignore [missing-import]
            import google.generativeai as genai
            genai.configure(api_key=api_key)

            for model_name in _model_candidates():
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    text = (getattr(response, "text", "") or "").strip()
                    if text:
                        return text
                except Exception:
                    continue
        except ImportError:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                for model_name in _model_candidates():
                    try:
                        response = client.models.generate_content(model=model_name, contents=prompt)
                        text = (getattr(response, "text", "") or "").strip()
                        if text:
                            return text
                    except Exception:
                        continue
            except ImportError:
                LOGGER.debug("No Google GenAI package available")

        return ""
    except Exception as exc:
        LOGGER.warning("Gemini generation client error: %s", exc)
        return ""


def _groq_generate(prompt: str) -> str:
    """Generate reply via Groq LLM as fallback."""
    api_key = os.getenv("GROQ_API_KEY", "").strip() or getattr(settings, "groq_api_key", "")
    if not api_key:
        return ""
    try:
        from groq import Groq
        from app.nlp.groq_client import _model_candidates_from_env
        client = Groq(api_key=api_key)
        for model_name in _model_candidates_from_env():
            try:
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                    temperature=0.2,
                    max_tokens=600,
                )
                text = (chat_completion.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as e:
                LOGGER.debug("Groq generation failed on %s: %s", model_name, e)
                continue
        return ""
    except Exception as exc:
        LOGGER.warning("Groq generation error: %s", exc)
        return ""


def _fallback_reply(
    strategy: str,
    intent: str,
    emotion: str,
    context_docs: List[str],
    customer_memory: Optional[Any] = None,
) -> str:
    """Build a deterministic policy-grounded reply when LLM is unavailable."""
    context_hint = context_docs[0] if context_docs else ""
    clean_intent = (intent or "").strip().lower()

    # Empathy prefix based on detected emotion
    empathy_prefix = ""
    if emotion in {"angry", "frustrated", "urgent", "disappointed", "worried"}:
        empathy_prefix = "I truly understand your frustration and apologize for the inconvenience. "

    # Check for active open issues in memory
    open_issue_acknowledgment = ""
    if customer_memory:
        open_issues = getattr(customer_memory, "open_issues", [])
        if open_issues:
            top_issue = open_issues[0]
            open_issue_acknowledgment = f"Regarding your open issue on '{top_issue.issue_title}', our team is actively tracking this. "

    base = "Thank you for reaching out. We are reviewing your inquiry and will assist you shortly."

    if any(kw in clean_intent for kw in ["refund", "money back"]) and context_docs:
        timeline_facts = _extract_timeline_facts(context_docs)
        if timeline_facts:
            details = ". ".join(timeline_facts)
            base = f"Thank you for contacting us regarding your refund request. {details}."
        else:
            base = "Thank you for contacting us regarding your refund request. According to our policy, eligible refunds are processed to your original payment method."
    elif any(kw in clean_intent for kw in ["track", "order", "status", "delivery", "shipping"]) and context_docs:
        base = "Thank you for checking on your order status. We are tracking your package to ensure safe delivery."
    elif any(kw in clean_intent for kw in ["product", "inquiry", "material", "recommendation", "catalog", "specs", "question", "build"]) and context_docs:
        product_lines = []
        product_title = ""
        for doc in context_docs:
            for line in doc.splitlines():
                clean_l = line.strip()
                if (clean_l.startswith("P0") or "—" in clean_l) and not product_title:
                    product_title = clean_l
                elif ":" in clean_l:
                    key, val = clean_l.split(":", 1)
                    if key.strip().lower() in {"material", "material/build", "build", "price", "features", "category", "colors", "sizes"} and val.strip():
                        product_lines.append(f"{key.strip()}: {val.strip()}")
        if product_lines:
            header = f"Regarding {product_title}, " if product_title else "According to our product catalog, "
            base = f"{header}here are the details from our catalog: {'. '.join(product_lines[:4])}."
        else:
            base = "Thank you for inquiring about our products. Please let us know if you need specific sizing or feature recommendations."

    return (empathy_prefix + open_issue_acknowledgment + base).strip()


def _format_reply_sections(reply_text: str, intent: str = "") -> str:
    """Format reply with clean paragraphs, removing document headers and compacting lists."""
    if not reply_text or not reply_text.strip():
        return reply_text

    text = reply_text.strip()

    # Strip top-level raw document/outline headers (e.g. "**ShopiFyX Warranty Policy (Summary)**")
    lines = text.splitlines()
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^\*{0,2}#*\s*(ShopiFyX|Warranty|Return|Refund|Payment|Shipping|Support)\s+.*(Policy|Summary|Overview)\*{0,2}:?$", stripped, re.IGNORECASE):
            continue
        filtered_lines.append(line)

    text = "\n".join(filtered_lines).strip()

    # Build clean paragraphs
    paragraphs = []
    current_para = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_para:
                paragraphs.append("\n".join(current_para))
                current_para = []
            continue
        current_para.append(line)

    if current_para:
        paragraphs.append("\n".join(current_para))

    result = "\n\n".join(paragraphs).strip()
    # Compact spaced-out bullet and numbered lists
    result = re.sub(r'(\n(?:[-*•]|\d+\.)\s[^\n]+)\n\n(?=(?:[-*•]|\d+\.)\s)', r'\1\n', result)
    return result.strip()


def generate_reply_structured(
    current_message: str = "",
    intent: str = "general_support",
    intent_confidence: float = 0.80,
    emotion: str = "neutral",
    emotion_confidence: float = 0.60,
    strategy: str = "general_helpful",
    kb_context: Optional[List[str]] = None,
    customer_memory: Optional[Any] = None,
    reply_memory: Optional[List[str]] = None,
    strict_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate structured response JSON matching the V3 system contract."""
    chunks = kb_context or []
    replies = reply_memory or []

    # Memory formatting
    mem_context_str = ""
    if customer_memory is not None:
        try:
            from app.memory.memory_formatter import format_customer_memory
            formatted = format_customer_memory(customer_memory, current_intent=intent, current_message=current_message)
            mem_context_str = formatted.full_context_text
        except Exception:
            mem_context_str = ""

    prompt = strict_prompt or build_response_prompt(
        customer_message=current_message,
        intent=intent,
        intent_confidence=intent_confidence,
        emotion=emotion,
        emotion_intensity=emotion_confidence,
        context_chunks=chunks,
        history="\n\n".join(replies) if replies else "",
        customer_memory_context=mem_context_str,
        strategy=strategy,
    )

    cust_name = ""
    if customer_memory is not None:
        prof = getattr(customer_memory, "profile", None)
        if prof and getattr(prof, "name", None):
            cust_name = prof.name or ""

    generated = _gemini_generate(prompt) or _groq_generate(prompt)
    if generated:
        json_str = _extract_json_block(generated)
        if json_str:
            try:
                data = json.loads(json_str)
                reply_text = data.get("reply", "")
                if reply_text and isinstance(reply_text, str) and reply_text.strip():
                    cleaned_reply = normalize_customer_response(reply_text, customer_name=cust_name)
                    return {
                        "reply": cleaned_reply,
                        "confidence": float(data.get("confidence", 0.90)),
                        "requires_escalation": bool(data.get("requires_escalation", False)),
                        "escalation_reason": data.get("escalation_reason"),
                    }
            except Exception:
                pass

        cleaned = normalize_customer_response(generated, customer_name=cust_name)
        if cleaned:
            return {
                "reply": cleaned,
                "confidence": 0.88,
                "requires_escalation": False,
                "escalation_reason": None,
            }

    # Fallback
    fallback = _fallback_reply(
        strategy=strategy,
        intent=intent,
        emotion=emotion,
        context_docs=chunks,
        customer_memory=customer_memory,
    )
    return {
        "reply": normalize_customer_response(fallback, customer_name=cust_name),
        "confidence": 0.70,
        "requires_escalation": False,
        "escalation_reason": None,
    }


def generate_reply(
    current_message: str = "",
    intent: str = "general_support",
    emotion: str = "neutral",
    strategy: str = "general_helpful",
    kb_context: Optional[List[str]] = None,
    customer_memory: Optional[Any] = None,
    reply_memory: Optional[List[str]] = None,
    # Compatibility aliases
    context_docs: Optional[List[str]] = None,
    similar_user_docs: Optional[List[str]] = None,
    customer_text: str = "",
    strict_prompt: Optional[str] = None,
    intent_confidence: Optional[float] = None,
    emotion_intensity: Optional[float] = None,
    customer_memory_context: str = "",
) -> str:
    """Generate a policy-grounded reply string, matching all caller contracts."""
    msg = current_message or customer_text
    chunks = kb_context if kb_context is not None else (context_docs or [])
    replies = reply_memory if reply_memory is not None else (similar_user_docs or [])
    int_conf = float(intent_confidence if intent_confidence is not None else 0.80)
    emo_conf = float(emotion_intensity if emotion_intensity is not None else 0.60)

    structured = generate_reply_structured(
        current_message=msg,
        intent=intent,
        intent_confidence=int_conf,
        emotion=emotion,
        emotion_confidence=emo_conf,
        strategy=strategy,
        kb_context=chunks,
        customer_memory=customer_memory,
        reply_memory=replies,
        strict_prompt=strict_prompt,
    )
    return structured["reply"]
