# SalesAI Admin Dashboard

A modern, responsive React + Vite admin dashboard for monitoring and managing customer support emails processed by the SalesAI Email Agent.

## Features

✅ Real-time email monitoring table
✅ Email intent, emotion, and confidence score tracking
✅ Email status visualization (replied, escalated, failed)
✅ View generated replies in a modal
✅ Auto-refresh every 30 seconds
✅ Mobile-responsive design
✅ Clean, production-ready UI with Tailwind CSS

## Tech Stack

- **Frontend Framework**: React 18
- **Build Tool**: Vite
- **HTTP Client**: Axios
- **Styling**: Tailwind CSS
- **Package Manager**: npm

## Installation

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Environment Setup

Ensure the backend is running on `http://localhost:8000`. The frontend is configured to proxy API requests to this URL.

### 3. Development Server

```bash
npm run dev
```

The dashboard will be available at `http://localhost:5173`

### 4. Production Build

```bash
npm run build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Navbar.jsx              # Top navigation bar
│   │   ├── EmailTable.jsx          # Main email data table
│   │   ├── ReplyModal.jsx          # Modal for viewing replies
│   │   ├── StatusBadge.jsx         # Status indicator component
│   │   ├── EmotionBadge.jsx        # Emotion indicator component
│   │   └── ConfidenceBar.jsx       # Confidence score progress bar
│   ├── pages/
│   │   └── Dashboard.jsx           # Main dashboard page
│   ├── App.jsx                     # Root app component
│   ├── main.jsx                    # React DOM entry point
│   └── index.css                   # Global styles
├── index.html                      # HTML template
├── vite.config.js                  # Vite configuration
├── tailwind.config.js              # Tailwind CSS configuration
├── postcss.config.js               # PostCSS configuration
└── package.json                    # Dependencies and scripts
```

## Component Documentation

### Navbar
Displays the SalesAI logo, total email count, and refresh button.

**Props:**
- `totalEmails` (number): Total count of emails
- `onRefresh` (function): Callback for refresh button
- `isLoading` (boolean): Loading state

### EmailTable
Displays emails in a responsive table with sortable columns.

**Props:**
- `emails` (array): Array of email objects
- `onViewReply` (function): Callback when "View" button is clicked

**Email Object Structure:**
```javascript
{
  id: "123",
  sender: "customer@example.com",
  subject: "Order Status",
  body: "Where is my order?",
  intent: "Order Status",
  emotion: "frustrated",
  reply: "Your order will ship tomorrow",
  confidence: 0.82,
  status: "replied",
  timestamp: "2026-03-23T10:30:00"
}
```

### ReplyModal
Modal popup showing the full email thread and generated reply.

**Props:**
- `email` (object): Email object to display
- `isOpen` (boolean): Modal visibility
- `onClose` (function): Callback to close modal

### StatusBadge
Colored badge indicating email processing status.

**Statuses:**
- ✅ `replied` - Green
- ⚠️ `escalated` - Red
- ❌ `failed` - Gray

### EmotionBadge
Colored badge showing detected customer emotion.

**Emotions:**
- 😊 `happy` - Green
- 😐 `neutral` - Yellow
- 😠 `frustrated` - Orange
- 😡 `angry` - Red

### ConfidenceBar
Progress bar showing confidence score of the generated reply (0-100%).

## API Integration

The dashboard fetches email records from the backend API:

```
GET /api/emails?limit=100
```

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

## Usage

1. **Start the backend** (in the parent directory):
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. **Start the frontend** (in the frontend directory):
   ```bash
   npm run dev
   ```

3. **Open your browser** to `http://localhost:5173`

4. **View incoming emails** in the table as they're processed

5. **Click "View"** on any email to see the full conversation and generated reply

## Features in Detail

### Real-time Monitoring
- Auto-refreshes email data every 30 seconds
- Manual refresh button in navbar
- Loading states for better UX

### Email Details
- **Sender**: Customer email address
- **Subject**: Email subject line
- **Intent**: Classified email intent (Order Status, Refund Request, etc.)
- **Emotion**: Detected customer emotional state
- **Confidence**: AI confidence score for the reply (0-100%)
- **Status**: Processing result (Replied, Escalated, Failed)
- **Timestamp**: When the email was processed

### Reply Viewing
- Click the "View" button to open a modal
- See original customer message
- View the generated AI reply
- Close modal to return to table

## Responsive Design

The dashboard is fully responsive:
- **Desktop**: Full table with all columns visible
- **Tablet**: Scrollable table with optimized spacing
- **Mobile**: Vertical scrolling with stacked columns

## Error Handling

- Network errors display a friendly error message
- Backend connection issues are handled gracefully
- Auto-retry mechanism via regular polling
- User-friendly error messages

## Performance Optimizations

- Lazy loading with Vite
- Efficient React re-rendering with hooks
- Tailwind CSS for minimal CSS
- Optimized regex and string operations
- 30-second auto-refresh interval (configurable)

## Browser Support

- Chrome/Chromium (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Development Notes

### Adding New Components
1. Create component file in `src/components/`
2. Use functional components with React hooks
3. Accept props for data and callbacks
4. Use Tailwind CSS for styling

### Modifying Table Columns
Edit the table headers and rows in `EmailTable.jsx`

### Changing API Endpoint
Update `API_BASE_URL` in `Dashboard.jsx`

### Customizing Styles
Edit `tailwind.config.js` for theme customization
Edit `src/index.css` for global styles

## Troubleshooting

### Dashboard shows "No emails yet"
- Check backend is running on `http://localhost:8000`
- Check that the `/api/emails` endpoint is returning data
- Check browser console for network errors

### CORS errors in console
- Backend CORS middleware is configured in `app/main.py`
- Ensure backend has CORS enabled

### Refresh button not working
- Check network tab in DevTools
- Verify backend API endpoint is responding
- Check for error messages in console

## Production Deployment

### Build for Production
```bash
npm run build
```

### Serve Build
```bash
npm run preview
```

### Deploy to Production Server
1. Build the frontend: `npm run build`
2. Serve the `dist/` folder using a web server
3. Configure proxy to backend API

### Environment Variables
Create a `.env.production` file for production settings:
```
VITE_API_URL=https://api.yourdomain.com
```

## License

Built for SalesAI Email Agent
