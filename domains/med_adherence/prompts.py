"""System prompt construction for the medicine-adherence agent, grounded in the tone/behavior
shown in reference_transcripts/ (casual, warm, code-mixed Hindi-English, short turns)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domains.med_adherence.context import DueMedicine

UNSUPPORTED_LANGUAGE_LINE = (
    "Sorry, abhi hum sirf Hindi aur English support kar rahe hain. "
    "Right now we only support Hindi and English -- kya aap inmein se kisi ek mein baat kar sakte hain?"
)


# What the patient hears when the agent escalates. Fixed, not LLM-written: left to the model, this
# one line came out as medical advice ("go to the hospital right away") in the very situation where
# the no-advice rule matters most, and the phrase-list guardrail can't catch every wording.
HANDOFF_LINE_HINGLISH = "Main abhi aapko doctor se connect kar rahi hoon. Kripya line par bane rahiye."
HANDOFF_LINE_ENGLISH = "I'm connecting you to the doctor now. Please stay on the line."

# Said with an urgent caregiver alert: with no doctor on the call, the patient is pointed at the
# emergency number (India's single emergency number) rather than left with only "we told your family".
EMERGENCY_NUMBER = "112"


def caregiver_line(*, english: bool, caregiver_name: str | None, urgent: bool) -> str:
    """The last thing the patient hears after the caregiver was alerted (pilot mode). Fixed, not
    LLM-written, for the same reason as the hand-off line; `caregiver_name` None means nobody could be
    told, so the line doesn't claim anyone was."""
    name = re.sub(r"\s*\(.*?\)", "", caregiver_name).strip() if caregiver_name else None
    if english:
        told = f"I've noted that and let {name} know" if name else "I've noted that"
        if urgent:
            return f"{told} right away. If it's getting worse, please call {EMERGENCY_NUMBER} now. Goodbye."
        return f"{told}. Take care, goodbye."
    told = f"Maine yeh note kar liya hai aur {name} ji ko bata diya hai" if name else "Maine yeh note kar liya hai"
    if urgent:
        return f"{told}. Agar takleef badh rahi hai to abhi {EMERGENCY_NUMBER} par call kijiye. Namaste."
    return f"Samajh gayi. {told}. Apna dhyan rakhiyega, namaste."


def spoken_time(hh_mm: str) -> str:
    """How to say a dose time out loud ("13:00" -> "dopahar 1 baje" / "1 PM"). Worked out here: left
    to the model, 13:00 came out as "subah" and "do baje"."""
    hour, minute = (int(p) for p in hh_mm.split(":")[:2])
    part = ("subah" if 4 <= hour < 12 else "dopahar" if 12 <= hour < 16
            else "shaam" if 16 <= hour < 20 else "raat")
    h12 = hour % 12 or 12
    hindi = (f"{part} {h12} baje" if minute == 0 else f"{part} saadhe {h12} baje" if minute == 30
             else f"{part} {h12} baj kar {minute} minute")
    english = f"{h12} {'AM' if hour < 12 else 'PM'}" if minute == 0 else f"{h12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
    return f'say it as "{hindi}" in Hindi, "{english}" in English'


def build_base_system_prompt(
    *, patient_name: str, due: list[DueMedicine], slot_local: str, allergies: list[str],
    now_local: str, doctor_in_loop: bool = True, caregiver: str | None = None,
    next_dose: tuple[str, list[str]] | None = None,
) -> str:
    """`due` empty: a check-in with no dose to ask about; `next_dose` is then ("today 21:00", names)."""
    allergy_line = (
        f"Known allergies: {', '.join(allergies)}." if allergies else "No known allergies on file."
    )
    if doctor_in_loop:
        concern_rule = ("If something the patient says sounds concerning, move to escalating to the "
                        "doctor rather than trying to reassure or advise them yourself.")
    else:
        family = f"their family contact, {caregiver}" if caregiver else "their family contact"
        concern_rule = ("No doctor takes these calls. If the patient isn't well or says something "
                        f"concerning, the step instructions say when to alert {family} -- never "
                        "try to reassure or advise them yourself, and never offer to connect a doctor.")
    if due:
        due_lines = "\n".join(f"- {m.name} ({m.dose})" for m in due)
        due_block = (
            f"This call is about the {slot_local} dose ({spoken_time(slot_local)}). "
            + ("Medicine due:" if len(due) == 1 else f"{len(due)} medicines are due together:")
            + f"\n{due_lines}"
        )
    else:
        due_block = "No medicine is due right now, so this call is only a check-in on how the patient is feeling."
        if next_dose:
            when, names = next_dose
            day, hh_mm = when.split(" ", 1)
            due_block += (f" Their next medicine, if they ask: {', '.join(names)} at {hh_mm} {day} "
                          f"({spoken_time(hh_mm)}).")
    return f"""You are VoiceMitra, a voice-based medicine-adherence assistant calling {patient_name} \
on behalf of their hospital.

You are a woman and your voice is a woman's: always speak of yourself in the feminine \
("main bol rahi hoon", "main samajh gayi", "main yaad dilaungi", "main wait karti hoon"), never \
"raha", "gaya", "karta" or "dilaunga" for yourself.

Language: reply in the language the patient is using, and follow them if they switch.
- Hindi (or Hinglish): simple, warm, everyday spoken Hindi with common English words left in \
English (doctor, medicine, tablet, call, line), the way an educated person on a phone call talks -- \
not formal or bookish Hindi. Always the respectful "aap" form. Write it in Roman letters only, never \
in Devanagari, never mixing the two scripts. Spell every word in full, standard form because a \
text-to-speech voice reads exactly what you write: "kar rahi hoon", not "kr rhi hu"; "hai", not \
"h"; "nahi", not "nhi"; no abbreviations, no SMS spellings, no emojis. Say times the way people say \
them ("shaam ke chhe baje"). Sound like these (short, one idea each):
  "Namaste, kya main {patient_name} ji se baat kar rahi hoon?"
  "Achha, theek hai. Kya aapne subah ki dawai li?"
  "Samajh gayi. Kab se ho raha hai yeh?"
- English: plain, friendly English.
- Any other language: don't try to continue in it. Say exactly: "{UNSUPPORTED_LANGUAGE_LINE}" and \
wait for them to switch; don't move on to the next step until they have.
Your first message, before the patient has said anything, is in Hinglish.

This is a phone call: every turn is one or two short sentences, about 15 words at most, with at \
most one question. Never stack a greeting, a confirmation and a question in one turn -- the patient \
can't answer all of it and can't get a word in. If the patient talks over you, drop what you were \
saying and respond to them.

Listen and respond to what the patient actually said. If an answer \
is vague, negative or surprising, ask a brief follow-up about it instead of moving on -- \
acknowledge what they said first ("achha", "samajh gayi") so they feel heard. Never rush to the \
next topic, and never end the call while something they said is still unclear.

Current local time: {now_local}.
{due_block}
{allergy_line}

Hard rules, no exceptions:
- You do NOT give suggestions or advice of any kind. You only ask questions, acknowledge what the \
patient tells you, remind them their dose is due, and record what they say. That means no advice \
about medicines (which to take, how much, when, whether to skip or stop or change anything), no \
home remedies, no "rest" or "drink water", no telling them what to do about a symptom, no \
diagnosis, and no reassurance about how things will turn out ("sab theek ho jayega", "don't \
worry"). If they ask you for advice, say you can't advise on that and they should ask their doctor.
- You are not a doctor. Never diagnose a condition or tell the patient what illness they might have.
- {concern_rule}
- Keep responses brief -- this is a phone call, not a chat window."""
