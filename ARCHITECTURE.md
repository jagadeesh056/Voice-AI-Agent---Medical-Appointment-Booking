# Architecture Documentation

## System Overview

The Voice AI Agent is a full-stack application for managing clinical appointments through natural voice conversation. It combines modern AI/ML with traditional database systems for a complete, production-ready solution.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Browser                           │
│  - Web Audio API for microphone access                          │
│  - WebSocket for real-time communication                        │
│  - React components for UI rendering                            │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ WebSocket + REST/JSON
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Nginx/Load Balancer                          │
│  - HTTPS termination                                            │
│  - Request routing                                              │
│  - Rate limiting                                                │
└────────────────┬────────────────────────────────────────────────┘
                 │
     ┌───────────┴────────────┐
     ▼                        ▼
┌──────────────┐    ┌──────────────┐
│  Next.js     │    │  FastAPI     │
│  Frontend    │    │  Backend     │
│              │    │              │
│ - Components │    │ - Routes     │
│ - Pages      │    │ - Services   │
│ - State Mgmt │    │ - Models     │
└──────────────┘    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    ┌────────┐         ┌────────┐         ┌────────┐
    │  Voice │         │   AI   │         │ Intent │
    │Process │         │ Agent  │         │  Class │
    │   or   │         │        │         │   ifier│
    │  (STT/ │         │ (GPT-4)│         │        │
    │  TTS)  │         │        │         │        │
    └────────┘         └────────┘         └────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    ┌────────┐         ┌────────┐         ┌─────────┐
    │Postgres│         │ Redis  │         │OpenAI   │
    │Database│         │Cache   │         │API      │
    │        │         │        │         │         │
    │ - Data │         │-Session│         │-Whisper │
    │ - Hist │         │-Context│         │-GPT-4   │
    └────────┘         └────────┘         │-TTS     │
                                          └─────────┘
```

## Backend Architecture

### Layer 1: API Layer (`app/routes/`)

**Responsibility**: HTTP/WebSocket request handling and response formatting

- **`users.py`**: User CRUD operations
- **`appointments.py`**: Appointment management
- **`sessions.py`**: Session lifecycle
- **`voice.py`**: Voice message processing and WebSocket management

**Flow**:
```
HTTP Request → Route Handler → Service Layer → Database/Cache
            ← Response (JSON/WebSocket)
```

### Layer 2: Service Layer (`app/services/`)

**Responsibility**: Business logic and external API integration

#### VoiceProcessor (`voice_processor.py`)
- Handles audio encoding/decoding
- Calls OpenAI Whisper for STT
- Calls OpenAI TTS for speech synthesis
- Audio feature extraction

**Flow**:
```
Audio (binary) → Base64 encode → Whisper API → Text
Text → OpenAI TTS API → MP3 audio → Base64 encode
```

#### VoiceAgent (`agent.py`)
- Core conversational AI logic
- Maintains conversation context
- Integrates intent classification and appointment extraction
- Generates contextual responses using GPT-4

**Flow**:
```
User Message → Intent Classification
            → Appointment Extraction
            → Context Management
            → GPT-4 Prompt Building
            → Response Generation
            → Appointment Actions
```

#### IntentClassifier (`intent_classifier.py`)
- Keyword-based intent detection
- Multi-language support (EN, HI, TA)
- Confidence scoring

**Intents**:
- `book`: Create new appointment
- `reschedule`: Modify existing appointment
- `cancel`: Delete appointment
- `query`: Ask about appointments
- `confirm`: User confirms action

#### AppointmentExtractor (`appointment_extractor.py`)
- Extracts appointment details from natural text
- Uses regex patterns and heuristics
- Supports date/time parsing
- Extracts doctor and clinic names

#### WebSocketHandler (`websocket_handler.py`)
- Real-time bidirectional communication
- Audio chunk handling
- Message streaming
- Connection lifecycle management

**Message Flow**:
```
Client → WebSocket → Audio chunks → Transcription
       ← Response JSON
       ← TTS audio (MP3 base64)
       ← Appointment data
```

### Layer 3: Data Layer (`app/database/`)

#### Models (`models.py`)

**User**:
```python
- id: int (PK)
- phone_number: str (unique)
- name: str
- email: str (optional)
- language_preference: str (en/hi/ta)
- status: enum (active/inactive/archived)
- timestamps: created_at, updated_at
```

**Appointment**:
```python
- id: int (PK)
- user_id: int (FK)
- appointment_date: datetime
- appointment_type: str (consultation/follow-up/checkup/etc)
- doctor_name: str
- clinic_name: str
- status: enum (booked/confirmed/completed/cancelled/rescheduled)
- notes: text
- timestamps: created_at, updated_at
```

**ConversationSession**:
```python
- id: int (PK)
- user_id: int (FK)
- session_token: str (unique, UUID)
- language: str
- is_active: bool
- start_time: datetime
- end_time: datetime (nullable)
- created_at: datetime
```

**ConversationHistory**:
```python
- id: int (PK)
- session_id: int (FK)
- appointment_id: int (FK, nullable)
- turn_number: int
- user_message: text
- assistant_message: text
- intent: str
- confidence_score: int
- created_at: datetime
```

#### Connection (`connection.py`)
- PostgreSQL connection pooling
- Session management
- Database initialization

### Layer 4: Cache Layer (`app/cache/`)

#### RedisCache (`redis_handler.py`)
- Session data storage (30-min TTL)
- Conversation context caching
- User data caching (60-min TTL)
- Fast lookup for active sessions

**Cache Keys**:
```
session:{session_token}     → Session metadata
context:{session_token}     → Conversation turns (last 10)
user:{user_id}              → User profile data
```

## Frontend Architecture (Next.js/React)

### Components

#### VoiceChat (`components/voice-chat.tsx`)
- Main application component
- State management for messages, recording, WebSocket
- Audio recording with Web Audio API
- WebSocket connection lifecycle

**State**:
```typescript
- sessionId: string
- messages: Message[]
- isRecording: boolean
- isProcessing: boolean
- language: 'en' | 'hi' | 'ta'
- connectionStatus: 'disconnected' | 'connecting' | 'connected'
```

**Features**:
- Real-time message display
- Audio recording/playback
- Language selection
- Connection status indicator
- Message history

### Page Structure

```
/
└── page.tsx (renders VoiceChat component)
└── layout.tsx (root HTML structure)
```

## Data Flow Diagrams

### Complete Voice Message Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ User presses "Speak" button → Browser requests microphone       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Audio recorded via Web Audio API → Encoded to base64            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket sends audio chunk {type: 'audio', data: base64}       │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼ (FastAPI WebSocket Handler)
┌─────────────────────────────────────────────────────────────────┐
│ VoiceProcessor.transcribe_audio()                               │
│   → Base64 decode                                               │
│   → Send to Whisper API (~300ms)                                │
│   → Receive transcribed text                                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket sends back {type: 'transcription', text: '...'}       │
│ (User sees their spoken words in UI)                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ VoiceAgent.process_message()                                    │
│   1. IntentClassifier.classify() → 'book'/'reschedule'/etc      │
│   2. AppointmentExtractor.extract() → date, doctor, clinic      │
│   3. Build GPT-4 prompt with:                                   │
│      - System instructions                                      │
│      - Conversation history (last 5 turns)                      │
│      - Current message                                          │
│   4. Call OpenAI API (~150ms)                                   │
│   5. Receive response text                                      │
│   6. Extract appointment data if intent is 'book'               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ VoiceProcessor.synthesize_speech()                              │
│   → Send response text to OpenAI TTS API (~100ms)               │
│   → Receive MP3 audio                                           │
│   → Base64 encode                                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Store in Database:                                              │
│   - ConversationHistory (turn, messages, intent)                │
│   - Appointment (if action taken)                               │
│   - Update ConversationSession                                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Update Redis Cache:                                             │
│   - conversation_turns list (max 10)                            │
│   - intent_history                                              │
│   - booking_context                                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket sends response {type: 'response', message, audio...}  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ Frontend receives:                                              │
│   - Displays text message                                       │
│   - Plays MP3 audio via Web Audio API                           │
│   - Shows appointment details (if applicable)                   │
│   - Updates conversation history                                │
└─────────────────────────────────────────────────────────────────┘
```

**Total Latency**: 300 + 150 + 100 + DB write + network = ~450-500ms

## Performance Characteristics

### Response Times
- STT (Whisper): 200-300ms
- NLU (Intent + Extraction): 50-100ms
- LLM (GPT-4): 100-200ms
- TTS (OpenAI): 50-100ms
- Database Write: 5-10ms
- Network Round-trip: ~100ms
- **Total**: ~450-500ms target

### Throughput
- Single instance: ~10 concurrent sessions
- Database connection pool: 10 + 20 overflow
- Redis can handle 10k+ ops/sec
- OpenAI API: depends on rate limits

### Storage
- Average conversation: ~5KB
- Appointment record: ~500 bytes
- User record: ~1KB
- 10,000 users × 1KB = 10MB users table
- 100,000 appointments × 500B = 50MB appointments
- 1,000,000 conversation turns × 5B = 5GB

## Security Architecture

### Authentication & Authorization
- Session tokens (UUID-based)
- User isolation (can only access own data)
- No persistent user login (stateless sessions)

### Data Protection
- Prepared statements (SQLAlchemy ORM prevents SQL injection)
- Input validation (Pydantic schemas)
- HTTPS ready (TLS termination at Nginx)

### Secrets Management
- Environment variables for API keys
- No secrets in git/code
- PostgreSQL user authentication
- Redis optional authentication

## Scaling Considerations

### Horizontal Scaling
1. **API Servers**: Deploy multiple FastAPI instances behind load balancer
2. **Frontend**: Static Next.js build can be served from CDN
3. **Database**: Use PostgreSQL replication or managed service (AWS RDS)
4. **Cache**: Use managed Redis (AWS ElastiCache)

### Vertical Scaling
1. Increase PostgreSQL connection pool
2. Add more RAM to Redis
3. Use faster CPU for Python workers

### Optimization Paths
1. Implement request caching for common queries
2. Use database query optimization and indexes
3. Implement async database operations
4. Use connection pooling for OpenAI API calls
5. Add response compression

## Monitoring & Observability

### Key Metrics
- Request latency (p50, p95, p99)
- Error rate
- Database connection pool usage
- Cache hit rate
- OpenAI API call counts
- Message processing rate

### Logging Strategy
- Backend: Structured JSON logs with timestamps
- Frontend: Browser console + error tracking
- Database: PostgreSQL query logs
- WebSocket: Connection events and errors

### Health Checks
- API: `/health` endpoint
- Database: Connection test on startup
- Redis: Ping on startup
- OpenAI: Test with models list

## Deployment Architecture

### Development
```
Local PostgreSQL + Redis + FastAPI + Next.js dev server
```

### Staging
```
Docker Compose with all services containerized
```

### Production
```
Nginx reverse proxy
  ↓
Load balancer (AWS ELB)
  ↓
  ├→ FastAPI instances (multiple)
  ├→ Next.js instances (multiple)
  ↓
  ├→ RDS PostgreSQL (managed)
  ├→ ElastiCache Redis (managed)
  ├→ CloudFront CDN
```

## Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend | Python/FastAPI | 3.13 / 0.136+ |
| Frontend | Next.js/React | 14+ / 19+ |
| Database | PostgreSQL | 14+ |
| Cache | Redis | 7+ |
| STT | OpenAI Whisper | API v1 |
| LLM | OpenAI GPT-4 | Turbo |
| TTS | OpenAI TTS | tts-1 |
| Auth | Session tokens | UUID |
| ORM | SQLAlchemy | 2.0+ |
| API docs | Pydantic/Swagger | 2.13+ |

## Future Architecture Improvements

1. **Microservices**: Split voice processing into separate service
2. **Message Queue**: Use Redis Queue or Celery for async tasks
3. **Vector DB**: Store conversation embeddings for semantic search
4. **Graph DB**: Model appointment dependencies and doctor networks
5. **Event Streaming**: Kafka for conversation event processing
6. **Caching Layer**: Redis caching for frequently accessed data
7. **CDN**: CloudFront for static assets
8. **Monitoring**: DataDog/Prometheus for metrics
