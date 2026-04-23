# Quick Start Guide

Get the Voice AI Agent running in 10 minutes.

## Prerequisites

- Python 3.13+
- Node.js 18+
- PostgreSQL 14+ (or use Docker)
- Redis 7+ (or use Docker)
- OpenAI API Key

## 1-Minute Setup (Using Docker)

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="sk-..."

# Start all services
docker-compose up -d

# Wait for services to be ready (30 seconds)
sleep 30

# Run tests to verify
cd backend
python test_integration.py

# Open browser
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

## Manual Setup (5 Minutes)

### Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/voice_agent_db
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=your_api_key_here
HOST=0.0.0.0
PORT=8000
EOF

# 5. Initialize database
python setup_db.py

# 6. Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup (New Terminal)

```bash
# 1. Install dependencies
pnpm install

# 2. Start development server
pnpm dev

# 3. Open http://localhost:3000
```

## Testing

```bash
# In backend directory
python test_integration.py
```

This runs ~20 tests covering:
- Health checks
- Session management
- Voice processing
- Appointments
- Language support

## First Conversation

1. Open http://localhost:3000
2. Click the blue "Tap to Speak" button
3. Say: "I need to book an appointment"
4. The AI will respond and extract appointment details
5. Confirm to book the appointment

## API Documentation

Interactive API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Key Endpoints

```bash
# Start a session
curl -X POST http://localhost:8000/api/sessions/start \
  -H "Content-Type: application/json" \
  -d '{"name": "John", "language": "en"}'

# Process a message
curl -X POST http://localhost:8000/api/voice/process \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "...",
    "user_message": "Book an appointment",
    "language": "en"
  }'

# Get health status
curl http://localhost:8000/health
```

## Troubleshooting

### Port Already in Use

```bash
# Frontend (3000)
lsof -i :3000 | kill -9 <PID>

# Backend (8000)
lsof -i :8000 | kill -9 <PID>
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
psql -U postgres -d postgres -c "SELECT 1"

# Or start with Docker
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
```

### Redis Connection Failed

```bash
# Check Redis is running
redis-cli ping

# Or start with Docker
docker run -d -p 6379:6379 redis:7
```

### OpenAI API Error

```bash
# Verify API key
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models | head -20

# Update .env with correct key
# Then restart backend
```

## Next Steps

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Test Languages**: Switch between English, Hindi, Tamil in the UI
3. **Create Users**: Use the API to create multiple users
4. **Schedule Appointments**: Book several test appointments
5. **Review Database**: Check stored appointments and conversation history

## File Structure

```
/backend
  app/main.py              # FastAPI app entry point
  app/routes/              # API endpoints
  app/services/            # Business logic
  setup_db.py              # Database initialization
  test_integration.py      # Integration tests

/components
  voice-chat.tsx           # Main UI component

/app
  page.tsx                 # Next.js page
  layout.tsx               # Root layout
```

## Common Tasks

### Change Language
In the UI, select language from dropdown (top right)

### View Conversation History
```bash
# Database query
psql -U postgres -d voice_agent_db -c "
SELECT turn_number, user_message, assistant_message, intent 
FROM conversation_history 
ORDER BY created_at DESC 
LIMIT 10;"
```

### Reset Database
```bash
cd backend
python setup_db.py  # This recreates tables
```

### View Server Logs
```bash
# Backend
uvicorn app.main:app --reload  # Logs appear in terminal

# Frontend
pnpm dev  # Logs appear in terminal
```

## Performance Notes

- First request to OpenAI API: ~2-3 seconds (cold start)
- Subsequent requests: ~300-500ms
- Audio processing: Mostly network latency
- Database queries: <10ms with proper indexes

## Security Notes

For production, you should:

1. Change PostgreSQL password
2. Use environment variables for all secrets
3. Enable HTTPS/SSL
4. Set up firewall rules
5. Use strong session tokens
6. Implement rate limiting
7. Enable database backups

See `DEPLOYMENT.md` for production setup.

## Getting Help

- API Documentation: http://localhost:8000/docs
- GitHub Issues: (add your repo)
- Documentation: See README.md
- Deployment: See DEPLOYMENT.md

## What's Next?

1. Integrate with actual phone system (Twilio/Vonage)
2. Add SMS confirmations
3. Add email reminders
4. Build admin dashboard
5. Add payment processing
6. Deploy to production

Happy coding!
