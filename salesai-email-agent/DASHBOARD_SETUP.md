# SalesAI Admin Dashboard - Setup Guide

## Overview

A complete React + Vite admin dashboard frontend for the SalesAI Email Agent backend. View, monitor, and manage all processed customer emails with real-time updates.

## What's Included

### ✅ Frontend (React + Vite)
- Responsive admin dashboard
- Real-time email table
- Email reply viewer modal
- Status & emotion badges
- Confidence score visualization
- Auto-refresh functionality
- Mobile-friendly design

### ✅ Backend Updates
- New `/api/emails` endpoint
- `get_email_records()` database function
- CORS middleware for frontend access
- Email record storage and retrieval

## Folder Structure

```
salesai-email-agent/
├── app/
│   ├── main.py                 # Updated with /api/emails endpoint & CORS
│   └── db/
│       └── supabase_client.py  # Updated with get_email_records()
└── frontend/                   # NEW: React + Vite frontend
    ├── src/
    │   ├── components/
    │   │   ├── Navbar.jsx
    │   │   ├── EmailTable.jsx
    │   │   ├── ReplyModal.jsx
    │   │   ├── StatusBadge.jsx
    │   │   ├── EmotionBadge.jsx
    │   │   └── ConfidenceBar.jsx
    │   ├── pages/
    │   │   └── Dashboard.jsx
    │   ├── App.jsx
    │   ├── main.jsx
    │   └── index.css
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── package.json
    ├── README.md
    └── .gitignore
```

## Quick Start

### Step 1: Backend Setup (One-time)

The backend is already updated. Make sure you have the latest code:

```bash
cd d:\SalesAI\salesai-email-agent
pip install -r requirements.txt
```

### Step 2: Frontend Installation

```bash
cd frontend
npm install
```

This will install:
- React 18
- Vite 5
- Axios (for API calls)
- Tailwind CSS (for styling)
- Supporting tools

### Step 3: Start Backend

```bash
cd d:\SalesAI\salesai-email-agent
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 4: Start Frontend (in a new terminal)

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.0.8  ready in XXX ms

  ➜  Local:   http://localhost:5173/
```

### Step 5: Access Dashboard

Open your browser to **http://localhost:5173**

You should see:
- SalesAI Admin header
- Empty table (if no emails processed yet)
- Navbar with refresh button

## Using the Dashboard

### View Emails
1. Navigate to http://localhost:5173
2. Table displays all processed emails
3. Shows: Sender, Subject, Intent, Emotion, Confidence, Status, Time

### Check Email Details
1. Click the **"View"** button on any email
2. Modal opens showing:
   - Customer email address
   - Original subject
   - Original message body
   - Generated AI reply
3. Click **"Close"** to return to table

### Refresh Data
1. Click the **"Refresh"** button in navbar
2. Fetches latest emails from backend
3. Automatic refresh every 30 seconds

### Understand Status Badges
- 🟢 **Replied** (Green) = Email answered by AI
- 🔴 **Escalated** (Red) = Email sent to human support
- ⚪ **Failed** (Gray) = Email processing failed

### Understand Emotion Badges
- 🟢 **Happy** (Green)
- 🟡 **Neutral** (Yellow)
- 🟠 **Frustrated** (Orange)
- 🔴 **Angry** (Red)

### Confidence Bar
- Shows 0-100% confidence in the generated reply
- 🟢 70-100% = High confidence
- 🟡 50-70% = Medium confidence
- 🔴 0-50% = Low confidence

## Testing the System

### Generate Test Emails

Use curl or Postman to send test emails:

```bash
curl -X POST "http://localhost:8000/process-email" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "test@example.com",
    "subject": "Order Status Query",
    "body": "Where is my order? I have been waiting for 2 weeks!"
  }'
```

Wait a few seconds, then refresh the dashboard to see the processed email.

### Check Backend API Directly

```bash
curl http://localhost:8000/api/emails
```

Should return JSON with email records.

## Features Overview

### Real-time Monitoring
- Auto-refresh every 30 seconds
- Manual refresh button
- Loading states for better UX

### Email Analysis
- **Intent Classification** - Order Status, Refund Request, etc.
- **Emotion Detection** - Happy, Neutral, Frustrated, Angry
- **Confidence Score** - How confident the AI is in its reply
- **Status Tracking** - Replied, Escalated, or Failed

### Reply Management
- View full generated replies in modal
- See context (original message + subject)
- Understand why email was escalated

### Responsive Design
- Desktop-optimized table view
- Tablet-friendly with horizontal scroll
- Mobile-friendly with stacked layout

## Environment Variables

If needed, create `frontend/.env.local`:

```
VITE_API_URL=http://localhost:8000
```

(Already configured in vite.config.js)

## Development Commands

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linter (if configured)
npm run lint
```

## Components Explained

### Navbar
- Shows SalesAI logo
- Displays total email count
- Has refresh button
- Shows loading state during refresh

### EmailTable
- Displays emails in responsive table
- Columns: Sender, Subject, Intent, Emotion, Confidence, Status, Time, Actions
- Click "View" button to see full reply
- Hover effect for better UX

### ReplyModal
- Modal popup for viewing email details
- Shows: From, Subject, Original Message, Generated Reply
- Close button to dismiss
- Scrollable for long content

### StatusBadge
- Color-coded status indicators
- replied → Green
- escalated → Red
- failed → Gray

### EmotionBadge
- Color-coded emotion indicators
- happy → Green
- neutral → Yellow
- frustrated → Orange
- angry → Red

### ConfidenceBar
- Progress bar (0-100%)
- Color changes based on confidence level
- High (≥70%) → Green
- Medium (50-70%) → Yellow
- Low (<50%) → Red

## API Specification

### Get Emails Endpoint

```
GET /api/emails
```

**Query Parameters:**
- `limit` (optional, default: 100) - Maximum records to return

**Response:**
```json
{
  "total": 5,
  "emails": [
    {
      "id": 1,
      "sender": "customer@gmail.com",
      "subject": "Order Status",
      "body": "Where is my order?",
      "intent": "Order Status",
      "emotion": "frustrated",
      "reply": "Your order...",
      "confidence": 0.82,
      "status": "replied",
      "timestamp": "2026-03-23T10:30:00"
    }
  ]
}
```

**Error Response:**
```json
{
  "detail": "Error message"
}
```

## Troubleshooting

### "Failed to load emails" Error
**Causes:**
- Backend not running on port 8000
- API endpoint not responding
- CORS not properly configured

**Solution:**
1. Check backend is running: `http://localhost:8000/health`
2. Check API endpoint: `http://localhost:8000/api/emails`
3. Check browser console for error details

### No Emails Showing
**Causes:**
- No emails processed yet
- Database not initialized
- Email records not saved

**Solution:**
1. Send test email: 
   ```bash
   curl -X POST "http://localhost:8000/process-email" \
     -H "Content-Type: application/json" \
     -d '{"customer_email":"test@example.com","subject":"Test","body":"Test"}'
   ```
2. Wait 3-5 seconds
3. Click "Refresh" button

### Modal Won't Display
**Causes:**
- Email object missing required fields
- Redux state not updating

**Solution:**
1. Check browser console for errors
2. Verify backend returns complete email object
3. Refresh page

### Styling Issues
**Causes:**
- Tailwind CSS not compiled
- Browser cache

**Solution:**
1. Clear browser cache (Ctrl+Shift+Delete)
2. Hard refresh (Ctrl+F5)
3. Stop dev server and restart: `npm run dev`

## Building for Production

### 1. Build Frontend
```bash
cd frontend
npm run build
```

Creates optimized `dist/` folder.

### 2. Deploy Frontend
Option A: Static hosting (Netlify, Vercel, etc.)
- Upload contents of `dist/` folder

Option B: Serve from backend
- Copy `dist/` folder to backend static directory
- Configure backend to serve frontend

### 3. Update Backend URL
Before building, update API URL in `.env.local`:
```
VITE_API_URL=https://your-api-domain.com
```

Then rebuild:
```bash
npm run build
```

## Performance Tips

- Auto-refresh every 30 seconds (configurable in Dashboard.jsx)
- Efficient React hooks usage
- Tailwind CSS for minimal styling
- Vite for fast bundling
- Lazy component loading

## Code Quality

- Production-ready React best practices
- Proper error handling
- Loading states
- Clean component structure
- Reusable components
- Proper prop types usage

## Next Steps

1. ✅ Install dependencies: `npm install`
2. ✅ Start backend: `uvicorn app.main:app --reload ...`
3. ✅ Start frontend: `npm run dev`
4. ✅ Access dashboard: http://localhost:5173
5. ✅ Send test emails and view in dashboard
6. ✅ Deploy to production when ready

## Support

For issues or questions:
1. Check frontend/README.md for detailed docs
2. Check browser console for error messages
3. Check backend logs for API errors
4. Verify all services are running

## File Manifest

### Backend Changes
- `app/main.py` - Added CORS middleware and `/api/emails` endpoint
- `app/db/supabase_client.py` - Added `get_email_records()` function

### Frontend Files Created
- `frontend/package.json` - Dependencies
- `frontend/vite.config.js` - Vite configuration
- `frontend/tailwind.config.js` - Tailwind configuration
- `frontend/postcss.config.js` - PostCSS configuration
- `frontend/index.html` - HTML template
- `frontend/src/main.jsx` - React entry point
- `frontend/src/App.jsx` - Root component
- `frontend/src/index.css` - Global styles
- `frontend/src/pages/Dashboard.jsx` - Main dashboard page
- `frontend/src/components/Navbar.jsx` - Top navigation
- `frontend/src/components/EmailTable.jsx` - Email table display
- `frontend/src/components/ReplyModal.jsx` - Reply modal
- `frontend/src/components/StatusBadge.jsx` - Status indicator
- `frontend/src/components/EmotionBadge.jsx` - Emotion indicator
- `frontend/src/components/ConfidenceBar.jsx` - Confidence visualization
- `frontend/.gitignore` - Git ignore rules
- `frontend/README.md` - Detailed documentation

---

**Ready to go!** 🚀 Start the services and access your admin dashboard at http://localhost:5173
