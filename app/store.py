from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)

from .market import CHINA_TZ, normalize_code


CHECKPOINTS = (
    ("auction_0925", 9, 25),
    ("m05_0935", 9, 35),
    ("m10_0940", 9, 40),
    ("m15_0945", 9, 45),
    ("m20_0950", 9, 50),
    ("m25_0955", 9, 55),
    ("m30_1000", 10, 0),
    ("m60_1030", 10, 30),
    ("close_1500", 15, 0),
)


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


class CloudMarketStore:
    """SQLAlchemy store that works with Render Postgres and local SQLite."""

    def __init__(self, database_url: str | None = None) -> None:
        database_url = (database_url or os.getenv("DATABASE_URL") or "").strip()
        if not database_url:
            local_path = Path(os.getenv("BSE_DATA_PATH", str(Path(tempfile.gettempdir()) / "bse_sell_assistant.sqlite3")))
            local_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{local_path.as_posix()}"
        if database_url.startswith("postgres://"):
            database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
        elif database_url.startswith("postgresql://"):
            database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)
        self.backend = self.engine.url.get_backend_name()
        self.persistent = self.backend == "postgresql" or bool(os.getenv("BSE_DATA_PATH"))
        self._lock = threading.RLock()
        self.meta = MetaData()
        self._define_tables()
        self.meta.create_all(self.engine)

    def _define_tables(self) -> None:
        self.profiles = Table(
            "security_profiles",
            self.meta,
            Column("code", String(6), primary_key=True),
            Column("issue_price", Float),
            Column("first_day_tradable_shares", Float),
            Column("denominator_source", Text),
            Column("denominator_verified", Boolean, nullable=False, default=False),
            Column("updated_at", String(40), nullable=False),
        )
        self.snapshots = Table(
            "intraday_snapshots",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_date", String(10), nullable=False, index=True),
            Column("code", String(6), nullable=False, index=True),
            Column("captured_at", String(40), nullable=False, index=True),
            Column("source", Text, nullable=False),
            Column("price", Float), Column("open", Float), Column("high", Float), Column("low", Float),
            Column("vwap", Float), Column("volume_shares", Float), Column("amount_yuan", Float),
            Column("custom_turnover_pct", Float), Column("payload_json", Text, nullable=False),
        )
        self.checkpoints = Table(
            "checkpoint_snapshots",
            self.meta,
            Column("session_date", String(10), nullable=False),
            Column("code", String(6), nullable=False),
            Column("checkpoint", String(24), nullable=False),
            Column("captured_at", String(40), nullable=False),
            Column("source", Text, nullable=False), Column("price", Float),
            Column("volume_shares", Float), Column("amount_yuan", Float),
            Column("custom_turnover_pct", Float),
            UniqueConstraint("session_date", "code", "checkpoint", name="uq_checkpoint"),
        )
        self.events = Table(
            "signal_events",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_date", String(10), nullable=False, index=True),
            Column("code", String(6), nullable=False, index=True),
            Column("captured_at", String(40), nullable=False),
            Column("recorded_at", String(40), nullable=False), Column("source", Text, nullable=False),
            Column("price", Float), Column("high", Float), Column("vwap", Float),
            Column("turnover_pct", Float), Column("grade", Text, nullable=False),
            Column("sell_ratio", Float), Column("sell_qty", Float), Column("sell_price", Float),
            Column("guard_price", Float), Column("score", Float), Column("risk_type", Text),
            Column("nearest", Text, nullable=False), Column("best_window", Text), Column("deadline", Text),
            Column("decision_key", Text, nullable=False), Column("is_material_change", Boolean, nullable=False),
            Column("payload_json", Text, nullable=False),
            UniqueConstraint("session_date", "code", "captured_at", name="uq_signal_capture"),
        )

    @staticmethod
    def _checkpoint_for(captured_at: datetime) -> str | None:
        for name, hour, minute in CHECKPOINTS:
            if captured_at.hour == hour and captured_at.minute == minute:
                return name
        return None

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        code = normalize_code(str(payload.get("code") or ""))
        shares = _number(payload.get("firstDayTradableShares"))
        if shares is not None and shares <= 0:
            raise ValueError("首日可交易股数必须大于 0")
        now = datetime.now(CHINA_TZ).isoformat(timespec="seconds")
        with self._lock, self.engine.begin() as db:
            existing = db.execute(select(self.profiles).where(self.profiles.c.code == code)).mappings().first()
            values = {
                "code": code,
                "issue_price": _number(payload.get("issuePrice")) if payload.get("issuePrice") is not None else (existing or {}).get("issue_price"),
                "first_day_tradable_shares": shares if shares is not None else (existing or {}).get("first_day_tradable_shares"),
                "denominator_source": str(payload.get("denominatorSource") or (existing or {}).get("denominator_source") or "").strip(),
                "denominator_verified": bool(payload.get("denominatorVerified")) if shares is not None else bool((existing or {}).get("denominator_verified")),
                "updated_at": now,
            }
            if existing:
                db.execute(update(self.profiles).where(self.profiles.c.code == code).values(**values))
            else:
                db.execute(insert(self.profiles).values(**values))
            if values["first_day_tradable_shares"]:
                denominator = float(values["first_day_tradable_shares"])
                db.execute(
                    update(self.snapshots).where(and_(self.snapshots.c.code == code, self.snapshots.c.volume_shares.is_not(None))).values(
                        custom_turnover_pct=self.snapshots.c.volume_shares / denominator * 100
                    )
                )
                db.execute(
                    update(self.checkpoints).where(and_(self.checkpoints.c.code == code, self.checkpoints.c.volume_shares.is_not(None))).values(
                        custom_turnover_pct=self.checkpoints.c.volume_shares / denominator * 100
                    )
                )
        return self.get_profile(code) or {}

    def get_profile(self, code: str) -> dict[str, Any] | None:
        code = normalize_code(code)
        with self.engine.connect() as db:
            row = db.execute(select(self.profiles).where(self.profiles.c.code == code)).mappings().first()
        if not row:
            return None
        return {
            "code": row["code"], "issuePrice": row["issue_price"],
            "firstDayTradableShares": row["first_day_tradable_shares"],
            "denominatorSource": row["denominator_source"],
            "denominatorVerified": bool(row["denominator_verified"]),
            "denominatorUpdatedAt": row["updated_at"],
        }

    def record_snapshot(self, row: dict[str, Any], captured_at: datetime) -> dict[str, Any]:
        captured_at = captured_at.astimezone(CHINA_TZ)
        code = normalize_code(str(row.get("code") or ""))
        profile = self.get_profile(code) or {}
        volume = _number(row.get("volumeShares"))
        amount = _number(row.get("amountYuan") or row.get("amount"))
        shares = _number(profile.get("firstDayTradableShares"))
        turnover = volume / shares * 100 if volume is not None and shares else None
        timestamp = captured_at.isoformat(timespec="milliseconds")
        values = {
            "session_date": captured_at.date().isoformat(), "code": code, "captured_at": timestamp,
            "source": str(row.get("source") or "unknown"), "price": _number(row.get("price")),
            "open": _number(row.get("open")), "high": _number(row.get("high")), "low": _number(row.get("low")),
            "vwap": _number(row.get("vwap")), "volume_shares": volume, "amount_yuan": amount,
            "custom_turnover_pct": turnover,
            "payload_json": json.dumps(row, ensure_ascii=False, separators=(",", ":"), default=str),
        }
        checkpoint = self._checkpoint_for(captured_at)
        with self._lock, self.engine.begin() as db:
            db.execute(insert(self.snapshots).values(**values))
            if checkpoint:
                key = and_(
                    self.checkpoints.c.session_date == values["session_date"],
                    self.checkpoints.c.code == code,
                    self.checkpoints.c.checkpoint == checkpoint,
                )
                current = db.execute(select(self.checkpoints).where(key)).mappings().first()
                checkpoint_values = {k: values[k] for k in (
                    "session_date", "code", "captured_at", "source", "price", "volume_shares", "amount_yuan", "custom_turnover_pct"
                )}
                checkpoint_values["checkpoint"] = checkpoint
                if current:
                    current_volume = _number(current["volume_shares"]) or -1
                    if (volume or -1) >= current_volume:
                        db.execute(update(self.checkpoints).where(key).values(**checkpoint_values))
                else:
                    db.execute(insert(self.checkpoints).values(**checkpoint_values))
        result = dict(row)
        result.update({
            "customTurnoverPct": turnover,
            "turnover": turnover if turnover is not None else _number(row.get("turnover")),
            "turnoverMethod": "first_day_tradable_shares" if turnover is not None else "vendor_default",
            "firstDayTradableShares": shares,
            "denominatorVerified": bool(profile.get("denominatorVerified")),
            "denominatorSource": profile.get("denominatorSource") or "",
            "capturedAt": timestamp, "sessionDate": values["session_date"],
            "checkpointCaptured": checkpoint,
        })
        return result

    def metrics(self, code: str, session_date: str | None = None) -> dict[str, Any]:
        code = normalize_code(code)
        session_date = (session_date or datetime.now(CHINA_TZ).date().isoformat())[:10]
        condition = and_(self.snapshots.c.session_date == session_date, self.snapshots.c.code == code)
        with self.engine.connect() as db:
            snapshots = db.execute(select(self.snapshots).where(condition).order_by(self.snapshots.c.captured_at)).mappings().all()
            checkpoint_rows = db.execute(
                select(self.checkpoints).where(and_(self.checkpoints.c.session_date == session_date, self.checkpoints.c.code == code))
            ).mappings().all()
        latest = snapshots[-1] if snapshots else None

        def delta(minutes: int) -> float | None:
            if not latest or latest["custom_turnover_pct"] is None:
                return None
            latest_at = datetime.fromisoformat(latest["captured_at"])
            target = latest_at - timedelta(minutes=minutes)
            candidates = [item for item in snapshots if item["custom_turnover_pct"] is not None and datetime.fromisoformat(item["captured_at"]) <= target]
            if not candidates:
                return None
            earlier = candidates[-1]
            earlier_at = datetime.fromisoformat(earlier["captured_at"])
            if not timedelta(0) <= target - earlier_at <= timedelta(seconds=90):
                return None
            return max(0.0, float(latest["custom_turnover_pct"]) - float(earlier["custom_turnover_pct"]))

        checkpoints = {
            item["checkpoint"]: {
                "capturedAt": item["captured_at"], "source": item["source"], "price": item["price"],
                "volumeShares": item["volume_shares"], "amountYuan": item["amount_yuan"],
                "turnoverPct": item["custom_turnover_pct"],
            }
            for item in checkpoint_rows
        }
        history_minutes = 0.0
        if len(snapshots) >= 2:
            history_minutes = max(0.0, (datetime.fromisoformat(snapshots[-1]["captured_at"]) - datetime.fromisoformat(snapshots[0]["captured_at"])).total_seconds() / 60)
        return {
            "sessionDate": session_date, "code": code, "checkpoints": checkpoints,
            "turnoverDelta5Pct": delta(5), "turnoverDelta30Pct": delta(30),
            "turnoverHistoryMinutes": round(history_minutes, 1),
            "latestCapturedAt": latest["captured_at"] if latest else None,
        }

    @staticmethod
    def _event_public(row: Any, inserted: bool | None = None) -> dict[str, Any]:
        payload = json.loads(row["payload_json"] or "{}")
        result = {
            "id": row["id"], "sessionDate": row["session_date"], "code": row["code"],
            "capturedAt": row["captured_at"], "recordedAt": row["recorded_at"], "source": row["source"],
            "price": row["price"], "high": row["high"], "vwap": row["vwap"], "turnoverPct": row["turnover_pct"],
            "grade": row["grade"], "sellRatio": row["sell_ratio"], "sellQty": row["sell_qty"],
            "sellPrice": row["sell_price"], "guardPrice": row["guard_price"], "score": row["score"],
            "riskType": row["risk_type"], "nearest": row["nearest"], "bestWindow": row["best_window"],
            "deadline": row["deadline"], "decisionKey": row["decision_key"],
            "isMaterialChange": bool(row["is_material_change"]),
            "analysis": payload.get("analysis") or [], "state": payload.get("state") or {},
        }
        if inserted is not None:
            result["inserted"] = inserted
        return result

    def record_signal_event(self, event: dict[str, Any]) -> dict[str, Any]:
        code = normalize_code(str(event.get("code") or ""))
        raw = str(event.get("capturedAt") or "")
        try:
            captured = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(CHINA_TZ)
        except ValueError:
            captured = datetime.now(CHINA_TZ)
        captured_at = captured.isoformat(timespec="milliseconds")
        session_date = str(event.get("sessionDate") or captured.date().isoformat())[:10]
        decision_key = str(event.get("decisionKey") or "") or json.dumps({
            "grade": event.get("grade"), "sellRatio": _number(event.get("sellRatio")) or 0,
            "sellQty": _number(event.get("sellQty")) or 0, "nearest": event.get("nearest") or "",
        }, ensure_ascii=False, sort_keys=True)
        values = {
            "session_date": session_date, "code": code, "captured_at": captured_at,
            "recorded_at": datetime.now(CHINA_TZ).isoformat(timespec="milliseconds"),
            "source": str(event.get("source") or "unknown"), "price": _number(event.get("price")),
            "high": _number(event.get("high")), "vwap": _number(event.get("vwap")),
            "turnover_pct": _number(event.get("turnoverPct")), "grade": str(event.get("grade") or "观察"),
            "sell_ratio": _number(event.get("sellRatio")), "sell_qty": _number(event.get("sellQty")),
            "sell_price": _number(event.get("sellPrice")), "guard_price": _number(event.get("guardPrice")),
            "score": _number(event.get("score")), "risk_type": str(event.get("riskType") or ""),
            "nearest": str(event.get("nearest") or "等待行情"), "best_window": str(event.get("bestWindow") or ""),
            "deadline": str(event.get("deadline") or ""), "decision_key": decision_key,
            "is_material_change": True,
            "payload_json": json.dumps({"analysis": event.get("analysis") or [], "state": event.get("state") or {}}, ensure_ascii=False, separators=(",", ":")),
        }
        key = and_(self.events.c.session_date == session_date, self.events.c.code == code, self.events.c.captured_at == captured_at)
        with self._lock, self.engine.begin() as db:
            existing = db.execute(select(self.events).where(key)).mappings().first()
            if existing:
                return self._event_public(existing, inserted=False)
            previous = db.execute(
                select(self.events.c.decision_key).where(and_(self.events.c.session_date == session_date, self.events.c.code == code)).order_by(self.events.c.captured_at.desc()).limit(1)
            ).scalar_one_or_none()
            values["is_material_change"] = previous != decision_key
            result = db.execute(insert(self.events).values(**values).returning(self.events.c.id))
            event_id = result.scalar_one()
            row = db.execute(select(self.events).where(self.events.c.id == event_id)).mappings().one()
        return self._event_public(row, inserted=True)

    def signal_events(self, code: str, session_date: str | None = None, *, changes_only: bool = False, limit: int = 5000) -> dict[str, Any]:
        code = normalize_code(code)
        session_date = (session_date or datetime.now(CHINA_TZ).date().isoformat())[:10]
        condition = and_(self.events.c.session_date == session_date, self.events.c.code == code)
        with self.engine.connect() as db:
            all_rows = db.execute(select(self.events).where(condition).order_by(self.events.c.captured_at).limit(min(max(limit, 1), 20000))).mappings().all()
        visible = [row for row in all_rows if row["is_material_change"]] if changes_only else all_rows
        return {
            "sessionDate": session_date, "code": code, "total": len(all_rows),
            "materialChanges": sum(bool(row["is_material_change"]) for row in all_rows),
            "changesOnly": changes_only, "events": [self._event_public(row) for row in visible],
        }

    def clear_session(self, code: str, session_date: str) -> None:
        code = normalize_code(code)
        with self._lock, self.engine.begin() as db:
            for table in (self.snapshots, self.checkpoints, self.events):
                db.execute(delete(table).where(and_(table.c.code == code, table.c.session_date == session_date[:10])))
