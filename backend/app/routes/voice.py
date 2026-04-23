from fastapi import APIRouter, Depends, HTTPException, status, WebSocket
from sqlalchemy.orm import Session

from app.database.connection import get_db, SessionLocal
from app.database.models import ConversationSession, ConversationHistory
from app.schemas.voice_schemas import VoiceMessageRequest, VoiceMessageResponse
from app.cache.redis_handler import cache
from app.services.voice_processor import VoiceProcessor
from app.services.agent import VoiceAgent
from app.services.websocket_handler import VoiceWebSocketHandler

router = APIRouter()

voice_processor = VoiceProcessor()
agent = VoiceAgent()
ws_handler = VoiceWebSocketHandler()


@router.post("/process", response_model=VoiceMessageResponse)
async def process_voice_message(
    request: VoiceMessageRequest,
    db: Session = Depends(get_db),
):
    """Process a voice/text message and return agent response"""

    session = db.query(ConversationSession).filter(
        ConversationSession.session_token == request.session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is no longer active",
        )

    context = cache.get_conversation_context(request.session_id) or {}
    language = request.language or session.language

    result = await agent.process_message(
        user_message=request.user_message,
        session_id=request.session_id,
        user_id=session.user_id,
        language=language,
        context=context,
        db=db,
    )

    turn_number = len(context.get("conversation_turns", [])) + 1

    appointment_id = None
    if result.get("appointment_data"):
        appointment_id = result["appointment_data"].get("appointment_id")

    history_entry = ConversationHistory(
        session_id=session.id,
        appointment_id=appointment_id,
        turn_number=turn_number,
        user_message=request.user_message,
        assistant_message=result["response"],
        intent=result["intent"],
        confidence_score=result["confidence"],
    )
    db.add(history_entry)
    db.commit()
    db.refresh(history_entry)

    conversation_turns = context.get("conversation_turns", [])
    conversation_turns.append({
        "turn": turn_number,
        "user": request.user_message,
        "assistant": result["response"],
        "intent": result["intent"],
    })
    if len(conversation_turns) > 10:
        conversation_turns = conversation_turns[-10:]

    context["conversation_turns"] = conversation_turns
    context["intent_history"] = context.get("intent_history", []) + [result["intent"]]

    if result.get("_booking_context"):
        context["booking_context"] = result["_booking_context"]
    else:
        context["booking_context"] = {}

    cache.store_conversation_context(request.session_id, context)

    print(f"[v0] Turn {turn_number} | session={request.session_id} | intent={result['intent']}")

    return VoiceMessageResponse(
        session_id=request.session_id,
        turn_number=turn_number,
        user_message=request.user_message,
        assistant_message=result["response"],
        intent=result["intent"],
        confidence_score=result["confidence"],
        audio_base64=result.get("audio_base64"),
        appointment_data=result.get("appointment_data"),
    )


@router.websocket("/ws/{session_id}")
async def websocket_voice_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time voice streaming"""
    db = SessionLocal()
    try:
        await ws_handler.handle_connection(websocket, session_id, db)
    finally:
        db.close()