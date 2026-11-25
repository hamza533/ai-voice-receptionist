"""staff schedules, time off, SMS, waitlist, integrations, setup flag

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("business_config") as t:
        t.add_column(sa.Column("sms_confirmations", sa.Boolean(), nullable=False, server_default=sa.true()))
        t.add_column(sa.Column("sms_reminders", sa.Boolean(), nullable=False, server_default=sa.true()))
        t.add_column(sa.Column("reminder_hours", sa.Integer(), nullable=False, server_default="24"))
        t.add_column(sa.Column("waitlist_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        t.add_column(sa.Column("waitlist_hold_minutes", sa.Integer(), nullable=False, server_default="30"))
        # Existing installs are already set up; new ones go through the setup wizard.
        t.add_column(sa.Column("setup_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE business_config SET setup_completed = true")

    op.create_table(
        "staff_shifts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id", "weekday", "start_time", name="uq_staff_shift_start"),
    )
    op.create_index("ix_staff_shifts_staff_id", "staff_shifts", ["staff_id"])

    op.create_table(
        "time_off",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_time_off_staff_id", "time_off", ["staff_id"])

    op.create_table(
        "waitlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("time_of_day", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=True),
        sa.Column("offer_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_staff_id", sa.Integer(), nullable=True),
        sa.Column("offer_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offered_slots", JSONB, nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["offer_staff_id"], ["staff.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_waitlist_status_day", "waitlist", ["status", "day"])

    op.create_table(
        "sms_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )

    op.create_table(
        "integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("account_email", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("calendar_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )


def downgrade() -> None:
    op.drop_table("integrations")
    op.drop_table("sms_messages")
    op.drop_index("ix_waitlist_status_day", table_name="waitlist")
    op.drop_table("waitlist")
    op.drop_index("ix_time_off_staff_id", table_name="time_off")
    op.drop_table("time_off")
    op.drop_index("ix_staff_shifts_staff_id", table_name="staff_shifts")
    op.drop_table("staff_shifts")
    with op.batch_alter_table("business_config") as t:
        for col in (
            "setup_completed",
            "waitlist_hold_minutes",
            "waitlist_enabled",
            "reminder_hours",
            "sms_reminders",
            "sms_confirmations",
        ):
            t.drop_column(col)
