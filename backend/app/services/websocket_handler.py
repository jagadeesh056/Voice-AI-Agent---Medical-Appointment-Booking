import json
import asyncio
from typing import Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.services.voice_processor import VoiceProcessor
from app.services.agent import VoiceAgent
from app.cache.redis_handler import cache
from app.database.connection import SessionLocal
from app.database.models import ConversationSession, ConversationHistory

OLLAMA_TIMEOUT_SECONDS = 60


class VoiceWebSocketHandler:
    """Handles WebSocket connections for real-time voice processing"""

    def __init__(self):
        self.voice_processor = VoiceProcessor()
        self.agent = VoiceAgent()
        self.active_sessions: Dict[str, WebSocket] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        db: Optional[Session] = None,
    ):
        await websocket.accept()
        self.active_sessions[session_id] = websocket
        print(f"[v0] WebSocket connected: {session_id}")

        session_data = cache.get_session(session_id)
        if not session_data:
            await websocket.send_json({
                "type": "error",
                "message": "Session not found",
                "session_id": session_id,
            })
            await websocket.close()
            return

        owns_db_session = False
        if db is None:
            db = SessionLocal()
            owns_db_session = True

        try:
            while True:
                raw_data = await websocket.receive_text()
                message_data = json.loads(raw_data)
                msg_type = message_data.get("type")

                if msg_type == "audio":
                    await self._handle_audio_chunk(websocket, session_id, message_data, db)
                elif msg_type == "text":
                    await self._handle_text_message(websocket, session_id, message_data, db)
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg_type == "close":
                    await websocket.close()
                    break
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unsupported message type: {msg_type}",
                        "session_id": session_id,
                    })

        except WebSocketDisconnect:
            print(f"[v0] WebSocket disconnected: {session_id}")
        except Exception as e:
            print(f"[v0] WebSocket error for {session_id}: {e}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                    "session_id": session_id,
                })
            except Exception:
                pass
        finally:
            self.active_sessions.pop(session_id, None)
            if owns_db_session and db:
                db.close()

    # ------------------------------------------------------------------
    # Audio handler
    # ------------------------------------------------------------------

    async def _handle_audio_chunk(
        self,
        websocket: WebSocket,
        session_id: str,
        message_data: dict,
        db: Session,
    ):
        try:
            audio_data = message_data.get("data")
            language = message_data.get("language", "en")

            # In Ollama / text-only mode this helps mock STT return the real text
            hint_text = message_data.get("hint_text") or message_data.get("text")

            if not audio_data:
                await websocket.send_json({
                    "type": "error",
                    "message": "Audio chunk missing",
                    "session_id": session_id,
                })
                return

            transcription = await self.voice_processor.transcribe_audio(
                audio_data=audio_data,
                language=language,
                hint_text=hint_text,
            )

            if not transcription.get("text"):
                await websocket.send_json({
                    "type": "error",
                    "message": "Could not transcribe audio",
                    "session_id": session_id,
                })
                return

            await websocket.send_json({
                "type": "transcription",
                "text": transcription["text"],
                "confidence": transcription.get("confidence", 0),
                "session_id": session_id,
            })

            await self._handle_text_message(
                websocket=websocket,
                session_id=session_id,
                message_data={
                    "type": "text",
                    "message": transcription["text"],
                    "language": language,
                },
                db=db,
            )

        except Exception as e:
            print(f"[v0] Error processing audio chunk: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"Audio processing error: {str(e)}",
                "session_id": session_id,
            })

    # ------------------------------------------------------------------
    # Text / main handler
    # ------------------------------------------------------------------

    async def _handle_text_message(
        self,
        websocket: WebSocket,
        session_id: str,
        message_data: dict,
        db: Session,
    ):
        try:
            user_message = (message_data.get("message") or "").strip()
            language = message_data.get("language", "en")

            if not user_message:
                return

            session_db = db.query(ConversationSession).filter(
                ConversationSession.session_token == session_id
            ).first()

            if not session_db:
                await websocket.send_json({
                    "type": "error",
                    "message": "Session not found in database",
                    "session_id": session_id,
                })
                return

            if not session_db.is_active:
                await websocket.send_json({
                    "type": "error",
                    "message": "Session is no longer active",
                    "session_id": session_id,
                })
                return

            context = cache.get_conversation_context(session_id) or {}

            await websocket.send_json({
                "type": "processing",
                "message": "Processing your message…",
                "session_id": session_id,
            })

            try:
                result = await asyncio.wait_for(
                    self.agent.process_message(
                        user_message=user_message,
                        session_id=session_id,
                        user_id=session_db.user_id,
                        language=language,
                        context=context,
                        db=db,
                    ),
                    timeout=OLLAMA_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                print(f"[v0] Ollama timed out for session {session_id}")
                await websocket.send_json({
                    "type": "response",
                    "message": "Sorry, I'm taking too long to respond. Please try again.",
                    "intent": "error",
                    "confidence": 0,
                    "turn_number": 0,
                    "session_id": session_id,
                })
                return

            turn_number = len(context.get("conversation_turns", [])) + 1
            appointment_payload = result.get("appointment_data") or {}
            appointment_id = appointment_payload.get("appointment_id")

            history_entry = ConversationHistory(
                session_id=session_db.id,
                appointment_id=appointment_id,
                turn_number=turn_number,
                user_message=user_message,
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
                "user": user_message,
                "assistant": result["response"],
                "intent": result["intent"],
            })
            if len(conversation_turns) > 10:
                conversation_turns = conversation_turns[-10:]

            context["conversation_turns"] = conversation_turns
            context["intent_history"] = context.get("intent_history", []) + [result["intent"]]

            if result.get("_booking_context") is not None:
                context["booking_context"] = result["_booking_context"]
            elif result.get("appointment_data"):
                context["booking_context"] = result["appointment_data"]

            cache.store_conversation_context(session_id, context)

            response_message = {
                "type": "response",
                "message": result["response"],
                "intent": result["intent"],
                "confidence": result["confidence"],
                "turn_number": turn_number,
                "session_id": session_id,
            }

            if result.get("audio_base64"):
                response_message["audio"] = result["audio_base64"]

            if result.get("appointment_data"):
                response_message["appointment"] = result["appointment_data"]

            await websocket.send_json(response_message)
            print(
                f"[v0] Turn {turn_number} sent | session={session_id} | "
                f"intent={result['intent']} | appointment_id={appointment_id}"
            )

        except Exception as e:
            print(f"[v0] Error processing text message: {e}")
            try:
                await websocket.send_json({
                    "type": "response",
                    "message": "Something went wrong. Please try again.",
                    "intent": "error",
                    "confidence": 0,
                    "turn_number": 0,
                    "session_id": session_id,
                })
            except Exception:
                pass