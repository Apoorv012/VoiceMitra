"""Rules+keyword layer behind escalation decisions: a red-flag symptom list (used by the forced-
escalation guardrail in guardrails.py, independent of what the LLM decides) and an allergy/
medication cross-check (used when logging a dose event or symptom).

The keyword matching here is intentionally simple substring matching over Hindi/Hinglish/English
phrasing -- good enough to force a safety override for the POC's scenarios, not a claim of robust
NLU. `escalate_to_doctor` (the LLM-driven tool) remains the primary decision path; this module is
the backstop.
"""

from __future__ import annotations

RED_FLAGS: dict[str, list[str]] = {
    "chest pain": ["chest pain", "chest mein dard", "chest me dard", "seene mein dard", "seene me dard"],
    "breathlessness": ["saans lene mein takleef", "saans phool", "saans nahi aa rahi", "breathless", "shortness of breath"],
    "fainting / severe dizziness": ["behosh", "chakkar aa rahe", "chakkar aa raha", "fainting", "faint ho"],
    "severe bleeding": ["khoon aa raha", "bahut khoon", "heavy bleeding"],
    "severe allergic reaction": ["saans rukna", "gala sujj", "throat swelling", "severe rash", "anaphyla"],
}


def detect_red_flag(text: str) -> str | None:
    lowered = text.lower()
    for canonical, phrases in RED_FLAGS.items():
        if any(phrase in lowered for phrase in phrases):
            return canonical
    return None


def check_allergy_conflict(medicine_name: str, allergies: list[str]) -> str | None:
    """Very simple stub cross-check: flags if an allergy name appears inside the medicine name.
    Extended in Chunk 4 if a real drug/allergy mapping is worth adding for the demo."""
    lowered_medicine = medicine_name.lower()
    for allergy in allergies:
        if allergy.strip().lower() in lowered_medicine:
            return f"'{medicine_name}' may conflict with the recorded allergy to '{allergy}'"
    return None
