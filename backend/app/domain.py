from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Problem(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def normalize_team(value: str) -> str:
    value = value.strip().upper()
    if not value or len(value) > 32 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Enter a nonempty Team ID of at most 32 characters.")
    return value


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    team_id: str
    code: str = Field(min_length=1, max_length=256)

    @field_validator("team_id")
    @classmethod
    def normalize(cls, value):
        return normalize_team(value)

    @field_validator("code")
    @classmethod
    def trim_code(cls, value):
        value = value.strip()
        if not value or len(value) > 256 or any(ord(c) < 32 for c in value):
            raise ValueError("Enter a nonempty PIN of 1–256 characters.")
        return value


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=1024)


class Deadline(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cutoff: datetime

    @field_validator("cutoff", mode="before")
    @classmethod
    def aware(cls, value):
        if not isinstance(value, str):
            raise ValueError("Use an ISO timestamp with timezone.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Deadline requires a timezone.")
        return parsed.astimezone(timezone.utc)


class SheetRecord(BaseModel):
    team_id: str
    form_timestamp: datetime

    @field_validator("team_id")
    @classmethod
    def normalize(cls, value):
        return normalize_team(value)

    @field_validator("form_timestamp", mode="before")
    @classmethod
    def timestamp(cls, value):
        if not isinstance(value, str):
            raise ValueError("Timestamp must be an ISO 8601 string.")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Timestamp requires a timezone.")
        return parsed.astimezone(timezone.utc)


class SheetEnvelope(BaseModel):
    success: bool = Field(strict=True)
    count: int = Field(ge=0, strict=True)
    data: list[SheetRecord]


def parse_sheet(payload) -> list[dict]:
    from pydantic import ValidationError

    try:
        parsed = SheetEnvelope.model_validate(payload)
    except ValidationError, ValueError, TypeError:
        raise Problem(
            502,
            "sheet_schema",
            "Sheet data is invalid. Check Team IDs and timezone-aware timestamps.",
        ) from None
    if not parsed.success or parsed.count != len(parsed.data):
        raise Problem(
            502,
            "sheet_schema",
            "Sheet reports failure or an inconsistent record count.",
        )
    seen, duplicates = set(), set()
    for row in parsed.data:
        if row.team_id in seen:
            duplicates.add(row.team_id)
        seen.add(row.team_id)
    if duplicates:
        raise Problem(
            422,
            "sheet_duplicates",
            "Duplicate Team IDs in Sheet: " + ", ".join(sorted(duplicates))[:1000],
        )
    return [row.model_dump(mode="json") for row in parsed.data]


class SheetSnapshot(BaseModel):
    records: list[dict]
    total_rows_read: int | None
    returned_rows: int
    eligible_records: int
    invalid_rows: list[dict]
    duplicate_ids: list[str]
    coverage_verified: bool

    def report(self):
        return self.model_dump(exclude={"records"})

    def require_importable(self):
        if not self.coverage_verified:
            raise Problem(
                409,
                "sheet_coverage_unverified",
                "Sheet response does not verify all registration rows. Add total_rows_read coverage metadata to the existing Apps Script export and compare with the actual response Sheet before synchronization.",
            )
        if self.duplicate_ids:
            raise Problem(
                422,
                "sheet_duplicates",
                "Duplicate normalized Team IDs require correction before synchronization: "
                + ", ".join(self.duplicate_ids)[:1000],
            )


def inspect_sheet(payload) -> SheetSnapshot:
    """Audit all exported rows. Legacy exports remain readable but cannot prove coverage."""
    from pydantic import ValidationError

    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise Problem(502, "sheet_schema", "Sheet export reports failure or an invalid response.")
    data, count = payload.get("data"), payload.get("count")
    if not isinstance(data, list) or type(count) is not int or count != len(data):
        raise Problem(
            502,
            "sheet_schema",
            "Sheet export count must match all returned registration rows.",
        )
    total = payload.get("total_rows_read")
    if total is not None and (type(total) is not int or total != len(data)):
        raise Problem(
            502,
            "sheet_coverage",
            "Sheet total_rows_read does not match returned rows; a partial export cannot be synchronized.",
        )
    records, invalid, ids = [], [], []
    for index, row in enumerate(data, start=2):
        row_number = row.get("row_number", index) if isinstance(row, dict) else index
        try:
            team_id = normalize_team(row["team_id"])
        except KeyError, ValueError, TypeError, AttributeError:
            invalid.append({"row_number": row_number, "reason": "invalid_team_id"})
            continue
        ids.append(team_id)
        try:
            parsed = SheetRecord.model_validate(row)
        except ValidationError, ValueError, TypeError:
            invalid.append(
                {
                    "row_number": row_number,
                    "team_id": team_id,
                    "reason": "invalid_registration_timestamp",
                }
            )
            continue
        records.append(parsed.model_dump(mode="json"))
    from collections import Counter

    duplicates = sorted(team for team, n in Counter(ids).items() if n > 1)
    records = [row for row in records if row["team_id"] not in duplicates]
    return SheetSnapshot(
        records=records,
        total_rows_read=total,
        returned_rows=len(data),
        eligible_records=len(records),
        invalid_rows=invalid,
        duplicate_ids=duplicates,
        coverage_verified=total is not None,
    )


class Reset(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmation: Literal["DELETE ALL SIMPLIFIED SUBMISSIONS"]
