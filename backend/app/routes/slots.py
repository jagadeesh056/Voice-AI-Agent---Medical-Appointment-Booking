from datetime import datetime, date, timedelta, time as dt_time
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Appointment, AppointmentStatus

router = APIRouter()

_SLOT_START = dt_time(9, 0)
_SLOT_END = dt_time(17, 0)
_SLOT_MINUTES = 30


def _generate_daily_slots(for_date: date) -> List[datetime]:
    slots = []
    current = datetime.combine(for_date, _SLOT_START)
    end = datetime.combine(for_date, _SLOT_END)
    while current < end:
        slots.append(current)
        current += timedelta(minutes=_SLOT_MINUTES)
    return slots


def _round_to_slot(dt: datetime) -> datetime:
    minute = (dt.minute // _SLOT_MINUTES) * _SLOT_MINUTES
    return dt.replace(minute=minute, second=0, microsecond=0)


@router.get("/")
def get_slots(
    query_date: Optional[str] = Query(None, alias="date"),
    db: Session = Depends(get_db),
):
    if query_date:
        try:
            target_date = date.fromisoformat(query_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    else:
        target_date = date.today()

    if target_date < date.today():
        return {
            "date": target_date.isoformat(),
            "day_label": target_date.strftime("%A, %d %B %Y"),
            "total_slots": 0,
            "available_count": 0,
            "booked_count": 0,
            "slots": [],
            "message": "Past dates are not available for booking."
        }

    slot_starts = _generate_daily_slots(target_date)

    day_start = datetime.combine(target_date, dt_time.min)
    day_end = datetime.combine(target_date, dt_time.max)

    booked_apts = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date >= day_start,
            Appointment.appointment_date <= day_end,
            Appointment.status.in_([
                AppointmentStatus.BOOKED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.RESCHEDULED,
            ]),
        )
        .all()
    )

    booked_map = {}
    for apt in booked_apts:
        booked_map[_round_to_slot(apt.appointment_date)] = apt

    now = datetime.now()
    result = []

    for slot_dt in slot_starts:
        apt = booked_map.get(slot_dt)
        is_past = slot_dt < now
        is_available = (not is_past) and (apt is None)

        slot_info = {
            "datetime": slot_dt.isoformat(),
            "time": slot_dt.strftime("%H:%M"),
            "label": slot_dt.strftime("%I:%M %p").lstrip("0"),
            "available": is_available,
            "past": is_past,
        }

        if apt:
            slot_info["appointment"] = {
                "id": apt.id,
                "appointment_type": apt.appointment_type,
                "doctor_name": apt.doctor_name,
                "clinic_name": apt.clinic_name,
                "status": str(apt.status),
            }

        result.append(slot_info)

    return {
        "date": target_date.isoformat(),
        "day_label": target_date.strftime("%A, %d %B %Y"),
        "total_slots": len(result),
        "available_count": sum(1 for s in result if s["available"]),
        "booked_count": sum(1 for s in result if "appointment" in s),
        "slots": result,
    }