"""HTTP-level integration tests: auth, CSRF, roles, agent endpoints, dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models import Call, Job, TranscriptTurn
from tests.conftest import login

pytestmark = pytest.mark.integration


def test_health_and_ready(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] == "ok"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers.get("X-Request-ID")


def test_login_csrf_and_roles(client, admin) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/me").status_code == 401
    bad = client.post("/api/auth/login", json={"email": admin["email"], "password": "wrong-pass"})
    assert bad.status_code == 401
    raw = client.post(
        "/api/auth/login", json={"email": admin["email"], "password": admin["password"]}
    )
    cookies = raw.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("rcp_session="))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    headers = {"X-CSRF-Token": raw.json()["csrf_token"]}
    assert client.get("/api/me").json()["role"] == "admin"
    biz = client.get("/api/settings/business").json()
    # State change without CSRF header is refused.
    assert client.put("/api/settings/business", json=biz).status_code == 403
    biz["greeting"] = "Hello from Luma, Ava speaking."
    r = client.put("/api/settings/business", json=biz, headers=headers)
    assert r.status_code == 200 and r.json()["greeting"].startswith("Hello from Luma")
    client.post("/api/auth/logout", headers=headers)
    assert client.get("/api/me").status_code == 401

    staff_headers = login(client, "staff@luma.example.com", "correct-horse-staple")
    assert client.put("/api/settings/business", json=biz, headers=staff_headers).status_code == 403
    assert client.get("/api/calls").status_code == 200


def test_login_rate_limited(client, admin) -> None:  # type: ignore[no-untyped-def]
    codes = [
        client.post(
            "/api/auth/login", json={"email": admin["email"], "password": "wrong-password"}
        ).status_code
        for _ in range(12)
    ]
    assert codes[-1] == 429


def test_agent_endpoints_require_service_token(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/agent/calls/start", json={"channel": "web", "room_name": "r"})
    assert r.status_code == 401
    r = client.post(
        "/api/agent/calls/start",
        json={"channel": "web", "room_name": "r"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_full_call_lifecycle(client, db, agent_headers, admin) -> None:  # type: ignore[no-untyped-def]
    start = client.post(
        "/api/agent/calls/start",
        json={"channel": "phone", "room_name": "sip-1", "caller_number": "+923001112233"},
        headers=agent_headers,
    )
    assert start.status_code == 200
    body = start.json()
    assert body["allowed"] and "Luma Hair Studio" in body["greeting"]
    assert "may be recorded and transcribed" in body["greeting"]
    assert "Never invent a time" in body["instructions"]
    call_id = body["call_id"]

    avail = client.post(
        "/api/agent/tools/check_availability",
        headers=agent_headers,
        json={"call_id": call_id, "args": {"service": "Haircut", "date_from": "tomorrow"}},
    ).json()
    assert avail["status"] == "ok"
    slot = avail["data"]["slots"][0]
    booked = client.post(
        "/api/agent/tools/book_appointment",
        headers=agent_headers,
        json={
            "call_id": call_id,
            "args": {
                "slot_id": slot["slot_id"],
                "service": "Haircut",
                "customer_name": "Ayesha Khan",
                "email": "ayesha.k@example.com",
                "caller_confirmed": True,
            },
        },
    ).json()
    assert booked["status"] == "ok", booked

    now = datetime.now(UTC)
    end = client.post(
        f"/api/agent/calls/{call_id}/end",
        headers=agent_headers,
        json={
            "ended_at": (now + timedelta(seconds=95)).isoformat(),
            "turns": [
                {"speaker": "agent", "text": body["greeting"], "ts": now.isoformat()},
                {
                    "speaker": "caller",
                    "text": "I'd like a haircut tomorrow",
                    "ts": (now + timedelta(seconds=5)).isoformat(),
                },
            ],
            "latency_ms": [610, 700, 540, 1200],
            "interruptions": 1,
            "audio_input_tokens": 3000,
            "audio_output_tokens": 2000,
        },
    )
    assert end.status_code == 200
    # Ending twice is harmless.
    again = client.post(
        f"/api/agent/calls/{call_id}/end", headers=agent_headers, json={"ended_at": now.isoformat()}
    )
    assert again.json()["status"] == "ended"
    assert db.scalar(select(func.count(TranscriptTurn.id))) == 2
    assert db.scalar(select(func.count(Job.id)).where(Job.kind == "post_call")) == 1

    # Run the post-call job and check the dashboard shows everything.
    from app.jobs.worker import Worker

    w = Worker()
    while w.run_once():
        pass
    headers = login(client, admin["email"], admin["password"])
    detail = client.get(f"/api/calls/{call_id}", headers=headers).json()
    assert detail["outcome"] == "booked"
    assert detail["summary"]
    assert detail["latency_p50_ms"] in range(600, 700)
    assert [t["tool"] for t in detail["tool_calls"]] == ["check_availability", "book_appointment"]
    assert detail["appointments"][0]["service"] == "Haircut"
    assert "•" in detail["caller"]  # caller number masked
    listing = client.get("/api/calls?outcome=booked").json()
    assert listing["total"] == 1 and listing["counts"]["booked"] == 1
    stats = client.get("/api/stats/overview").json()
    assert stats["calls"] == 1 and stats["appointments_booked"] == 1


def test_demo_daily_cap_and_busy(client, db, agent_headers, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", True)
    monkeypatch.setattr(s, "demo_daily_calls", 2)
    for i in range(2):
        db.add(
            Call(channel="web", room_name=f"r{i}", started_at=datetime.now(UTC), status="processed")
        )
    db.commit()
    r = client.post(
        "/api/agent/calls/start", json={"channel": "web", "room_name": "x"}, headers=agent_headers
    ).json()
    assert r["allowed"] is False and r["reason"] == "daily_demo_cap"
    tok = client.post("/api/web-call/token")
    assert tok.status_code == 503
    # Demo calls are capped at 3 minutes.
    assert s.effective_max_call_minutes == 3


def test_web_call_token_is_room_limited(client) -> None:  # type: ignore[no-untyped-def]
    import jwt  # PyJWT comes with livekit-api

    r = client.post("/api/web-call/token")
    assert r.status_code == 200, r.text
    body = r.json()
    claims = jwt.decode(body["token"], options={"verify_signature": False})
    assert claims["video"]["room"] == body["room"]
    assert claims["video"]["roomJoin"] is True
    assert not claims["video"].get("roomAdmin")
    assert claims["exp"] - claims["nbf"] <= 600
    assert claims["roomConfig"]["agents"][0]["agentName"] == "luma-receptionist"


def test_settings_crud_and_demo_delete_guard(client, admin, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    headers = login(client, admin["email"], admin["password"])
    r = client.post(
        "/api/settings/faqs",
        headers=headers,
        json={"question": "Do you do bridal hair?", "answer": "Yes, by appointment."},
    )
    assert r.status_code == 201
    faq_id = r.json()["id"]
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_mode", True)
    assert client.delete(f"/api/settings/faqs/{faq_id}", headers=headers).status_code == 403
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert client.delete(f"/api/settings/faqs/{faq_id}", headers=headers).status_code == 204
    bad_hours = [{"weekday": 0, "open_time": "18:00", "close_time": "10:00"}]
    assert client.put("/api/settings/hours", headers=headers, json=bad_hours).status_code == 422
