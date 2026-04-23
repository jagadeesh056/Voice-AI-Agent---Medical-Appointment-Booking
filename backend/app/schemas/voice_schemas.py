from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    phone_number: str
    name: str
    email: Optional[str] = None
    language_preference: str = "en"


class UserResponse(BaseModel):
    id: int
    phone_number: str
    name: str
    email: Optional[str]
    language_preference: str
    created_at: datetime

    class Config:
        from_attributes = True


class AppointmentBase(BaseModel):
    appointment_date: datetime
    appointment_type: str
    doctor_name: str
    clinic_name: str
    notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(BaseModel):
    appointment_date: Optional[datetime] = None
    appointment_type: Optional[str] = None
    doctor_name: Optional[str] = None
    clinic_name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class AppointmentResponse(AppointmentBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationHistoryEntry(BaseModel):
    turn_number: int
    user_message: str
    assistant_message: str
    intent: Optional[str] = None
    confidence_score: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionStartRequest(BaseModel):
    phone_number: Optional[str] = None
    name: Optional[str] = None
    language: str = "en"


class SessionStartResponse(BaseModel):
    session_id: str
    user_id: int
    language: str
    message: str


class AudioChunkRequest(BaseModel):
    session_id: str
    audio_data: str  # Base64 encoded audio


class VoiceMessageRequest(BaseModel):
    session_id: str
    user_message: str
    language: Optional[str] = None


class VoiceMessageResponse(BaseModel):
    session_id: str
    turn_number: int
    user_message: str
    assistant_message: str
    intent: str
    confidence_score: int
    audio_base64: Optional[str] = None  # TTS audio
    appointment_data: Optional[dict] = None


class ConversationContextUpdate(BaseModel):
    session_id: str
    user_message: str
    assistant_message: str
    intent: str
    confidence_score: int


class AppointmentIntentData(BaseModel):
    action: str  # book, reschedule, cancel, query
    appointment_date: Optional[datetime] = None
    appointment_type: Optional[str] = None
    doctor_name: Optional[str] = None
    clinic_name: Optional[str] = None
    appointment_id: Optional[int] = None


class SessionEndRequest(BaseModel):
    session_id: str
    end_reason: str = "user_ended"


class HealthCheckResponse(BaseModel):
    status: str
    database: str
    redis: str
    timestamp: datetime
