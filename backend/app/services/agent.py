import os
import re
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, date, time as dt_time

from openai import OpenAI
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database.models import Appointment, AppointmentStatus, User
from app.services.voice_processor import VoiceProcessor
from app.services.appointment_extractor import AppointmentExtractor

load_dotenv()

MEDICAL_SPECIALTIES = [
    "General Medicine", "Cardiology", "Orthopedics", "Dermatology",
    "Pediatrics", "Gynecology", "ENT", "Ophthalmology",
    "Neurology", "Psychiatry", "Dental", "Physiotherapy",
]

DEFAULT_CLINIC_NAME = "Main Clinic"


class VoiceAgent:
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    def __init__(self):
        self.client = OpenAI(
            base_url=self.OLLAMA_BASE_URL,
            api_key="ollama",
        )
        self.voice_processor = VoiceProcessor()
        self.appointment_extractor = AppointmentExtractor()
        print(f"[v0] VoiceAgent initialized with Ollama model: {self.OLLAMA_MODEL}")

    async def process_message(
        self,
        user_message: str,
        session_id: str,
        user_id: int,
        language: str,
        context: Dict[str, Any],
        db: Session,
    ) -> Dict[str, Any]:
        booking_context = context.get("booking_context", {}) or {}
        conversation_history = context.get("conversation_turns", [])[-8:]

        # --- Deterministic extraction ---
        extracted = self.appointment_extractor.extract(user_message, language)
        name = self._extract_name(user_message)
        phone = self._extract_phone(user_message)
        # Extract token AFTER phone so phone digits don't get grabbed
        token_id = self._extract_appointment_id(user_message, phone)
        specialty = self._extract_specialty(user_message)

        if name:
            booking_context["patient_name"] = name
            self._update_user_name(user_id, name, db)

        if phone:
            booking_context["phone_number"] = phone
            self._update_user_phone(user_id, phone, db)

        if specialty:
            booking_context["medical_specialty"] = specialty

        if extracted.get("preferred_date"):
            booking_context["preferred_date"] = extracted["preferred_date"]

        if extracted.get("preferred_time"):
            booking_context["preferred_time"] = extracted["preferred_time"]

        if extracted.get("doctor_name"):
            booking_context["doctor_name"] = extracted["doctor_name"]

        if token_id:
            booking_context["appointment_id"] = token_id

        booking_context.setdefault("clinic_name", DEFAULT_CLINIC_NAME)

        reasoning = self._model_reasoning(
            user_message=user_message,
            language=language,
            booking_context=booking_context,
            conversation_history=conversation_history,
        )

        action = reasoning.get("action", "general")
        reply = reasoning.get("reply", "How may I help you with your appointment today?")
        appointment_data = None

        if action == "book":
            missing = self._missing_book_fields(booking_context)
            if not missing:
                appointment_data, reply = self._create_appointment(user_id, booking_context, db)
                if appointment_data:
                    booking_context.clear()
            else:
                reply = self._booking_missing_reply(reasoning, missing)

        elif action == "reschedule":
            missing = self._missing_reschedule_fields(booking_context)
            if not missing:
                appointment_data, reply = self._reschedule_appointment(booking_context, db)
                if appointment_data:
                    booking_context.clear()
            else:
                reply = self._reschedule_missing_reply(reasoning, missing)

        elif action == "cancel":
            missing = self._missing_cancel_fields(booking_context)
            if not missing:
                appointment_data, reply = self._cancel_appointment(booking_context, db)
                if appointment_data:
                    booking_context.clear()
            else:
                reply = self._cancel_missing_reply(reasoning, missing)

        audio_base64 = await self.voice_processor.synthesize_speech(reply, language=language)

        return {
            "response": reply,
            "intent": action,
            "confidence": 90,
            "appointment_data": appointment_data,
            "audio_base64": audio_base64,
            "_booking_context": booking_context,
        }

    # ------------------------------------------------------------------
    # MODEL REASONING
    # ------------------------------------------------------------------

    def _model_reasoning(
        self,
        user_message: str,
        language: str,
        booking_context: Dict[str, Any],
        conversation_history: list,
    ) -> Dict[str, Any]:
        language_names = {"en": "English", "hi": "Hindi", "ta": "Tamil"}
        lang_name = language_names.get(language, "English")

        existing_context = self._serialize_context(booking_context)
        history_text = "\n".join(
            [f"User: {t.get('user', '')}\nAssistant: {t.get('assistant', '')}" for t in conversation_history]
        ) or "No previous conversation."

        system_prompt = f"""
You are a warm clinical customer-care assistant.
Speak naturally and professionally.

Your job is to understand whether the user wants:
- book
- reschedule
- cancel
- general help

IMPORTANT:
1. Never claim an appointment is booked, rescheduled, or cancelled unless the backend confirms it.
2. If information is missing, ask naturally only for the missing information.
3. For reschedule, the user must provide:
   - full name
   - phone number
   - token ID
   - new preferred date
   - new preferred time
4. For cancel, the user must provide:
   - full name
   - phone number
   - token ID
5. Return JSON only.

Return strict JSON:
{{
  "action": "book|reschedule|cancel|general",
  "reply": "natural assistant reply",
  "needs_more_info": true,
  "missing_fields": ["field1", "field2"]
}}
Respond in {lang_name}.
"""

        user_prompt = f"""
Conversation history:
{history_text}

Known context:
{existing_context}

Latest user message:
{user_message}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=220,
            )
            raw = response.choices[0].message.content.strip()
            parsed = self._extract_json(raw)
            if parsed:
                return parsed
        except Exception as e:
            print(f"[v0] Ollama reasoning error: {e}")

        return {
            "action": "general",
            "reply": "I can help you book, reschedule, or cancel an appointment. What would you like to do?",
            "needs_more_info": True,
            "missing_fields": [],
        }

    # ------------------------------------------------------------------
    # MISSING FIELDS + SAFE REPLIES
    # ------------------------------------------------------------------

    def _missing_book_fields(self, ctx: Dict[str, Any]):
        missing = []
        if not ctx.get("patient_name"):
            missing.append("patient_name")
        if not ctx.get("phone_number"):
            missing.append("phone_number")
        if not ctx.get("medical_specialty"):
            missing.append("medical_specialty")
        if not ctx.get("preferred_date"):
            missing.append("preferred_date")
        if not ctx.get("preferred_time"):
            missing.append("preferred_time")
        # doctor_name is OPTIONAL — never blocks booking
        return missing

    def _missing_reschedule_fields(self, ctx: Dict[str, Any]):
        missing = []
        if not ctx.get("patient_name"):
            missing.append("patient_name")
        if not ctx.get("phone_number"):
            missing.append("phone_number")
        if not ctx.get("appointment_id"):
            missing.append("appointment_id")
        if not ctx.get("preferred_date"):
            missing.append("preferred_date")
        if not ctx.get("preferred_time"):
            missing.append("preferred_time")
        return missing

    def _missing_cancel_fields(self, ctx: Dict[str, Any]):
        missing = []
        if not ctx.get("patient_name"):
            missing.append("patient_name")
        if not ctx.get("phone_number"):
            missing.append("phone_number")
        if not ctx.get("appointment_id"):
            missing.append("appointment_id")
        return missing

    def _booking_missing_reply(self, reasoning: Dict[str, Any], missing: list) -> str:
        if "patient_name" in missing:
            return "Sure, I can help with that. May I know your full name?"
        if "phone_number" in missing:
            return "Thank you. Could you also share your phone number?"
        if "medical_specialty" in missing:
            return "Which medical specialty would you like to book? For example: Dental, ENT, Cardiology, or General Medicine?"
        if "preferred_date" in missing and "preferred_time" in missing:
            return "What date and time would you prefer for the appointment?"
        if "preferred_date" in missing:
            return "What date would you prefer for the appointment?"
        if "preferred_time" in missing:
            return "What time would you like for the appointment?"
        return reasoning.get("reply") or "Please share the remaining appointment details."

    def _reschedule_missing_reply(self, reasoning: Dict[str, Any], missing: list) -> str:
        auth_fields = {"patient_name", "phone_number", "appointment_id"}
        if auth_fields & set(missing):
            return "I'd be happy to help reschedule. Please share your full name, phone number, and token ID so I can verify your appointment."
        if "preferred_date" in missing and "preferred_time" in missing:
            return "Thank you, identity verified. What new date and time would you like for the appointment?"
        if "preferred_date" in missing:
            return "What new date would you like for the appointment?"
        if "preferred_time" in missing:
            return "What new time would you prefer?"
        return reasoning.get("reply") or "Please share the new date and time."

    def _cancel_missing_reply(self, reasoning: Dict[str, Any], missing: list) -> str:
        if missing:
            return "I can help with cancellation. Please share your full name, phone number, and token ID so I can verify your appointment."
        return reasoning.get("reply") or "Please share the verification details."

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def _create_appointment(self, user_id: int, ctx: Dict[str, Any], db: Session):
        appointment_dt = self._combine_date_time(ctx.get("preferred_date"), ctx.get("preferred_time"))
        if not appointment_dt:
            return None, "I could not understand the appointment date and time clearly. Could you please repeat them?"

        if appointment_dt <= datetime.now():
            return None, "That looks like a past time. Please share a future date and time."

        if not self._is_slot_available(appointment_dt, db):
            return None, "That time slot is already booked. Please choose another date or time."

        appointment_type = ctx.get("medical_specialty") or "General"
        doctor_name = ctx.get("doctor_name") or "Any Available Doctor"
        clinic_name = ctx.get("clinic_name") or DEFAULT_CLINIC_NAME

        new_appointment = Appointment(
            user_id=user_id,
            appointment_date=appointment_dt,
            appointment_type=appointment_type,
            doctor_name=doctor_name,
            clinic_name=clinic_name,
            status=AppointmentStatus.BOOKED,
            notes=f"Phone: {ctx.get('phone_number')}",
        )
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)

        data = {
            "appointment_id": new_appointment.id,
            "patient_name": ctx.get("patient_name"),
            "medical_specialty": appointment_type,
            "appointment_type": appointment_type,
            "doctor_name": doctor_name,
            "clinic_name": clinic_name,
            "appointment_date": new_appointment.appointment_date.isoformat(),
            "status": "booked",
        }

        reply = (
            f"Your appointment has been booked successfully. "
            f"Your token ID is {new_appointment.id}. "
            f"Please save it for any future changes or cancellation."
        )
        return data, reply

    def _reschedule_appointment(self, ctx: Dict[str, Any], db: Session):
        appointment = self._find_user_appointment(ctx, db)
        if not appointment:
            return None, "I could not verify the appointment with that name, phone number, and token ID. Please double-check the details."

        new_dt = self._combine_date_time(ctx.get("preferred_date"), ctx.get("preferred_time"))
        if not new_dt:
            return None, "I could not understand the new date and time clearly. Please try again."

        if new_dt <= datetime.now():
            return None, "Please choose a future date and time."

        if not self._is_slot_available(new_dt, db, exclude_appointment_id=appointment.id):
            return None, "That time slot is already booked. Please choose another one."

        old_date = appointment.appointment_date
        appointment.appointment_date = new_dt
        appointment.status = AppointmentStatus.RESCHEDULED
        db.commit()
        db.refresh(appointment)

        data = {
            "appointment_id": appointment.id,
            "patient_name": ctx.get("patient_name"),
            "appointment_type": appointment.appointment_type,
            "doctor_name": appointment.doctor_name,
            "clinic_name": appointment.clinic_name,
            "appointment_date": appointment.appointment_date.isoformat(),
            "old_date": old_date.isoformat(),
            "new_date": appointment.appointment_date.isoformat(),
            "status": "rescheduled",
        }

        reply = (
            f"Your appointment has been rescheduled successfully. "
            f"The new date is {appointment.appointment_date.strftime('%A, %d %B %Y')} "
            f"at {appointment.appointment_date.strftime('%I:%M %p')}. "
            f"Your token ID remains {appointment.id}."
        )
        return data, reply

    def _cancel_appointment(self, ctx: Dict[str, Any], db: Session):
        appointment = self._find_user_appointment(ctx, db)
        if not appointment:
            return None, "I could not verify the appointment with that name, phone number, and token ID. Please double-check the details."

        appointment.status = AppointmentStatus.CANCELLED
        db.commit()
        db.refresh(appointment)

        data = {
            "appointment_id": appointment.id,
            "patient_name": ctx.get("patient_name"),
            "appointment_type": appointment.appointment_type,
            "doctor_name": appointment.doctor_name,
            "clinic_name": appointment.clinic_name,
            "status": "cancelled",
        }

        reply = f"Your appointment with token ID {appointment.id} has been cancelled successfully."
        return data, reply

    # ------------------------------------------------------------------
    # LOOKUPS
    # ------------------------------------------------------------------

    def _find_user_appointment(self, ctx: Dict[str, Any], db: Session):
        appointment_id = ctx.get("appointment_id")
        patient_name = (ctx.get("patient_name") or "").strip().lower()
        phone_number = (ctx.get("phone_number") or "").strip()

        if not appointment_id:
            print("[v0] _find_user_appointment: no appointment_id in context")
            return None

        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            print(f"[v0] _find_user_appointment: appointment {appointment_id} not found")
            return None

        user = db.query(User).filter(User.id == appointment.user_id).first()
        if not user:
            print(f"[v0] _find_user_appointment: user not found for appointment {appointment_id}")
            return None

        name_ok = (user.name or "").strip().lower() == patient_name

        # If DB phone is a temp placeholder, update it with the real phone and allow match
        db_phone = (user.phone_number or "").strip()
        if db_phone.startswith("temp_"):
            if phone_number:
                # Check that no OTHER user owns this phone before updating
                existing = db.query(User).filter(
                    User.phone_number == phone_number,
                    User.id != user.id
                ).first()
                if not existing:
                    user.phone_number = phone_number
                    db.commit()
                    print(f"[v0] Updated temp phone for user {user.id} → {phone_number}")
                else:
                    # Phone belongs to another user — match by name only for temp users
                    print(f"[v0] Phone {phone_number} already owned by user {existing.id}, skipping update")
            phone_ok = True  # temp users: skip strict phone check
        else:
            phone_ok = db_phone == phone_number

        print(f"[v0] Auth check: name_ok={name_ok}, phone_ok={phone_ok}, db_name='{user.name}', given_name='{patient_name}'")
        return appointment if (name_ok and phone_ok) else None

    def _combine_date_time(self, preferred_date, preferred_time) -> Optional[datetime]:
        try:
            if isinstance(preferred_date, datetime):
                base_date = preferred_date.date()
            elif isinstance(preferred_date, date):
                base_date = preferred_date
            else:
                return None

            hour, minute = map(int, preferred_time.split(":"))
            return datetime.combine(base_date, dt_time(hour=hour, minute=minute))
        except Exception:
            return None

    def _is_slot_available(self, appointment_dt: datetime, db: Session, exclude_appointment_id: Optional[int] = None) -> bool:
        start = appointment_dt.replace(second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        query = db.query(Appointment).filter(
            Appointment.appointment_date >= start,
            Appointment.appointment_date < end,
            Appointment.status.in_([
                AppointmentStatus.BOOKED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.RESCHEDULED,
            ]),
        )

        if exclude_appointment_id:
            query = query.filter(Appointment.id != exclude_appointment_id)

        return query.first() is None

    # ------------------------------------------------------------------
    # EXTRACTION HELPERS
    # ------------------------------------------------------------------

    def _extract_name(self, message: str) -> Optional[str]:
        msg = message.strip()
        msg_lower = msg.lower().strip()

        blocked = {
            "hi", "hello", "hi hello", "hey", "thanks", "thank you", "ok", "okay",
            "yes", "no", "book", "appointment", "cancel", "reschedule",
        }
        if msg_lower in blocked:
            return None

        patterns = [
            r"(?:my name is|my full name is|i am|i'm|this is|name(?:\s*:)?\s*)\s+([A-Za-z][A-Za-z\s]{1,60}?)(?:\s*,|\s*my|\s*phone|\s*token|\s*and|\s*$)",
            r"(?:my name is|my full name is|i am|i'm|this is)\s+([A-Za-z][A-Za-z\s]{1,60})",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]*){1,2})$",
        ]

        for pat in patterns:
            m = re.search(pat, msg, re.IGNORECASE)
            if m:
                name = m.group(1).strip().rstrip(",")
                words = [w for w in name.split() if w.strip()]
                if 1 <= len(words) <= 4:
                    return " ".join(w.capitalize() for w in words)
        return None

    def _normalize_spoken_digits(self, text: str) -> str:
        """Convert spoken numbers to digits. Handles 'double X' and word digits."""
        t = text.lower()

        # Handle "double X" FIRST (before single replacements)
        double_map = {
            "double zero": "00",
            "double one": "11",
            "double two": "22",
            "double three": "33",
            "double four": "44",
            "double five": "55",
            "double six": "66",
            "double seven": "77",
            "double eight": "88",
            "double nine": "99",
        }
        for k, v in double_map.items():
            t = t.replace(k, v)

        # Single word-digits — exact word boundaries only
        # DO NOT include "line", "light" or other ambiguous words
        single_map = {
            "zero": "0",
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
        }
        for k, v in single_map.items():
            t = re.sub(rf"\b{k}\b", v, t)

        return t

    def _extract_phone(self, message: str) -> Optional[str]:
        normalized = self._normalize_spoken_digits(message)
        # Match Indian mobile numbers: starts with 6-9, 10 digits
        m = re.search(r"\b(?:\+91[-\s]?)?([6-9]\d{9})\b", normalized)
        if not m:
            return None
        digits = re.sub(r"\D", "", m.group(0))
        return digits[-10:]  # Last 10 digits

    def _extract_appointment_id(self, message: str, phone: Optional[str] = None) -> Optional[int]:
        """
        Extract token/appointment ID.
        Priority: explicit keyword form first.
        Falls back to bare short number ONLY if no phone-like digits detected.
        """
        # 1. Explicit keyword: "token 15", "token id 15", "appointment id 15", "token id: 15"
        m = re.search(
            r"\b(?:token(?:\s*id)?|appointment(?:\s*id)?)\s*(?:is\s*|:\s*)?(\d{1,6})\b",
            message, re.IGNORECASE
        )
        if m:
            return int(m.group(1))

        # 2. Bare short number (1-4 digits) — only if no phone number was found
        if not phone:
            m = re.search(r"\b(\d{1,4})\b", message)
            if m:
                candidate = int(m.group(1))
                # Sanity: don't treat year-like numbers as token IDs
                if candidate < 9000:
                    return candidate

        return None

    def _extract_specialty(self, message: str) -> Optional[str]:
        msg = message.lower()
        aliases = {
            "dentist": "Dental",
            "dental": "Dental",
            "tooth": "Dental",
            "teeth": "Dental",
            "ent": "ENT",
            "ear": "ENT",
            "nose": "ENT",
            "throat": "ENT",
            "skin": "Dermatology",
            "heart": "Cardiology",
            "cardio": "Cardiology",
            "eye": "Ophthalmology",
            "vision": "Ophthalmology",
            "general": "General Medicine",
            "child": "Pediatrics",
            "children": "Pediatrics",
            "pediatric": "Pediatrics",
            "bone": "Orthopedics",
            "ortho": "Orthopedics",
            "neuro": "Neurology",
            "brain": "Neurology",
            "mental": "Psychiatry",
            "physio": "Physiotherapy",
            "gynec": "Gynecology",
            "women": "Gynecology",
        }

        for key, val in aliases.items():
            if key in msg:
                return val

        for spec in MEDICAL_SPECIALTIES:
            if spec.lower() in msg:
                return spec
        return None

    def _update_user_name(self, user_id: int, name: str, db: Session):
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user and name:
                user.name = name
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"[v0] _update_user_name error: {e}")

    def _update_user_phone(self, user_id: int, phone_number: str, db: Session):
        """Update user phone only if the new number isn't already taken by another user."""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not phone_number:
                return

            # Already has this number — nothing to do
            if user.phone_number == phone_number:
                return

            # Check if another user already owns this phone
            existing = db.query(User).filter(
                User.phone_number == phone_number,
                User.id != user_id
            ).first()

            if existing:
                print(f"[v0] Phone {phone_number} already owned by user {existing.id}, skipping update for user {user_id}")
                # Still store it in booking context — auth will match via that user
                return

            user.phone_number = phone_number
            db.commit()
            print(f"[v0] Updated phone for user {user_id} → {phone_number}")
        except Exception as e:
            db.rollback()
            print(f"[v0] _update_user_phone error: {e}")

    def _serialize_context(self, ctx: Dict[str, Any]) -> str:
        clean = {}
        for k, v in ctx.items():
            clean[k] = v.isoformat() if isinstance(v, datetime) else v
        return json.dumps(clean, ensure_ascii=False)

    def _extract_json(self, raw: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw)
        except Exception:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
        return None