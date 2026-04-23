from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User, Appointment, AppointmentStatus
from app.schemas.voice_schemas import UserCreate, UserResponse
from app.cache.redis_handler import cache

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────
# GET all users  (new admin endpoint)
# ──────────────────────────────────────────────────────────────────────────
@router.get("/")
async def get_all_users(db: Session = Depends(get_db)):
    """
    Return every registered user with appointment summary.
    Useful for admin dashboards and debugging.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        apts  = db.query(Appointment).filter(Appointment.user_id == u.id).all()
        total = len(apts)
        active = sum(
            1 for a in apts
            if a.status in (AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED)
        )
        latest = (
            max(apts, key=lambda a: a.appointment_date).appointment_date
            if apts else None
        )
        result.append({
            "user_id":             u.id,
            "name":                u.name,
            "phone_number":        u.phone_number,
            "email":               u.email,
            "language_preference": u.language_preference,
            "status":              u.status,
            "created_at":          u.created_at,
            "appointment_summary": {
                "total":            total,
                "active":           active,
                "latest_date":      latest,
            },
        })
    return result


# ──────────────────────────────────────────────────────────────────────────
# Standard CRUD
# ──────────────────────────────────────────────────────────────────────────
@router.post("/", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone_number == user_data.phone_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists",
        )
    new_user = User(
        phone_number=user_data.phone_number,
        name=user_data.name,
        email=user_data.email,
        language_preference=user_data.language_preference,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    print(f"[v0] New user created: {new_user.id}")
    return new_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    cached = cache.get_cached_user(user_id)
    if cached:
        return cached

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_dict = {
        "id":                  user.id,
        "phone_number":        user.phone_number,
        "name":                user.name,
        "email":               user.email,
        "language_preference": user.language_preference,
        "created_at":          user.created_at.isoformat(),
    }
    cache.cache_user_data(user_id, user_dict)
    return user

@router.get("/phone/{phone_number}", response_model=UserResponse)
async def get_user_by_phone(phone_number: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user