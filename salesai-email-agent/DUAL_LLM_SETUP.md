# Dual-LLM Setup & Testing Guide

## Quick Setup

### 1. Install Dependencies

```bash
# Install Groq package
pip install groq==0.10.0

# Or update all requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Update your `.env` file with Groq API key:

```env
# Existing (Gemini)
GEMINI_API_KEY=your_gemini_key_here

# New (Groq) 
GROQ_API_KEY=your_groq_key_here

# Optional: Customize model selection
GEMINI_MODEL=gemini-2.0-flash
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Verify Installation

```python
# Test imports
python -c "from app.nlp.dual_llm import select_best_nlp_output; print('✓ Dual-LLM module loaded')"
python -c "from app.nlp.groq_client import get_intent_and_emotion_groq; print('✓ Groq client loaded')"
python -c "from app.nlp.llm_selector import select_best_llm_output; print('✓ LLM selector loaded')"
```

## Testing

### Unit Test: Groq Client

```python
from app.nlp.groq_client import get_intent_and_emotion_groq

# Test Groq API (requires GROQ_API_KEY in .env)
result = get_intent_and_emotion_groq(
    "Where is my order? I placed it 5 days ago and haven't received it yet."
)

print(f"Groq Result:")
print(f"  Intent: {result['intent']} ({result['intent_confidence']:.2f})")
print(f"  Emotion: {result['emotion']} ({result['emotion_confidence']:.2f})")

# Expected: 
# Intent: Order Status (0.9+)
# Emotion: frustrated (0.8+)
```

### Unit Test: LLM Selector

```python
from app.nlp.llm_selector import select_best_llm_output

gemini_result = {
    "intent": "Complaint",
    "intent_confidence": 0.92,
    "emotion": "angry",
    "emotion_confidence": 0.85,
}

groq_result = {
    "intent": "Complaint", 
    "intent_confidence": 0.88,
    "emotion": "frustrated",
    "emotion_confidence": 0.80,
}

selected = select_best_llm_output(gemini_result, groq_result)

print(f"Selected Model: {selected['selected_model']}")
print(f"Gemini Score: {selected['gemini_score']:.2f}")
print(f"Groq Score: {selected['groq_score']:.2f}")

# Expected:
# Selected Model: gemini (higher score)
# Gemini Score: 0.89
# Groq Score: 0.85
```

### Unit Test: Dual-LLM Pipeline

```python
from app.nlp.dual_llm import select_best_nlp_output

test_message = "I want a refund! This product is broken and I'm very upset!"

result = select_best_nlp_output(test_message)

print(f"Dual-LLM Result:")
print(f"  Intent: {result['intent']}")
print(f"  Intent Confidence: {result['intent_confidence']:.2f}")
print(f"  Emotion: {result['emotion']}")
print(f"  Emotion Confidence: {result['emotion_confidence']:.2f}")
print(f"  Selected Model: {result['selected_model']}")

# Expected:
# Intent: Refund Request (0.9+)
# Emotion: angry (0.8+)
# Selected Model: gemini or groq (whichever scored higher)
```

### Integration Test: Full Email Pipeline

```python
from app.agents.orchestrator import handle_customer_email

result = handle_customer_email(
    customer_email="customer@example.com",
    subject="Order Status",
    body="Where is my order? I placed it 5 days ago and still haven't received it."
)

print(f"Email Processing Result:")
print(f"  Status: {result['status']}")
print(f"  Intent: {result['intent']}")
print(f"  Emotion: {result['emotion']}")
print(f"  Confidence: {result['confidence']}")
print(f"  Reply: {result['reply'][:100]}...")

# Expected:
# Status: replied or escalated
# Intent: Order Status
# Emotion: frustrated or neutral
# Confidence: > 0.5
```

### Log Monitoring

Monitor the application logs to verify dual-LLM is working:

```bash
# Run the email agent
uvicorn app.main:app --reload --log-level debug

# Look for these log patterns:
# [LLM COMPARISON] Gemini → ... Groq → ... Selected → ...
# [selected=gemini] or [selected=groq]
```

## Troubleshooting

### Issue: "GROQ_API_KEY not configured"

**Solution:**
1. Verify `.env` file contains: `GROQ_API_KEY=your_key`
2. Restart the application
3. System will fall back to Gemini-only if key not set

### Issue: "Groq library not installed"

**Solution:**
```bash
pip install groq==0.10.0
```

### Issue: "Both LLMs returning default result"

**Check:**
1. Both `GEMINI_API_KEY` and `GROQ_API_KEY` are set
2. Network connectivity is available
3. API quotas not exceeded
4. Log messages for specific error details

### Issue: "LLM comparison not appearing in logs"

**Check:**
1. Verify application is using updated orchestrator
2. Log level is set to DEBUG or INFO
3. Check for errors during import of dual_llm module
4. Restart application after updating files

## Performance Baseline

Expected response times (per email):

| Scenario | Time |
|----------|------|
| Gemini only | ~1-2s |
| Groq only | ~1-2s |
| Both (parallel) | ~2-3s |
| Both + RAG + Generation | ~5-10s |
| Total pipeline end-to-end | ~15-20s |

## Verification Checklist

- [ ] Groq package installed: `pip list | grep groq`
- [ ] Environment variables set: `echo $GROQ_API_KEY`
- [ ] Syntax validation passed: `python -m py_compile app/nlp/groq_client.py`
- [ ] Imports work: `python -c "from app.nlp.dual_llm import select_best_nlp_output"`
- [ ] Test email processed successfully
- [ ] Logs show `[LLM COMPARISON]` entries
- [ ] Selected model varies between Gemini and Groq on different inputs
- [ ] Response times acceptable (<20s per email)

## Rollback Instructions

If issues occur and you need to revert to Gemini-only:

### Option 1: Disable Groq (Keep code)
```env
# Comment out or remove Groq key
# GROQ_API_KEY=your_key_here

# Application will automatically fall back to Gemini
```

### Option 2: Revert orchestrator changes
```bash
# Restore original orchestrator.py
git checkout app/agents/orchestrator.py

# Or manually change:
# Replace: nlp_result = select_best_nlp_output(normalized_text)
# With:    intent_data = classify_intent(normalized_text)
#          emotion_data = detect_emotion(normalized_text)
```

## Next Steps

1. ✅ Install groq package
2. ✅ Set GROQ_API_KEY environment variable
3. ✅ Run unit tests above
4. ✅ Deploy to staging
5. ✅ Monitor logs for dual-LLM activity
6. ✅ Verify response times
7. ✅ Deploy to production
8. ✅ Monitor performance metrics

## Support

For issues or questions:
1. Check logs for `[LLM COMPARISON]` entries
2. Verify both API keys are valid
3. Test individual LLM functions
4. Review DUAL_LLM_IMPLEMENTATION.md for detailed architecture
