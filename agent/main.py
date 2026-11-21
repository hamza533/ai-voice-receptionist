"""LiveKit voice agent: speech-to-speech with Gemini Live, tools served by the API.

Run locally against LiveKit Cloud:   python -m agent.main dev
Production worker:                    python -m agent.main start

The agent is deliberately thin: it relays the conversation, calls the API's tools and
reports the transcript and latency at the end. Every business rule lives in the API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Literal

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    RunContext,
    cli,
    function_tool,
)
from livekit.agents.llm import ChatMessage
from livekit.plugins import google

from agent.api_client import ApiClient

log = logging.getLogger("agent")

AGENT_NAME = os.environ.get("LIVEKIT_AGENT_NAME", "luma-receptionist")
VOICE_MODEL = os.environ.get("VOICE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025")
BUSY_LINE = (
    "Sorry, the receptionist is busy right now. Please try again in a minute. Goodbye."
)


class CallState:
    def __init__(self, call_id: str) -> None:
        self.call_id = call_id
        self.turns: list[dict[str, Any]] = []
        self.latencies_ms: list[int] = []
        self.interruptions = 0
        self.end_reason = "hangup"
        self.transfer_to: str | None = None
        self.ended = False


def _result(res: dict[str, Any]) -> str:
    """What the model sees: status, instruction and data (no ids it should read out)."""
    return json.dumps(
        {"status": res.get("status"), "instruction": res.get("message"), "data": res.get("data")},
        ensure_ascii=False,
    )


class Receptionist(Agent):
    def __init__(self, instructions: str, api: ApiClient, state: CallState, ctx: JobContext):
        super().__init__(instructions=instructions)
        self.api = api
        self.state = state
        self.job_ctx = ctx

    async def _tool(self, name: str, args: dict[str, Any]) -> str:
        args = {k: v for k, v in args.items() if v is not None}
        res = await self.api.tool(self.state.call_id, name, args)
        await self._publish(name, str(res.get("status", "error")))
        return _result(res)

    async def _publish(self, tool: str, status: str) -> None:
        """Tell the web caller's UI what the receptionist is doing (no personal data)."""
        try:
            await self.job_ctx.room.local_participant.publish_data(
                json.dumps({"tool": tool, "status": status}).encode(),
                topic="receptionist.events",
                reliable=True,
            )
        except Exception:
            log.debug("could not publish tool event", exc_info=True)

    @function_tool()
    async def get_business_info(
        self,
        context: RunContext,
        topic: Literal["all", "hours", "address", "services", "staff", "contact"] = "all",
    ) -> str:
        """Opening hours, address, services with prices and durations, and staff."""
        return await self._tool("get_business_info", {"topic": topic})

    @function_tool()
    async def answer_faq(self, context: RunContext, question: str) -> str:
        """Look up the salon's FAQ (parking, payment, policies, products, ...).

        Args:
            question: the caller's question in their words
        """
        return await self._tool("answer_faq", {"question": question})

    @function_tool()
    async def check_availability(
        self,
        context: RunContext,
        service: str,
        date_from: str,
        date_to: str | None = None,
        staff: str | None = None,
        time_of_day: Literal["any", "morning", "afternoon", "evening"] = "any",
    ) -> str:
        """Find free appointment times. Only times returned here may be offered.

        Args:
            service: service name, e.g. "Haircut"
            date_from: the caller's words or ISO date, e.g. "tomorrow", "next friday"
            date_to: optional end of range (caller's words or ISO date)
            staff: preferred staff member, or omit for anyone
            time_of_day: morning, afternoon, evening or any
        """
        return await self._tool(
            "check_availability",
            {"service": service, "date_from": date_from, "date_to": date_to, "staff": staff,
             "time_of_day": time_of_day},
        )

    @function_tool()
    async def book_appointment(
        self,
        context: RunContext,
        slot_id: str,
        service: str,
        customer_name: str,
        phone: str | None = None,
        email: str | None = None,
        notes: str | None = None,
        caller_confirmed: bool = False,
    ) -> str:
        """Book a slot returned by check_availability. Set caller_confirmed=true only after
        reading back the details and hearing a clear yes.

        Args:
            slot_id: slot_id from check_availability
            service: service name
            customer_name: caller's full name
            phone: caller's phone (optional on phone calls: caller id is used)
            email: email for the confirmation (optional)
            notes: anything the stylist should know
            caller_confirmed: true once the caller said yes to the read-back
        """
        return await self._tool(
            "book_appointment",
            {"slot_id": slot_id, "service": service, "customer_name": customer_name,
             "phone": phone, "email": email, "notes": notes,
             "caller_confirmed": caller_confirmed},
        )

    @function_tool()
    async def reschedule_appointment(
        self,
        context: RunContext,
        contact: str,
        date: str,
        new_slot_id: str,
        appointment_ref: str | None = None,
        caller_confirmed: bool = False,
    ) -> str:
        """Move the caller's booking to a new slot from check_availability.

        Args:
            contact: phone number or email used for the booking
            date: date of the existing booking (caller's words or ISO)
            new_slot_id: slot_id for the new time, from check_availability
            appointment_ref: only if the tool asked which booking
            caller_confirmed: true once the caller said yes to the read-back
        """
        return await self._tool(
            "reschedule_appointment",
            {"contact": contact, "date": date, "new_slot_id": new_slot_id,
             "appointment_ref": appointment_ref, "caller_confirmed": caller_confirmed},
        )

    @function_tool()
    async def cancel_appointment(
        self,
        context: RunContext,
        contact: str,
        date: str,
        appointment_ref: str | None = None,
        caller_confirmed: bool = False,
    ) -> str:
        """Cancel the caller's booking.

        Args:
            contact: phone number or email used for the booking
            date: date of the booking (caller's words or ISO)
            appointment_ref: only if the tool asked which booking
            caller_confirmed: true once the caller said yes to the read-back
        """
        return await self._tool(
            "cancel_appointment",
            {"contact": contact, "date": date, "appointment_ref": appointment_ref,
             "caller_confirmed": caller_confirmed},
        )

    @function_tool()
    async def take_message(
        self, context: RunContext, name: str, callback_number: str, message: str,
        urgent: bool = False,
    ) -> str:
        """Save a message for the team; they get an email.

        Args:
            name: caller's name
            callback_number: number to call back
            message: the message
            urgent: true if it needs attention today
        """
        return await self._tool(
            "take_message",
            {"name": name, "callback_number": callback_number, "message": message,
             "urgent": urgent},
        )

    @function_tool()
    async def request_human(
        self, context: RunContext, name: str | None = None, callback_number: str | None = None,
        reason: str | None = None,
    ) -> str:
        """Hand off to a person: the caller asked for one or you can't help.

        Args:
            name: caller's name
            callback_number: number to call back (omit on phone calls to use caller id)
            reason: short reason
        """
        raw = await self.api.tool(
            self.state.call_id, "request_human",
            {k: v for k, v in {"name": name, "callback_number": callback_number,
                               "reason": reason}.items() if v},
        )
        await self._publish("request_human", str(raw.get("status", "error")))
        if raw.get("status") == "transferred":
            self.state.transfer_to = raw.get("data", {}).get("transfer_to")
            asyncio.create_task(self._transfer_after_goodbye())
        return _result(raw)

    async def _transfer_after_goodbye(self) -> None:
        await asyncio.sleep(4)  # let the agent say "connecting you now"
        sip = next(
            (p for p in self.job_ctx.room.remote_participants.values()
             if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP),
            None,
        )
        if sip is None or not self.state.transfer_to:
            return
        try:
            await self.job_ctx.transfer_sip_participant(sip, self.state.transfer_to)
            self.state.end_reason = "transferred"
        except Exception:
            log.exception("SIP transfer failed")

    @function_tool()
    async def end_call(self, context: RunContext) -> str:
        """End the call after saying goodbye (caller is done, or abusive after a warning)."""
        self.state.end_reason = "agent_ended"
        asyncio.create_task(_hang_up_soon(self.job_ctx, 3))
        return "Say a short goodbye now; the call will end."


async def _hang_up_soon(ctx: JobContext, delay: float) -> None:
    await asyncio.sleep(delay)
    try:
        await ctx.delete_room()
    except Exception:
        log.exception("could not end room")


def _caller(ctx: JobContext, participant: rtc.RemoteParticipant) -> tuple[str, str]:
    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        return "phone", participant.attributes.get("sip.phoneNumber", "")
    return "web", ""


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    participant = await ctx.wait_for_participant()
    channel, number = _caller(ctx, participant)
    api = ApiClient()
    try:
        start = await api.start_call(channel, ctx.room.name, number)
    except Exception:
        log.exception("API unreachable at call start")
        start = {"allowed": False, "reason": "api_down"}

    if not start.get("allowed"):
        # Speak a short busy message with the realtime model, then hang up.
        session: AgentSession = AgentSession(llm=google.realtime.RealtimeModel(
            model=VOICE_MODEL, voice=os.environ.get("VOICE_NAME", "Aoede")))
        await session.start(agent=Agent(instructions="Say only the line you are given."),
                            room=ctx.room, record=False)
        await session.generate_reply(instructions=f"Say exactly: {BUSY_LINE}")
        await asyncio.sleep(6)
        await api.aclose()
        await ctx.delete_room()
        return

    state = CallState(start["call_id"])
    started_at = datetime.now(UTC)
    usage = {"audio_in": 0, "audio_out": 0, "text": 0}
    user_stopped_at: float | None = None

    model = google.realtime.RealtimeModel(
        model=VOICE_MODEL,
        voice=start.get("voice") or os.environ.get("VOICE_NAME", "Aoede"),
        language=start.get("language") or None,
        temperature=0.6,
    )
    session = AgentSession(llm=model, user_away_timeout=30.0)
    agent = Receptionist(start["instructions"], api, state, ctx)

    @session.on("conversation_item_added")
    def _on_item(ev: Any) -> None:
        item = ev.item
        if not isinstance(item, ChatMessage):
            return
        text = (item.text_content or "").strip()
        if not text:
            return
        speaker = "caller" if item.role == "user" else "agent"
        state.turns.append(
            {"speaker": speaker, "text": text, "ts": datetime.now(UTC).isoformat()}
        )
        if item.role == "assistant":
            if item.interrupted:
                state.interruptions += 1
            e2e = (item.metrics or {}).get("e2e_latency")
            if e2e and e2e > 0:
                state.latencies_ms.append(int(e2e * 1000))

    @session.on("user_state_changed")
    def _on_user_state(ev: Any) -> None:
        nonlocal user_stopped_at
        if ev.new_state == "listening" and ev.old_state == "speaking":
            user_stopped_at = time.perf_counter()

    @session.on("agent_state_changed")
    def _on_agent_state(ev: Any) -> None:
        nonlocal user_stopped_at
        # Fallback latency measure when per-turn metrics are unavailable.
        if ev.new_state == "speaking" and user_stopped_at is not None:
            if not state.latencies_ms or len(state.latencies_ms) < len(
                [t for t in state.turns if t["speaker"] == "agent"]
            ):
                state.latencies_ms.append(int((time.perf_counter() - user_stopped_at) * 1000))
            user_stopped_at = None

    @session.on("metrics_collected")
    def _on_metrics(ev: Any) -> None:
        m = ev.metrics
        if getattr(m, "type", "") == "realtime_model_metrics":
            usage["audio_in"] += m.input_token_details.audio_tokens
            usage["audio_out"] += m.output_token_details.audio_tokens
            usage["text"] += m.input_token_details.text_tokens + m.output_token_details.text_tokens

    async def _report() -> None:
        if state.ended:
            return
        state.ended = True
        payload = {
            "ended_at": datetime.now(UTC).isoformat(),
            "end_reason": state.end_reason,
            "turns": state.turns,
            "latency_ms": state.latencies_ms,
            "interruptions": state.interruptions,
            "audio_input_tokens": usage["audio_in"],
            "audio_output_tokens": usage["audio_out"],
            "text_tokens": usage["text"],
        }
        try:
            await api.end_call(state.call_id, payload)
        except Exception:
            log.exception("could not report call end", extra={"call_id": state.call_id})
        finally:
            await api.aclose()

    ctx.add_shutdown_callback(_report)

    # Raw audio is not stored (spec): recording off.
    await session.start(agent=agent, room=ctx.room, record=False)
    await session.generate_reply(
        instructions=f"Greet the caller with exactly this, then wait: {start['greeting']}"
    )

    max_s = int(start.get("max_call_seconds", 600))

    async def _call_timer() -> None:
        await asyncio.sleep(max(10, max_s - 30))
        await session.generate_reply(
            instructions="The call time limit is nearly reached. Politely wrap up in one "
            "sentence: offer to take a message if anything is unfinished, then say goodbye."
        )
        await asyncio.sleep(30)
        state.end_reason = "time_limit"
        await ctx.delete_room()

    timer = asyncio.create_task(_call_timer())
    ctx.add_shutdown_callback(lambda: _cancel(timer))
    log.info("call started", extra={"call_id": state.call_id, "channel": channel,
                                    "started_at": started_at.isoformat()})


async def _cancel(task: asyncio.Task[Any]) -> None:
    task.cancel()


if __name__ == "__main__":
    cli.run_app(server)
