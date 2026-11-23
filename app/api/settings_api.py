"""Business settings (admin only for changes; staff can read)."""

from __future__ import annotations

from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import FAQ, BusinessConfig, Holiday, OpeningHours, Service, Staff, User
from app.schemas import (
    BusinessIn,
    BusinessOut,
    FaqIn,
    FaqOut,
    HolidayIn,
    HolidayOut,
    HoursIn,
    HoursOut,
    ServiceIn,
    ServiceOut,
    StaffIn,
    StaffOut,
)
from app.security import current_user, require_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])


def no_deletes_in_demo(settings: Settings = Depends(get_settings)) -> None:
    if settings.demo_mode:
        raise HTTPException(403, "Deleting is disabled in the public demo")


def _service_out(s: Service) -> ServiceOut:
    out = ServiceOut.model_validate(s)
    out.staff_ids = [m.id for m in s.staff]
    return out


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That name or value already exists") from exc


# ---------------------------------------------------------------- business


@router.get("/business", response_model=BusinessOut)
def get_business(db: Session = Depends(get_db), _: User = Depends(current_user)) -> BusinessConfig:
    biz = db.get(BusinessConfig, 1)
    if biz is None:
        raise HTTPException(404, "Not configured")
    return biz


@router.put("/business", response_model=BusinessOut)
def put_business(
    body: BusinessIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> BusinessConfig:
    if body.timezone not in available_timezones():
        raise HTTPException(422, "Unknown time zone")
    biz = db.get(BusinessConfig, 1) or BusinessConfig(id=1)
    for k, v in body.model_dump().items():
        setattr(biz, k, v)
    db.add(biz)
    _commit(db)
    return biz


# ---------------------------------------------------------------- services


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db), _: User = Depends(current_user)
) -> list[ServiceOut]:
    return [_service_out(s) for s in db.scalars(select(Service).order_by(Service.id))]


def _apply_service(db: Session, svc: Service, body: ServiceIn) -> None:
    for k, v in body.model_dump(exclude={"staff_ids"}).items():
        setattr(svc, k, v)
    svc.staff = list(db.scalars(select(Staff).where(Staff.id.in_(body.staff_ids))))


@router.post("/services", response_model=ServiceOut, status_code=201)
def create_service(
    body: ServiceIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> ServiceOut:
    svc = Service()
    _apply_service(db, svc, body)
    db.add(svc)
    _commit(db)
    return _service_out(svc)


@router.put("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    body: ServiceIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> ServiceOut:
    svc = db.get(Service, service_id)
    if svc is None:
        raise HTTPException(404, "Service not found")
    _apply_service(db, svc, body)
    _commit(db)
    return _service_out(svc)


@router.delete(
    "/services/{service_id}", status_code=204, dependencies=[Depends(no_deletes_in_demo)]
)
def delete_service(
    service_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> None:
    svc = db.get(Service, service_id)
    if svc is not None:
        svc.active = False  # soft delete: past appointments keep their service
        db.commit()


# ---------------------------------------------------------------- staff


@router.get("/staff", response_model=list[StaffOut])
def list_staff(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Staff]:
    return list(db.scalars(select(Staff).order_by(Staff.id)))


@router.post("/staff", response_model=StaffOut, status_code=201)
def create_staff(
    body: StaffIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> Staff:
    s = Staff(**body.model_dump())
    db.add(s)
    _commit(db)
    return s


@router.put("/staff/{staff_id}", response_model=StaffOut)
def update_staff(
    staff_id: int, body: StaffIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> Staff:
    s = db.get(Staff, staff_id)
    if s is None:
        raise HTTPException(404, "Staff not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    _commit(db)
    return s


# ---------------------------------------------------------------- hours & holidays


@router.get("/hours", response_model=list[HoursOut])
def list_hours(
    db: Session = Depends(get_db), _: User = Depends(current_user)
) -> list[OpeningHours]:
    return list(
        db.scalars(select(OpeningHours).order_by(OpeningHours.weekday, OpeningHours.open_time))
    )


@router.put("/hours", response_model=list[HoursOut])
def put_hours(
    body: list[HoursIn], db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[OpeningHours]:
    for h in body:
        if h.close_time <= h.open_time:
            raise HTTPException(422, "Closing time must be after opening time")
    db.execute(delete(OpeningHours))
    rows = [OpeningHours(**h.model_dump()) for h in body]
    db.add_all(rows)
    _commit(db)
    return list(
        db.scalars(select(OpeningHours).order_by(OpeningHours.weekday, OpeningHours.open_time))
    )


@router.get("/holidays", response_model=list[HolidayOut])
def list_holidays(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[Holiday]:
    return list(db.scalars(select(Holiday).order_by(Holiday.date)))


@router.post("/holidays", response_model=HolidayOut, status_code=201)
def add_holiday(
    body: HolidayIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> Holiday:
    h = Holiday(**body.model_dump())
    db.add(h)
    _commit(db)
    return h


@router.delete(
    "/holidays/{holiday_id}", status_code=204, dependencies=[Depends(no_deletes_in_demo)]
)
def delete_holiday(
    holiday_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> None:
    db.execute(delete(Holiday).where(Holiday.id == holiday_id))
    db.commit()


# ---------------------------------------------------------------- FAQs


@router.get("/faqs", response_model=list[FaqOut])
def list_faqs(db: Session = Depends(get_db), _: User = Depends(current_user)) -> list[FAQ]:
    return list(db.scalars(select(FAQ).order_by(FAQ.id)))


@router.post("/faqs", response_model=FaqOut, status_code=201)
def create_faq(body: FaqIn, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> FAQ:
    f = FAQ(**body.model_dump())
    db.add(f)
    _commit(db)
    return f


@router.put("/faqs/{faq_id}", response_model=FaqOut)
def update_faq(
    faq_id: int, body: FaqIn, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> FAQ:
    f = db.get(FAQ, faq_id)
    if f is None:
        raise HTTPException(404, "FAQ not found")
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    _commit(db)
    return f


@router.delete("/faqs/{faq_id}", status_code=204, dependencies=[Depends(no_deletes_in_demo)])
def delete_faq(
    faq_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> None:
    db.execute(delete(FAQ).where(FAQ.id == faq_id))
    db.commit()
