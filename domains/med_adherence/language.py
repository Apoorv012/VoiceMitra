"""Cheap, deterministic language detection for the patient's messages.

We only need to tell three things apart -- Hindi/Hinglish, English, and "something we don't
support" -- and Hindi is usually typed in Roman letters, which general language-ID libraries handle
badly. So: Devanagari => Hindi; a script that's neither Latin nor Devanagari => unsupported; Latin
text => count distinctive Hindi vs English function words. Latin text with neither (French,
"ok", a bare number...) is undecided (None) and left to the LLM, which is told the rules in the
system prompt.

Deliberately excluded from the word lists: words that also occur in other Latin-script languages
common enough to matter (e.g. "le", "se", "a", "on", "me"), since a false Hindi/English call there
would override the LLM's own judgement.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

Language = Literal["hindi", "english", "unsupported"]

_HINDI_WORDS = frozenset("""
haan han hnji ji nahi nahin nhi kya kyu kyun kab kaise kaisa kaisi kahan mai mujhe mera meri mere
aap aapko aapki aapka tum tumhe hum humein ye yeh wo woh abhi baad phir fir sab theek thik achha
accha acha bahut bohot bhi toh ka ki ke lunga lungi leta leti liya lena lelo kha khaya khali kar
karo karna raha rahi rahe dard sar pet dawai dawa gola bhool bhul gaya gayi chahiye lekin aur koi
kuch kal aaj subah shaam raat bata batao bolo boliye samajh dhanyawad shukriya namaste hoon hun hai
hain tha thi
""".split())

_ENGLISH_WORDS = frozenset("""
the is are am was were be been i you he she we they it my your his her this that these those yes
yeah not have has had took taken take taking feeling feel felt fine good well okay please thanks
thank sorry can could will would what why when how and but with of to in at for just little bit
very actually talk english hello hi speaking forgot remind later again headache pain since morning
evening night today yesterday tablet medicine dose speak
""".split())

_WORD = re.compile(r"[a-zA-Z']+")


def detect_language(text: str) -> Language | None:
    latin = devanagari = other = 0
    for ch in text:
        if not ch.isalpha():
            continue
        if "ऀ" <= ch <= "ॿ":
            devanagari += 1
        elif unicodedata.name(ch, "").startswith("LATIN"):
            latin += 1
        else:
            other += 1

    if devanagari and devanagari >= other:
        return "hindi"
    if other > latin:
        return "unsupported"

    words = _WORD.findall(text.lower())
    hindi = sum(w in _HINDI_WORDS for w in words)
    english = sum(w in _ENGLISH_WORDS for w in words)
    if hindi == 0 and english == 0:
        return None
    return "hindi" if hindi >= english else "english"
