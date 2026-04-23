import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.database.connection import get_db
from app.database.models import ConversationSession, User
from app.schemas.voice_schemas import (
    SessionStartRequest,
    SessionStartResponse,
    SessionEndRequest
)
from app.cache.redis_handler import cache

router = APIRouter()


@router.post("/start", response_model=SessionStartResponse)
async def start_session(
    request: SessionStartRequest,
    db: Session = Depends(get_db)
):
    """Start a new conversation session"""
    
    # Try to find existing user or create new one
    user = None
    if request.phone_number:
        user = db.query(User).filter(User.phone_number == request.phone_number).first()
    
    if not user and request.phone_number:
        # Create new user if doesn't exist
        user = User(
            phone_number=request.phone_number,
            name=request.name or "Guest",
            language_preference=request.language
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[v0] New user created during session start: {user.id}")
    elif not user:
        # Create temporary user for anonymous session
        user = User(
            phone_number=f"temp_{uuid.uuid4().hex[:8]}",
            name=request.name or "Guest",
            language_preference=request.language
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # Create session token
    session_token = str(uuid.uuid4())
    
    # Create conversation session
    session = ConversationSession(
        user_id=user.id,
        session_token=session_token,
        language=request.language,
        is_active=True
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Store session in Redis with initial context
    session_data = {
        "session_id": session.id,
        "session_token": session_token,
        "user_id": user.id,
        "language": request.language,
        "is_active": True,
        "created_at": session.start_time.isoformat()
    }
    cache.set_session(session_token, session_data)
    
    # Initialize conversation context
    context = {
        "user_name": user.name,
        "language": request.language,
        "conversation_turns": [],
        "intent_history": [],
        "booking_context": {}
    }
    cache.store_conversation_context(session_token, context)
    
    print(f"[v0] Session started: {session.id} for user {user.id}")
    
    return SessionStartResponse(
        session_id=session_token,
        user_id=user.id,
        language=request.language,
        message="Session started successfully. How can I help you with your appointment today?"
    )


@router.get("/{session_id}")
async def get_session_info(session_id: str, db: Session = Depends(get_db)):
    """Get session information"""
    # Try to get from cache first
    session_data = cache.get_session(session_id)
    if session_data:
        return session_data
    
    # Get from database
    session = db.query(ConversationSession).filter(
        ConversationSession.session_token == session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "language": session.language,
        "is_active": session.is_active,
        "created_at": session.start_time.isoformat()
    }


@router.post("/end")
async def end_session(
    request: SessionEndRequest,
    db: Session = Depends(get_db)
):
    """End a conversation session"""
    
    session = db.query(ConversationSession).filter(
        ConversationSession.session_token == request.session_id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Update session
    session.is_active = False
    session.end_time = datetime.utcnow()
    db.commit()
    
    # Delete from cache
    cache.delete_session(request.session_id)
    
    print(f"[v0] Session ended: {session.id} (reason: {request.end_reason})")
    
    return {
        "status": "ended",
        "session_id": request.session_id,
        "end_reason": request.end_reason
    }
