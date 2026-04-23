from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class AppointmentStatus(str, enum.Enum):
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True, nullable=True)
    language_preference = Column(String(10), default="en")  # en, hi, ta
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="user")
    sessions = relationship("ConversationSession", back_populates="user")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    appointment_date = Column(DateTime)
    appointment_type = Column(String(100))  # consultation, follow-up, checkup, etc.
    doctor_name = Column(String(255))
    clinic_name = Column(String(255))
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.BOOKED)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="appointments")
    history = relationship("ConversationHistory", back_populates="appointment")


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    session_token = Column(String(255), unique=True, index=True)
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    history = relationship("ConversationHistory", back_populates="session")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id"), index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    turn_number = Column(Integer)
    user_message = Column(Text)
    assistant_message = Column(Text)
    intent = Column(String(100), nullable=True)  # book, reschedule, cancel, query, etc.
    confidence_score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ConversationSession", back_populates="history")
    appointment = relationship("Appointment", back_populates="history")
