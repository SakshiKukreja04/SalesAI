# Dual-LLM Intent & Emotion Detection Implementation

## Overview

This document describes the dual-LLM implementation that adds Groq API as a second LLM provider alongside Gemini for intent classification and emotion detection in the SalesAI email agent system.

## Architecture

### Components

#### 1. **app/nlp/groq_client.py** (NEW)
- Groq API client wrapper
- Function: `get_intent_and_emotion_groq(text: str) -> Dict`
- Returns combined result with float confidence scores (0.0-1.0)
- Uses deterministic prompting (temperature=0)
- Graceful fallback on API failures

**Key features:**
- Validates Groq API key from environment
- Combines intent + emotion in single API call
- Converts confidence strings (High/Medium/Low) to floats (0.9/0.7/0.5)
- Returns fallback result with neutral defaults if API unavailable

#### 2. **app/nlp/llm_selector.py** (NEW)
- Comparator module for selecting best LLM output
- Function: `select_best_llm_output(gemini_result, groq_result) -> Dict`
- Scoring formula: `score = (intent_confidence * 0.6) + (emotion_confidence * 0.4)`
  - 60% weight on intent accuracy
  - 40% weight on emotion accuracy
- Returns result with highest combined score
- Includes metadata: selected_model, gemini_score, groq_score

#### 3. **app/nlp/dual_llm.py** (NEW)
- Unified dual-LLM interface
- Functions:
  - `detect_intent_emotion_gemini(text)` - Combines Gemini intent + emotion
  - `select_best_nlp_output(text)` - Main entry point for dual-LLM pipeline
- Runs both APIs in parallel using threading (non-blocking)
- Implements fail-safe handling:
  - If both succeed → use selector
  - If one fails → use other
  - If both fail → return default (Inquiry, neutral)
- Includes comprehensive logging

#### 4. **app/nlp/intent.py** (UPDATED)
- Added `detect_intent_emotion_gemini(text)` function
- Returns standardized format with float confidence
- Maintains backward compatibility with existing `classify_intent()` function
- Added `_confidence_to_float()` helper to convert string confidence to float

#### 5. **app/nlp/emotion.py** (UPDATED)
- Added `detect_intent_emotion_gemini(text)` function  
- Returns standardized format with float confidence
- Maintains backward compatibility with existing `detect_emotion()` function
- Added `_confidence_to_float()` helper

#### 6. **app/agents/orchestrator.py** (UPDATED)
- Modified step 2-3 to use `select_best_nlp_output()` instead of separate calls
- Now receives combined result with selected_model metadata
- Updates logging to include selected_model information
- Confidence values now floats instead of strings
- Maintains full backward compatibility with existing pipeline

#### 7. **app/config.py** (UPDATED)
- Added GROQ_API_KEY configuration
- Added GROQ_MODEL configuration (defaults to "mixtral-8x7b-32768")

#### 8. **requirements.txt** (UPDATED)
- Added `groq==0.10.0` package

### Return Format Standardization

All dual-LLM functions return:
```python
{
    "intent": str,
    "intent_confidence": float,  # 0.0-1.0
    "emotion": str,
    "emotion_confidence": float,  # 0.0-1.0
    "selected_model": "gemini" | "groq" | "default" | "error",  # selector functions only
    "gemini_score": float,  # selector functions only
    "groq_score": float,  # selector functions only
}
```

## Execution Flow

### Email Processing Pipeline (Unchanged)

```
Email → Preprocess → NLP (Dual-LLM) → RAG → Strategy → Generate → Validate → Send/Escalate → Log
```

### Dual-LLM Processing (New)

```
Raw Text
   ↓
[Parallel Execution - Threading]
   ├─→ Gemini API Call
   │     ├─ Intent Classification
   │     └─ Emotion Detection
   │
   └─→ Groq API Call
       ├─ Intent Classification  
       └─ Emotion Detection
   ↓
[Result Collection with 15s timeout per thread]
   ├─ If both succeed → Compare scores
   ├─ If one fails → Use successful one
   └─ If both fail → Return default
   ↓
[Score Comparison]
   score = (intent_conf * 0.6) + (emotion_conf * 0.4)
   ↓
[Select Winner]
   Higher score → Use selected result
   ↓
Return combined result with metadata
```

## Environment Variables

Required:
```
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
```

Optional:
```
GEMINI_MODEL=gemini-2.0-flash        # Defaults to gemini-1.5-flash
GROQ_MODEL=llama-3.3-70b-versatile   # Defaults to llama-3.3-70b-versatile
```

## Logging

### LLM Selection Logging
```
[LLM COMPARISON] 
Gemini → intent=Complaint (0.92), emotion=frustrated (0.85), score=0.89 |
Groq   → intent=Complaint (0.88), emotion=frustrated (0.80), score=0.86
Selected → Gemini
```

### Orchestration Logging
```
[REQ_ID] NLP Results: intent=Complaint (0.92), emotion=frustrated (0.85) [selected=gemini]
```

## Error Handling & Fallbacks

| Scenario | Action |
|----------|--------|
| Both LLMs succeed | Use score-based selector |
| Gemini fails | Use Groq result with warning |
| Groq fails | Use Gemini result with warning |
| Both fail | Return default (Inquiry, neutral) with error log |
| API key missing | Use fallback without API call |
| Network timeout | Handled by individual LLM with retry |
| Invalid response | Use fallback heuristic |

## Performance Considerations

### Parallel Execution
- Both API calls run concurrently using Python threading
- 15-second timeout per API call
- Total latency: ~15 seconds worst-case (not doubled)
- Typical latency: 2-4 seconds (both APIs respond quickly)

### Backward Compatibility
- Existing `classify_intent()` and `detect_emotion()` functions unchanged
- New dual-LLM functions used only in orchestrator
- RAG, ChromaDB, email sending, Supabase logging unmodified
- Memory system unchanged

### No Breaking Changes
- Function signatures of external interfaces preserved
- Return format compatible with downstream consumers
- Configuration fields optional with sensible defaults

## Files Modified/Created

### New Files:
- `app/nlp/groq_client.py` - 180 lines
- `app/nlp/llm_selector.py` - 70 lines  
- `app/nlp/dual_llm.py` - 160 lines

### Modified Files:
- `app/nlp/intent.py` - Added 50 lines (new functions)
- `app/nlp/emotion.py` - Added 50 lines (new functions)
- `app/agents/orchestrator.py` - Updated 20 lines (orchestration logic)
- `app/config.py` - Added 2 lines (GROQ config)
- `requirements.txt` - Added 1 line (groq package)

## Testing Recommendations

### Unit Tests
```python
# Test individual LLM functions
from app.nlp.groq_client import get_intent_and_emotion_groq
from app.nlp.intent import detect_intent_emotion_gemini
from app.nlp.emotion import detect_intent_emotion_gemini

# Test selector
from app.nlp.llm_selector import select_best_llm_output

# Test dual-LLM pipeline
from app.nlp.dual_llm import select_best_nlp_output
```

### Integration Tests
```python
# Mock email processing
from app.agents.orchestrator import handle_customer_email

# Test with sample emails
result = handle_customer_email(
    customer_email="test@example.com",
    subject="Order Issue",
    body="My order hasn't arrived yet"
)

# Verify result contains selected_model
assert "selected_model" in result
assert result["intent"] in ["Complaint", "Inquiry", ...]
assert 0.0 <= result["confidence"] <= 1.0
```

### Manual Testing
1. Send test email to system
2. Check orchestrator logs for `[LLM COMPARISON]` output
3. Verify selected model in database logs
4. Monitor response times (should not double from original)

## Monitoring

### Key Metrics
- Response time per email (should remain ~2-5 seconds)
- API error rates per provider
- Model selection distribution (how often Gemini vs Groq wins)
- Confidence score trends

### Logging Checkpoint
```
# Look for these in logs:
[LLM COMPARISON]  # Indicates dual-LLM execution
selected_model=  # Shows which model was selected
gemini_score=    # Comparison scores
groq_score=      # Comparison scores
```

## Migration Notes

### For Existing Deployments
1. Install new dependency: `pip install groq==0.10.0`
2. Add environment variable: `GROQ_API_KEY=your_key`
3. Restart the application - changes are transparent
4. Monitor logs during first deployment

### Rollback Plan
If issues occur:
1. Remove `GROQ_API_KEY` environment variable
2. System falls back to Gemini-only (see error handling)
3. Or modify orchestrator to use original `classify_intent()` and `detect_emotion()`

## FAQ

**Q: Will dual-LLM double response time?**
A: No. APIs run in parallel with threading. Total time ≈ single API call time (~2-4s) with small overhead.

**Q: What if Groq API is down?**
A: System gracefully falls back to Gemini-only with warning log.

**Q: How are scores calculated?**
A: `score = (intent_confidence × 0.6) + (emotion_confidence × 0.4)` - intent weighted 60%, emotion 40%.

**Q: Can I change the weight formula?**
A: Yes, modify the scoring in `llm_selector.py` line ~39.

**Q: Does this change the RAG retrieval?**
A: No. Intent/emotion are passed to RAG unchanged. RAG logic is untouched.

**Q: Will old code still work?**
A: Yes. `classify_intent()` and `detect_emotion()` functions still exist and work as before.

## Next Steps

1. Install Groq package: `pip install groq`
2. Set `GROQ_API_KEY` in environment
3. Deploy and monitor logs for `[LLM COMPARISON]` entries
4. Verify response times remain acceptable
5. Monitor model selection distribution in logs
