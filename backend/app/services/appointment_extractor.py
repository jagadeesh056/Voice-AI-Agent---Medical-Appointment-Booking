import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Any


class AppointmentExtractor:
    def __init__(self):
        self.appointment_types = [
            "consultation",
            "follow-up",
            "checkup",
            "physical",
            "dental",
            "eye",
            "skin",
            "general",
            "specialist",
            "surgery",
            "treatment",
        ]
        print("[v0] AppointmentExtractor initialized")

    def extract(self, message: str, language: str = "en") -> Dict[str, Any]:
        message_lower = message.lower().strip()
        extracted = {
            "appointment_type": None,
            "doctor_name": None,
            "clinic_name": None,
            "preferred_date": None,
            "preferred_time": None,
            "extracted_fields": [],
        }

        apt_type = self._extract_appointment_type(message_lower)
        if apt_type:
            extracted["appointment_type"] = apt_type
            extracted["extracted_fields"].append("appointment_type")

        doctor = self._extract_doctor_name(message)
        if doctor:
            extracted["doctor_name"] = doctor
            extracted["extracted_fields"].append("doctor_name")

        clinic = self._extract_clinic_name(message)
        if clinic:
            extracted["clinic_name"] = clinic
            extracted["extracted_fields"].append("clinic_name")

        date_obj = self._extract_date(message_lower)
        if date_obj:
            extracted["preferred_date"] = date_obj
            extracted["extracted_fields"].append("preferred_date")

        time_str = self._extract_time(message_lower)
        if time_str:
            extracted["preferred_time"] = time_str
            extracted["extracted_fields"].append("preferred_time")

        return extracted

    def _extract_appointment_type(self, message: str) -> Optional[str]:
        for apt_type in self.appointment_types:
            if apt_type in message:
                return apt_type

        if re.search(r"\b(consultation|visit|appointment|meet doctor|see doctor)\b", message):
            return "consultation"

        return None

    def _extract_doctor_name(self, message: str) -> Optional[str]:
        patterns = [
            r"(?:with\s+)?(?:dr|doctor)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1).strip()
        return None

    def _extract_clinic_name(self, message: str) -> Optional[str]:
        return None

    def _extract_date(self, message: str) -> Optional[datetime]:
        now = datetime.now()

        if "today" in message:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)

        if "tomorrow" in message:
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        if "day after tomorrow" in message:
            return (now + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

        if "next week" in message:
            return (now + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

        month_map = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        # 26th April 2026 / 26 April / 26th of April
        m = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?\s+"
            r"(january|february|march|april|may|june|july|august|september|october|november|december)"
            r"(?:\s+(\d{4}))?\b",
            message,
            re.IGNORECASE,
        )
        if m:
            day = int(m.group(1))
            month = month_map[m.group(2).lower()]
            year = int(m.group(3)) if m.group(3) else now.year
            try:
                return datetime(year, month, day)
            except ValueError:
                return None

        # dd/mm/yyyy or dd-mm-yyyy
        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", message)
        if m:
            day, month, year = map(int, m.groups())
            try:
                return datetime(year, month, day)
            except ValueError:
                return None

        # yyyy-mm-dd
        m = re.search(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b", message)
        if m:
            year, month, day = map(int, m.groups())
            try:
                return datetime(year, month, day)
            except ValueError:
                return None

        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        for day_name, day_num in weekdays.items():
            if re.search(rf"\b{day_name}\b", message):
                days_ahead = (day_num - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                return (now + timedelta(days=days_ahead)).replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

        return None

    def _extract_time(self, message: str) -> Optional[str]:
        # HH:MM
        match = re.search(r"\b(\d{1,2}):(\d{2})\b", message)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

        # 4 pm / 4:30 pm / 4 p.m.
        match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b",
            message,
            re.IGNORECASE,
        )
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            ampm = match.group(3).lower().replace(".", "")

            if not (1 <= hour <= 12 and 0 <= minute <= 59):
                return None

            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:{minute:02d}"

        # common natural times
        natural_times = {
            "morning": "10:00",
            "afternoon": "14:00",
            "evening": "17:00",
            "noon": "12:00",
        }
        for phrase, normalized in natural_times.items():
            if re.search(rf"\b{phrase}\b", message):
                return normalized

        return None