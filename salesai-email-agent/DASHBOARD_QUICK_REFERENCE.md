# SalesAI Admin Dashboard - Quick Reference

## 🚀 Quick Start (Copy & Paste)

### Terminal 1: Start Backend
```bash
cd d:\SalesAI\salesai-email-agent
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2: Start Frontend
```bash
cd d:\SalesAI\salesai-email-agent\frontend
npm install  # First time only
npm run dev
```

### Terminal 3: Open Dashboard
Navigate to: **http://localhost:5173**

---

## 📊 Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│ SalesAI Admin | Total Emails: 42 | [Refresh Button] │  ← Navbar
├─────────────────────────────────────────────────────┤
│ ┌────┬────────┬────────┬────────┬──────┬──────┬────┐ │
│ │ From │ Subject │ Intent │ Emotion │ Conf │ Status │ View │  ← Table
│ ├────┼────────┼────────┼────────┼──────┼──────┼────┤ │
│ │... │... │ ... │ 😠 │ 82% │ ✅ Replied│ [V] │ │
│ │... │... │ ... │ 😐 │ 45% │ 🔴 Failed │ [V] │ │
│ └────┴────────┴────────┴────────┴──────┴──────┴────┘ │
└─────────────────────────────────────────────────────┘
         ↓ Click [V]
   ┌─────────────────────┐
   │ From: customer@... │
   │ Subject: Order...  │
   │ Message: ...       │
   │ Reply: ...         │
   │ [Close]            │
   └─────────────────────┘
```

---

## 🎨 Color Guide

### Status Badges
| Status | Color | Meaning |
|--------|-------|---------|
| Replied | 🟢 Green | Email answered by AI |
| Escalated | 🔴 Red | Forwarded to human support |
| Failed | ⚪ Gray | Processing failed |

### Emotion Badges
| Emotion | Color | Icon |
|---------|-------|------|
| Happy | 🟢 Green | 😊 |
| Neutral | 🟡 Yellow | 😐 |
| Frustrated | 🟠 Orange | 😠 |
| Angry | 🔴 Red | 😡 |

### Confidence Bar
| Range | Color |
|-------|-------|
| 0-50% | 🔴 Red |
| 50-70% | 🟡 Yellow |
| 70-100% | 🟢 Green |

---

## 📝 Common Tasks

### View an Email Reply
1. Find email in table
2. Click **[View]** button
3. Modal shows full conversation
4. Click **[Close]** to dismiss

### Refresh Emails
- Click **[Refresh]** button in navbar
- Or wait 30 seconds for auto-refresh

### Send Test Email
```bash
curl -X POST "http://localhost:8000/process-email" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "test@example.com",
    "subject": "Test Subject",
    "body": "This is a test message"
  }'
```

### Check Backend Health
```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "ok", "service": "SalesAI Email Agent"}
```

### Fetch Email Data Directly
```bash
curl "http://localhost:8000/api/emails?limit=10"
```

---

## 🔍 Table Columns Explained

| Column | Description |
|--------|-------------|
| **Sender** | Customer's email address |
| **Subject** | Email subject line |
| **Intent** | AI-classified email type (Order Status, Refund, etc.) |
| **Emotion** | Detected emotional tone (Happy, Angry, etc.) |
| **Confidence** | AI confidence in generated reply (0-100%) |
| **Status** | Processing result (Replied/Escalated/Failed) |
| **Time** | When email was processed |
| **Action** | View button to see full reply |

---

## 🛠 Configuration

### Change Auto-Refresh Interval
Edit `frontend/src/pages/Dashboard.jsx`:
```javascript
// Line: const interval = setInterval(fetchEmails, 30000)
// 30000 = 30 seconds
// Change to: 60000 = 60 seconds
const interval = setInterval(fetchEmails, 60000)
```

### Change Backend URL
Edit `frontend/src/pages/Dashboard.jsx`:
```javascript
// Line: const API_BASE_URL = 'http://localhost:8000'
const API_BASE_URL = 'https://your-api-domain.com'
```

### Change Email Limit
Edit `frontend/src/pages/Dashboard.jsx`:
```javascript
// Line: const response = await axios.get(`${API_BASE_URL}/api/emails`, { params: { limit: 100 } })
// Change 100 to desired limit
const response = await axios.get(`${API_BASE_URL}/api/emails`, { params: { limit: 500 } })
```

---

## 🐛 Debugging

### Check Browser Console
```
Ctrl + Shift + I → Console tab
```

Look for:
- Network errors (red)
- API response errors
- JavaScript errors

### Check Network Tab
```
Ctrl + Shift + I → Network tab
```

Look for:
- API requests to `/api/emails`
- Response status (200 = OK)
- Response payload

### Check Backend Logs
Look in Terminal 1 for messages like:
```
INFO:     GET /api/emails
INFO:     Fetched 5 email records from database
```

### Enable Verbose Logging
Add to backend `app/main.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📱 Responsive Breakpoints

- **Desktop** (1024px+): Full table view
- **Tablet** (768px-1023px): Horizontal scrolling
- **Mobile** (< 768px): Stacked layout

---

## 🔒 Security Notes

### Frontend
- No sensitive data stored in localStorage
- API calls made server-to-server
- CORS configured in backend

### Backend
- CORS allows all origins (update for production)
- No authentication required (add JWT tokens for production)
- Sensitive emails stored in PostgreSQL

---

## 📦 Dependencies

### Frontend
```json
{
  "react": "18.2.0",
  "react-dom": "18.2.0",
  "axios": "1.6.0",
  "vite": "5.0.8",
  "tailwindcss": "3.3.0"
}
```

### Backend (Already installed)
```
fastapi
uvicorn
psycopg2-binary (PostgreSQL)
google-generativeai (Gemini)
```

---

## 🚨 Common Issues & Solutions

### Issue: "Failed to load emails"
**Solution:**
```bash
# Check backend is running
curl http://localhost:8000/health

# Check API endpoint
curl http://localhost:8000/api/emails
```

### Issue: "No emails showing"
**Solution:**
```bash
# Send test email
curl -X POST "http://localhost:8000/process-email" \
  -H "Content-Type: application/json" \
  -d '{"customer_email":"test@gmail.com","subject":"Test","body":"Test"}'

# Refresh dashboard
# Click [Refresh] button
```

### Issue: Port 5173 already in use
**Solution:**
```bash
# Kill process on port 5173
lsof -i :5173
kill -9 <PID>

# Or start on different port
npm run dev -- --port 3000
```

### Issue: Port 8000 already in use
**Solution:**
```bash
# Kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Or use different port
uvicorn app.main:app --reload --port 8001
```

### Issue: Tailwind CSS not working
**Solution:**
```bash
# Clear cache and restart
npm run dev

# Or clean install
rm -rf node_modules package-lock.json
npm install
npm run dev
```

---

## 📋 Production Checklist

- [ ] Build frontend: `npm run build`
- [ ] Test production build: `npm run preview`
- [ ] Update backend URL
- [ ] Update CORS origins in backend
- [ ] Add authentication (JWT tokens)
- [ ] Set up HTTPS
- [ ] Configure database backups
- [ ] Set up monitoring/alerts
- [ ] Deploy frontend to hosting
- [ ] Deploy backend to server
- [ ] Update DNS records
- [ ] Monitor logs and performance

---

## 📚 File Locations

| File | Location |
|------|----------|
| Frontend source | `frontend/src/` |
| Backend API | `app/main.py` |
| Database functions | `app/db/supabase_client.py` |
| Dashboard guide | `DASHBOARD_SETUP.md` |
| Frontend README | `frontend/README.md` |

---

## 🎯 Next Steps

1. ✅ Read `DASHBOARD_SETUP.md`
2. ✅ Follow "Quick Start" section
3. ✅ Access dashboard at http://localhost:5173
4. ✅ Send test emails
5. ✅ View in dashboard
6. ✅ Customize as needed
7. ✅ Deploy to production

---

## 📞 Support Resources

- Backend Docs: `README.md` (root folder)
- Frontend Docs: `frontend/README.md`
- API Docs: Access http://localhost:8000/docs (Swagger)
- Dashboard Setup: `DASHBOARD_SETUP.md`

---

**Happy Monitoring!** 🎉

Dashboard is now ready to track all your email agent's operations.
