from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database.connection import get_db
from app.database.models import Appointment, User, AppointmentStatus
from app.schemas.voice_schemas import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)

router = APIRouter()


class AuthVerifyRequest(BaseModel):
    patient_name: str
    phone_number: str
    appointment_id: int


class AuthVerifyResponse(BaseModel):
    verified: bool
    message: str
    appointment_id: Optional[int] = None
    patient_name: Optional[str] = None


@router.post("/verify-auth", response_model=AuthVerifyResponse)
async def verify_appointment_auth(
    body: AuthVerifyRequest,
    db: Session = Depends(get_db),
):
    apt = db.query(Appointment).filter(Appointment.id == body.appointment_id).first()
    if not apt:
        return AuthVerifyResponse(
            verified=False,
            message=f"Appointment ID {body.appointment_id} not found.",
        )

    user = db.query(User).filter(User.id == apt.user_id).first()
    if not user:
        return AuthVerifyResponse(
            verified=False,
            message="User not found.",
        )

    name_match = (user.name or "").strip().lower() == body.patient_name.strip().lower()
    phone_match = (user.phone_number or "").strip() == body.phone_number.strip()

    if not name_match or not phone_match:
        return AuthVerifyResponse(
            verified=False,
            message="Name or phone number does not match the appointment record.",
        )

    return AuthVerifyResponse(
        verified=True,
        message="Identity verified successfully.",
        appointment_id=apt.id,
        patient_name=user.name,
    )


@router.post("/", response_model=AppointmentResponse)
async def create_appointment(
    user_id: int,
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_appointment = Appointment(
        user_id=user_id,
        appointment_date=appointment_data.appointment_date,
        appointment_type=appointment_data.appointment_type,
        doctor_name=appointment_data.doctor_name,
        clinic_name=appointment_data.clinic_name,
        notes=appointment_data.notes,
        status=AppointmentStatus.BOOKED,
    )
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)
    print(f"[v0] Appointment created: {new_appointment.id} for user {user_id}")
    return new_appointment


@router.get("/all")
async def get_all_appointments(db: Session = Depends(get_db)):
    apts = db.query(Appointment).order_by(Appointment.created_at.desc()).all()
    return [
        {
            "appointment_id": apt.id,
            "patient_name": apt.user.name if apt.user else "Unknown",
            "phone_number": apt.user.phone_number if apt.user else None,
            "appointment_date": apt.appointment_date,
            "appointment_type": apt.appointment_type,
            "doctor_name": apt.doctor_name,
            "clinic_name": apt.clinic_name,
            "status": apt.status,
            "created_at": apt.created_at,
        }
        for apt in apts
    ]


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


@router.get("/user/{user_id}")
async def get_user_appointments(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    appointments = db.query(Appointment).filter(Appointment.user_id == user_id).all()
    return [
        {
            "id": apt.id,
            "appointment_date": apt.appointment_date,
            "appointment_type": apt.appointment_type,
            "doctor_name": apt.doctor_name,
            "clinic_name": apt.clinic_name,
            "status": apt.status,
            "created_at": apt.created_at,
        }
        for apt in appointments
    ]


@router.put("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: int,
    update_data: AppointmentUpdate,
    patient_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if patient_name or phone_number:
        user = db.query(User).filter(User.id == appointment.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if (user.name or "").strip().lower() != (patient_name or "").strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Name does not match appointment record.",
            )

        if (user.phone_number or "").strip() != (phone_number or "").strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Phone number does not match appointment record.",
            )

    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(appointment, field, value)

    db.commit()
    db.refresh(appointment)
    print(f"[v0] Appointment {appointment_id} updated")
    return appointment


@router.delete("/{appointment_id}")
async def cancel_appointment(
    appointment_id: int,
    patient_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    db: Session = Depends(get_db),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    if patient_name or phone_number:
        user = db.query(User).filter(User.id == appointment.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if (user.name or "").strip().lower() != (patient_name or "").strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Name does not match appointment record.",
            )

        if (user.phone_number or "").strip() != (phone_number or "").strip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Phone number does not match appointment record.",
            )

    appointment.status = AppointmentStatus.CANCELLED
    db.commit()
    db.refresh(appointment)

    print(f"[v0] Appointment {appointment_id} cancelled")
    return {
        "status": "cancelled",
        "appointment_id": appointment_id,
        "message": "Appointment cancelled successfully.",
    }