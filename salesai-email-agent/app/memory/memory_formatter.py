"""Customer Memory Formatting & Budgeting module.

Formats structured CustomerMemory into a compact, prioritized prompt context
without exceeding token budget or duplicating information.
"""

from __future__ import annotations

import logging
from typing import List, Set
from app.memory.memory_models import CustomerMemory, FormattedMemoryContext

LOGGER = logging.getLogger(__name__)

# Maximum character limits for context sections to prevent prompt bloating
MAX_ISSUES_CHARS = 400
MAX_HISTORY_CHARS = 700
MAX_INTERESTS_CHARS = 200
MAX_SEMANTIC_CHARS = 400
MAX_TOTAL_MEMORY_CHARS = 1600


def format_customer_memory(
    memory: CustomerMemory,
    current_intent: str = "",
    current_message: str = "",
) -> FormattedMemoryContext:
    """Format CustomerMemory into structured, prioritized text sections.
    
    Priority Order:
    1. Open issues
    2. Recent conversations (intent-relevant first)
    3. Relevant previous interactions
    4. Product interests
    5. Older history / patterns
    """
    if memory.is_empty or not memory.profile:
        return FormattedMemoryContext(full_context_text="[NEW CUSTOMER - No prior history]")

    seen_texts: Set[str] = set()

    # 1. Profile block
    prof = memory.profile
    profile_lines = [
        f"- Customer ID: {prof.customer_id}",
        f"- Total Interactions: {prof.total_interactions}",
    ]
    if prof.name and prof.name != "Valued Customer":
        profile_lines.append(f"- Name: {prof.name}")
    if prof.first_contact_at:
        profile_lines.append(f"- First Contact: {prof.first_contact_at.strftime('%Y-%m-%d')}")
    if memory.risk_level != "LOW":
        profile_lines.append(f"- Customer Risk Level: {memory.risk_level}")
    if memory.repeat_issue_detected:
        profile_lines.append(f"- Note: Repeat inquiry on '{memory.repeat_issue_intent or current_intent}'")

    profile_text = "CUSTOMER PROFILE:\n" + "\n".join(profile_lines)

    # 2. Open Issues (Priority 1)
    open_issue_lines = []
    if memory.open_issues:
        for issue in memory.open_issues[:3]:
            priority_tag = f"[{issue.priority.upper()}] " if issue.priority in {"high", "urgent"} else ""
            line = f"- {priority_tag}{issue.issue_title} (Status: {issue.status})"
            if issue.description and issue.description != issue.issue_title:
                line += f" — {issue.description[:100]}"
            if issue.created_at:
                line += f" [Reported: {issue.created_at.strftime('%Y-%m-%d')}]"
            open_issue_lines.append(line)
            seen_texts.add(issue.issue_title.lower())

    # Add recently resolved issues if intent is related to past issue
    if memory.resolved_issues and current_intent in {"refund_request", "order_status", "warranty_claim"}:
        for res in memory.resolved_issues[:2]:
            if res.issue_title.lower() not in seen_texts:
                line = f"- [RESOLVED] {res.issue_title}"
                if res.resolution_notes:
                    line += f" (Resolved: {res.resolution_notes[:80]})"
                open_issue_lines.append(line)
                seen_texts.add(res.issue_title.lower())

    issues_text = ""
    if open_issue_lines:
        joined_issues = "\n".join(open_issue_lines)
        if len(joined_issues) > MAX_ISSUES_CHARS:
            joined_issues = joined_issues[:MAX_ISSUES_CHARS] + "..."
        issues_text = "OPEN / RECENT ISSUES:\n" + joined_issues

    # 3. Recent Conversations (Priority 2, prioritized by intent relevance)
    history_lines = []
    if memory.recent_conversations:
        # Separate intent-matching conversations to put them first
        matching_convs = []
        other_convs = []
        clean_intent = (current_intent or "").strip().lower()

        for conv in memory.recent_conversations:
            if clean_intent and conv.intent.strip().lower() == clean_intent:
                matching_convs.append(conv)
            else:
                other_convs.append(conv)

        ordered_convs = (matching_convs + other_convs)[:4]

        for conv in ordered_convs:
            date_str = conv.created_at.strftime("%Y-%m-%d") if conv.created_at else "Recent"
            cust_msg = conv.customer_message or conv.normalized_message or ""
            reply_msg = conv.generated_reply or ""
            
            # Truncate turn messages for compactness
            cust_snippet = cust_msg[:120].strip()
            reply_snippet = reply_msg[:140].strip()

            line = f"- {date_str} (Intent: {conv.intent}, Emotion: {conv.emotion})"
            if cust_snippet:
                line += f"\n  Customer: \"{cust_snippet}\""
            if reply_snippet:
                line += f"\n  ShopiFyX: \"{reply_snippet}\""

            history_lines.append(line)
            seen_texts.add(cust_snippet.lower()[:30])

    history_text = ""
    if history_lines:
        joined_history = "\n".join(history_lines)
        if len(joined_history) > MAX_HISTORY_CHARS:
            joined_history = joined_history[:MAX_HISTORY_CHARS] + "..."
        history_text = "RECENT CONVERSATION HISTORY:\n" + joined_history

    # 4. Product Interests (Priority 4)
    interest_lines = []
    if memory.interests:
        for item in memory.interests[:4]:
            interest_lines.append(f"- {item.product_name} (Status: {item.interest_status})")
    
    interests_text = ""
    if interest_lines:
        joined_interests = "\n".join(interest_lines)
        if len(joined_interests) > MAX_INTERESTS_CHARS:
            joined_interests = joined_interests[:MAX_INTERESTS_CHARS] + "..."
        interests_text = "PRODUCT INTERESTS:\n" + joined_interests

    # 5. Semantic Past Interactions (Priority 3 - deduplicated)
    semantic_lines = []
    if memory.relevant_interactions:
        for inter in memory.relevant_interactions:
            msg = inter.get("message", "").strip()
            if msg and msg[:30].lower() not in seen_texts:
                intent_tag = f" (Intent: {inter.get('intent')})" if inter.get("intent") else ""
                semantic_lines.append(f"- Past Query{intent_tag}: \"{msg[:100]}\"")
                seen_texts.add(msg[:30].lower())

    semantic_text = ""
    if semantic_lines:
        joined_semantic = "\n".join(semantic_lines)
        if len(joined_semantic) > MAX_SEMANTIC_CHARS:
            joined_semantic = joined_semantic[:MAX_SEMANTIC_CHARS] + "..."
        semantic_text = "RELEVANT PREVIOUS INTERACTIONS:\n" + joined_semantic

    # 6. Previous AI Reply Patterns (if relevant and not duplicated)
    reply_pattern_lines = []
    if memory.previous_replies:
        for rep in memory.previous_replies[:2]:
            clean_rep = rep.strip()
            if clean_rep and len(clean_rep) > 20:
                reply_pattern_lines.append(f"- \"{clean_rep[:120]}\"")
    
    reply_patterns_text = ""
    if reply_pattern_lines:
        reply_patterns_text = "PREVIOUS RESPONSE PATTERNS:\n" + "\n".join(reply_pattern_lines)

    # Assemble full context respecting max memory budget
    sections = [s for s in [profile_text, issues_text, history_text, interests_text, semantic_text, reply_patterns_text] if s]
    full_context = "\n\n".join(sections)
    
    if len(full_context) > MAX_TOTAL_MEMORY_CHARS:
        # Fallback to essential sections (Profile + Issues + History)
        essential = [s for s in [profile_text, issues_text, history_text] if s]
        full_context = "\n\n".join(essential)

    return FormattedMemoryContext(
        profile_text=profile_text,
        recent_history_text=history_text,
        open_issues_text=issues_text,
        product_interests_text=interests_text,
        relevant_interactions_text=semantic_text,
        reply_patterns_text=reply_patterns_text,
        full_context_text=full_context,
    )
