"""Read a photo of a doctor's prescription into draft medicines for staff to check (pilot step 8).

Nothing is saved here: the draft fills the add-prescription form, staff fix what the model got wrong and save
it the normal way. The photo itself isn't stored either.

Gemini (vision) through its OpenAI-compatible endpoint, the same client `core/providers/llm.py` builds. The
call LLM may be Sarvam (text only), so this always uses Gemini; `PRESCRIPTION_MODEL` overrides the model.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date

from pydantic import BaseModel, Field, ValidationError

from backend.models import DoseFrequency
from core.providers.llm import GEMINI_DEFAULT_MODEL, get_gemini_llm_client

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 6 * 1024 * 1024  # the web app shrinks photos to ~1600 px first, so this is generous
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")


class DraftMedicine(BaseModel):
    medicine_name: str
    dosage: str = ""                      # "1 tablet after food"
    frequency: DoseFrequency = DoseFrequency.fixed_times
    times: list[str] = Field(default_factory=list)
    interval_days: int | None = None
    days: int | None = None               # how long to take it, if written ("x 5 days")
    unsure: str | None = None             # what the model couldn't read or wasn't sure about


class PrescriptionDraft(BaseModel):
    medicines: list[DraftMedicine]
    prescribed_on: date | None = None     # the date written on the prescription, if any
    notes: str | None = None              # anything staff should know (e.g. "as needed" medicines left out)


class PhotoUnreadable(Exception):
    pass


PROMPT = """You read photos of Indian doctors' prescriptions (printed or handwritten) for a medicine-reminder \
service. Staff will check your answer before anything is saved, so mark what you are unsure about instead of \
guessing silently.

Return JSON only, in this shape:
{"medicines": [{"medicine_name": str, "dosage": str, "frequency": "fixed_times" | "weekly" | "every_x_day",
  "times": ["HH:MM", ...], "interval_days": int | null, "days": int | null, "unsure": str | null}],
 "prescribed_on": "YYYY-MM-DD" | null, "notes": str | null}

Rules:
- One entry per medicine to be taken. Use the name as written (brand and strength, e.g. "Telma 40"); fix obvious \
handwriting only when sure.
- dosage: how much and any instruction, e.g. "1 tablet after food", "10 ml before breakfast", "1 capsule".
- Times as 24-hour HH:MM. Use these defaults unless the prescription gives clock times: morning 08:00, \
afternoon 14:00, evening 18:00, night/bedtime 21:00.
  Patterns: "1-0-1" = morning and night; "1-1-1" = morning, afternoon, night; "0-0-1" = night; \
"OD"/"once a day" = 08:00; "BD"/"twice a day" = 08:00 and 21:00; "TDS"/"thrice" = 08:00, 14:00, 21:00; \
"QID" = 08:00, 12:00, 16:00, 21:00; "HS" = 21:00; "empty stomach" alone = 07:00.
- Every day -> "fixed_times". Once a week -> "weekly". Every N days (alternate days = 2) -> "every_x_day" with \
interval_days N.
- days: the duration if written ("x 5 days" -> 5, "1 month" -> 30, "2 weeks" -> 14); null if not written or \
"continue".
- Leave out medicines taken only "SOS"/"as needed", tests, and advice; say so in notes.
- If the photo is not a prescription or nothing can be read, return {"medicines": [], "notes": "<why>"}.
- Never add a medicine that isn't written. Never change a dose."""

_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


def _clean_times(times: list[str]) -> list[str]:
    out = []
    for t in times:
        m = _TIME.match(str(t).strip())
        if m and int(m[1]) < 24 and int(m[2]) < 60:
            out.append(f"{int(m[1]):02d}:{m[2]}")
    return sorted(set(out))


def _parse(text: str) -> PrescriptionDraft:
    text = text.strip()
    if text.startswith("```"):  # some models fence JSON even when asked not to
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise PhotoUnreadable("the reader's answer wasn't JSON") from e
    meds = []
    for m in raw.get("medicines") or []:
        if not isinstance(m, dict) or not str(m.get("medicine_name") or "").strip():
            continue
        if m.get("frequency") not in {f.value for f in DoseFrequency}:
            m["frequency"] = DoseFrequency.fixed_times.value
        if m["frequency"] == DoseFrequency.daily.value:
            m["frequency"] = DoseFrequency.fixed_times.value
        m["times"] = _clean_times(m.get("times") or [])
        for k in ("interval_days", "days"):
            v = m.get(k)
            m[k] = v if isinstance(v, int) and 1 <= v <= 365 else None
        if m["frequency"] == DoseFrequency.every_x_days.value and not m["interval_days"]:
            m["interval_days"] = 2
        try:
            meds.append(DraftMedicine.model_validate(m))
        except ValidationError:
            continue
    on = raw.get("prescribed_on")
    try:
        prescribed_on = date.fromisoformat(on) if isinstance(on, str) else None
    except ValueError:
        prescribed_on = None
    notes = raw.get("notes")
    return PrescriptionDraft(medicines=meds, prescribed_on=prescribed_on,
                             notes=str(notes) if notes else None)


async def read_prescription_photo(image_b64: str, mime_type: str) -> PrescriptionDraft:
    client = get_gemini_llm_client()
    model = os.environ.get("PRESCRIPTION_MODEL", GEMINI_DEFAULT_MODEL)
    resp = await client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Read this prescription."},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
            ]},
        ],
    )
    text = resp.choices[0].message.content or ""
    log.info("prescription photo read with %s: %d chars", model, len(text))
    return _parse(text)
