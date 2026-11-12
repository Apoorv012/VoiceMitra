"use client";

// Patient-facing text in English and Hindi. Staff screens (doctor, operator) are English only.
// Hindi is written the way it is spoken: simple words, "aap" form, English kept for words people
// actually say in English (doctor, medicine names).

import { useSyncExternalStore } from "react";

export type Lang = "en" | "hi";

type Entry = { en: string; hi: string };

export const MESSAGES = {
  // time and greetings
  today: { en: "Today", hi: "आज" },
  yesterday: { en: "Yesterday", hi: "कल" },
  now: { en: "now", hi: "अभी" },
  in_min: { en: "in {n} min", hi: "{n} मिनट में" },
  in_hours: { en: "in {n} h", hi: "{n} घंटे में" },
  good_morning: { en: "Good morning", hi: "सुप्रभात" },
  good_afternoon: { en: "Good afternoon", hi: "नमस्कार" },
  good_evening: { en: "Good evening", hi: "शुभ संध्या" },
  namaste: { en: "Hello, {name}", hi: "नमस्ते, {name}" },

  and: { en: "and", hi: "और" },
  years_old: { en: "{n} years old", hi: "{n} वर्ष" },
  transcript_title: { en: "Conversation", hi: "बातचीत" },
  transcript_empty: { en: "No conversation was recorded for this call.", hi: "इस कॉल की बातचीत दर्ज नहीं है।" },
  you_said: { en: "You", hi: "आप" },
  agent_said: { en: "VoiceMitra", hi: "VoiceMitra" },

  // common
  loading: { en: "Loading…", hi: "लोड हो रहा है…" },
  load_error: { en: "Couldn't load this. Please check your connection.", hi: "यह लोड नहीं हो सका। कृपया अपना इंटरनेट जाँचें।" },
  retry: { en: "Try again", hi: "फिर कोशिश करें" },
  back: { en: "Back", hi: "वापस" },
  close: { en: "Close", hi: "बंद करें" },
  send: { en: "Send", hi: "भेजें" },

  // signing in
  signin_title: { en: "Sign in", hi: "साइन इन करें" },
  signin_sub: {
    en: "Use the username and password you were given.",
    hi: "जो यूज़रनेम और पासवर्ड आपको दिया गया है, उससे साइन इन करें।",
  },
  signin_btn: { en: "Sign in", hi: "साइन इन करें" },
  signin_wrong: {
    en: "That username and password don't match. Please check and try again.",
    hi: "यूज़रनेम और पासवर्ड मेल नहीं खाते। कृपया जाँचकर फिर कोशिश करें।",
  },
  signin_paused: {
    en: "Too many tries. Please wait a few minutes and try again.",
    hi: "बहुत बार कोशिश हो गई। कृपया कुछ मिनट रुककर फिर कोशिश करें।",
  },
  signin_error: { en: "Couldn't sign in. Please check your connection.", hi: "साइन इन नहीं हो सका। कृपया अपना इंटरनेट जाँचें।" },
  signin_forgot: {
    en: "Forgot your password? Ask the person who set up VoiceMitra for you.",
    hi: "पासवर्ड भूल गए? जिसने आपके लिए VoiceMitra सेट किया है, उनसे पूछें।",
  },
  signin_no_account: {
    en: "No account yet? VoiceMitra is in a small pilot right now.",
    hi: "अभी खाता नहीं है? VoiceMitra अभी एक छोटे पायलट में है।",
  },
  signin_early_access: { en: "Ask to join or get early access", hi: "जुड़ने या जल्दी इस्तेमाल के लिए पूछें" },
  sign_out: { en: "Sign out", hi: "साइन आउट करें" },
  not_allowed_title: { en: "This page isn't yours", hi: "यह पेज आपका नहीं है" },
  not_allowed_sub: { en: "You're signed in as {name}.", hi: "आप {name} के नाम से साइन इन हैं।" },
  go_home: { en: "Go to my page", hi: "मेरे पेज पर जाएँ" },

  // caregiver
  cg_looking_after: { en: "Looking after {name}", hi: "{name} की देखभाल" },
  cg_in_call: { en: "{name} is talking to VoiceMitra right now.", hi: "{name} अभी VoiceMitra से बात कर रहे हैं।" },
  cg_alerts: { en: "Alerts", hi: "अलर्ट" },
  cg_new: { en: "{n} new", hi: "नए: {n}" },
  cg_no_alerts: {
    en: "No alerts. You'll see one here if {name} isn't feeling well or can't be reached.",
    hi: "कोई अलर्ट नहीं। अगर {name} की तबीयत ठीक न हो या उनसे बात न हो सके, तो यहाँ दिखेगा।",
  },
  cg_no_new: { en: "No new alerts.", hi: "कोई नया अलर्ट नहीं।" },
  cg_urgent: { en: "Urgent", hi: "ज़रूरी" },
  cg_unwell: { en: "Not feeling well", hi: "तबीयत ठीक नहीं" },
  cg_unreachable: { en: "Couldn't be reached", hi: "बात नहीं हो सकी" },
  cg_mark_seen: { en: "Mark as seen", hi: "देख लिया" },
  cg_mark_all_seen: { en: "Mark all as seen", hi: "सब देख लिए" },
  cg_seen: { en: "Seen {when}", hi: "देखा गया: {when}" },
  cg_earlier: { en: "Earlier", hi: "पहले के" },
  cg_todays_meds: { en: "{name}'s medicines today", hi: "{name} की आज की दवाइयाँ" },
  cg_how_doing: { en: "How {name} is doing", hi: "{name} की तबीयत" },
  cg_last_checkin: { en: "Last check-in with VoiceMitra {when}", hi: "VoiceMitra से पिछली बातचीत {when}" },
  cg_not_linked: { en: "You're no longer the family contact for this patient.", hi: "अब आप इस मरीज़ के परिवार के संपर्क नहीं हैं।" },

  // tabs
  tab_today: { en: "Today", hi: "आज" },
  tab_medicines: { en: "Medicines", hi: "दवाइयाँ" },
  tab_history: { en: "History", hi: "इतिहास" },
  tab_me: { en: "Me", hi: "मैं" },

  // talk card
  talk_title: { en: "Talk to VoiceMitra", hi: "VoiceMitra से बात करें" },
  talk_sub: { en: "A quick check-in takes about 2 minutes.", hi: "छोटी-सी बातचीत में लगभग 2 मिनट लगते हैं।" },
  talk_btn: { en: "Start check-in", hi: "बातचीत शुरू करें" },
  talk_starting: { en: "Starting…", hi: "शुरू हो रहा है…" },
  talk_in_call: { en: "Return to your call", hi: "अपनी कॉल पर लौटें" },
  talk_error: { en: "Couldn't start the call. Please try again.", hi: "कॉल शुरू नहीं हो सकी। कृपया फिर कोशिश करें।" },
  last_checkin: { en: "Last check-in {when}", hi: "पिछली बातचीत {when}" },
  no_checkin_yet: { en: "No check-ins yet", hi: "अभी तक कोई बातचीत नहीं हुई" },

  // today's doses
  next_dose: { en: "Next dose", hi: "अगली दवा" },
  todays_meds: { en: "Today's medicines", hi: "आज की दवाइयाँ" },
  none_today: { en: "No medicines are scheduled for today.", hi: "आज कोई दवा तय नहीं है।" },
  dose_taken: { en: "Taken", hi: "ले ली" },
  dose_partial: { en: "Partly taken", hi: "आधी ली" },
  dose_missed: { en: "Missed", hi: "छूट गई" },
  dose_later: { en: "Taking later", hi: "बाद में लेंगे" },
  dose_unknown: { en: "Not sure", hi: "पक्का नहीं" },
  dose_skipped: { en: "Skipped on advice", hi: "सलाह पर छोड़ी" },
  dose_upcoming: { en: "Upcoming", hi: "आने वाली" },
  dose_due: { en: "Due now", hi: "अभी लेनी है" },
  dose_nocheckin: { en: "Not checked", hi: "पूछा नहीं गया" },

  // the week
  this_week: { en: "This week", hi: "इस हफ़्ते" },
  week_summary: { en: "{taken} of {total} doses taken", hi: "{total} में से {taken} खुराकें ली गईं" },
  week_none: { en: "Nothing was scheduled this week.", hi: "इस हफ़्ते कुछ तय नहीं था।" },
  week_unchecked: { en: "{n} not checked", hi: "{n} के बारे में पूछा नहीं गया" },
  day_good: { en: "All taken", hi: "सब ली" },
  day_mixed: { en: "Some missed", hi: "कुछ छूटीं" },
  day_missed: { en: "Missed", hi: "छूट गईं" },
  day_unknown: { en: "Not checked", hi: "पूछा नहीं गया" },
  day_upcoming: { en: "Coming up", hi: "आगे" },
  day_none: { en: "Nothing due", hi: "कुछ तय नहीं" },

  // how you're doing
  how_doing: { en: "How you're doing", hi: "आपकी सेहत" },
  doing_ok: { en: "Looks fine", hi: "सब ठीक लगा" },
  doing_watch: { en: "Worth telling your doctor", hi: "डॉक्टर को बताना ठीक रहेगा" },
  doing_urgent: { en: "Needs a doctor's attention", hi: "डॉक्टर को दिखाना ज़रूरी है" },
  reminder_at: { en: "VoiceMitra will call you at {time}", hi: "VoiceMitra आपको {time} पर कॉल करेगा" },
  caregiver_line: {
    en: "{name} ({relation}) is told if we can't reach you or you're not feeling well.",
    hi: "अगर आपसे बात न हो सके या आपकी तबीयत ठीक न हो, तो {name} ({relation}) को बताया जाता है।",
  },

  // medicines page
  meds_title: { en: "Your medicines", hi: "आपकी दवाइयाँ" },
  allergies: { en: "Allergies", hi: "एलर्जी" },
  no_allergies: { en: "No known allergies", hi: "कोई ज्ञात एलर्जी नहीं" },
  med_current: { en: "Current", hi: "अभी की" },
  med_past: { en: "Finished", hi: "पूरी हो चुकीं" },
  med_daily: { en: "Every day at {times}", hi: "रोज़ {times}" },
  med_weekly: { en: "Once a week at {times}", hi: "हफ़्ते में एक बार, {times}" },
  med_fixed: { en: "At {times}", hi: "{times} पर" },
  med_every: { en: "Every {n} days at {times}", hi: "हर {n} दिन, {times}" },
  med_until: { en: "until {date}", hi: "{date} तक" },
  med_days_left: { en: "{n} days left", hi: "{n} दिन बाकी" },
  med_last_day: { en: "Last day today", hi: "आज आख़िरी दिन है" },
  med_week: { en: "{taken} of {known} taken this week", hi: "इस हफ़्ते {known} में से {taken} ली" },
  no_meds: { en: "No medicines on your list yet.", hi: "आपकी सूची में अभी कोई दवा नहीं है।" },

  // history
  history_title: { en: "Your check-ins", hi: "आपकी बातचीत" },
  checkin: { en: "Check-in call", hi: "जाँच-बातचीत" },
  doctor_joined: { en: "A doctor joined this call", hi: "इस कॉल में डॉक्टर जुड़े" },
  escalated: { en: "A doctor was contacted", hi: "डॉक्टर से संपर्क किया गया" },
  view_conversation: { en: "View conversation", hi: "बातचीत देखें" },
  mentioned: { en: "You mentioned: {list}", hi: "आपने बताया: {list}" },
  no_history: { en: "No check-ins yet.", hi: "अभी तक कोई बातचीत नहीं हुई।" },
  family_told: { en: "Family were told", hi: "परिवार को बताया गया" },
  med_status_taken: { en: "Medicine taken", hi: "दवा ली" },
  med_status_not_taken: { en: "Medicine not taken", hi: "दवा नहीं ली" },
  med_status_confusion: { en: "Unsure about medicine", hi: "दवा के बारे में पक्का नहीं" },
  med_status_dont_know: { en: "Unsure about medicine", hi: "दवा के बारे में पक्का नहीं" },

  // me
  me_title: { en: "Your details", hi: "आपकी जानकारी" },
  phone: { en: "Phone", hi: "फ़ोन" },
  address: { en: "Address", hi: "पता" },
  caregiver: { en: "Family contact", hi: "परिवार का संपर्क" },
  language: { en: "Language", hi: "भाषा" },
  install_title: { en: "Add to your home screen", hi: "होम स्क्रीन पर जोड़ें" },
  install_sub: { en: "Open VoiceMitra like an app, in one tap.", hi: "VoiceMitra को ऐप की तरह एक टैप में खोलें।" },
  install_btn: { en: "Install", hi: "इंस्टॉल करें" },
  install_ios: {
    en: "Tap the Share button, then “Add to Home Screen”.",
    hi: "शेयर बटन दबाएँ, फिर “Add to Home Screen” चुनें।",
  },

  // connect a phone (pairing the VoiceMitra phone app)
  phone_title: { en: "Connect a phone", hi: "फ़ोन जोड़ें" },
  phone_sub: {
    en: "With the VoiceMitra app, your phone rings like a normal call when it's time for your medicine.",
    hi: "VoiceMitra ऐप से, दवा का समय होने पर आपका फ़ोन आम कॉल की तरह बजेगा।",
  },
  phone_btn: { en: "Get a code", hi: "कोड पाएँ" },
  phone_another: { en: "Connect another phone", hi: "एक और फ़ोन जोड़ें" },
  phone_enter: { en: "Open the VoiceMitra app on the phone and type this number:", hi: "फ़ोन पर VoiceMitra ऐप खोलें और यह नंबर लिखें:" },
  phone_expires: { en: "Works for {time} more", hi: "{time} और चलेगा" },
  phone_expired: { en: "This number has expired.", hi: "यह नंबर अब नहीं चलेगा।" },
  phone_new_code: { en: "Get a new code", hi: "नया कोड पाएँ" },
  phone_waiting: { en: "Waiting for the phone…", hi: "फ़ोन का इंतज़ार है…" },
  phone_done: { en: "Phone connected", hi: "फ़ोन जुड़ गया" },
  phone_connected: { en: "Connected phones", hi: "जुड़े हुए फ़ोन" },
  phone_unnamed: { en: "Phone", hi: "फ़ोन" },
  phone_error: { en: "Couldn't get a code. Please try again.", hi: "कोड नहीं मिल सका। कृपया फिर कोशिश करें।" },

  // your login (the same username + password on this website and in the VoiceMitra phone app)
  login_title: { en: "Your login", hi: "आपका लॉगिन" },
  login_sub: {
    en: "Use this username and password to sign in here and in the VoiceMitra phone app.",
    hi: "यहाँ और VoiceMitra फ़ोन ऐप में इसी यूज़रनेम और पासवर्ड से साइन इन करें।",
  },
  login_username: { en: "Username", hi: "यूज़रनेम" },
  login_password: { en: "Password", hi: "पासवर्ड" },
  login_new_password: { en: "New password", hi: "नया पासवर्ड" },
  login_pass_hint: { en: "At least {n} letters or numbers.", hi: "कम से कम {n} अक्षर या अंक।" },
  login_show: { en: "Show password", hi: "पासवर्ड दिखाएँ" },
  login_none: { en: "No login set yet.", hi: "अभी कोई लॉगिन नहीं बना है।" },
  login_set: { en: "Set a login", hi: "लॉगिन बनाएँ" },
  login_change: { en: "Change login", hi: "लॉगिन बदलें" },
  login_save: { en: "Save", hi: "सेव करें" },
  login_cancel: { en: "Cancel", hi: "रद्द करें" },
  login_saved: { en: "Saved. Use these to sign in here and on the phone app.", hi: "सेव हो गया। यहाँ और फ़ोन ऐप में इन्हीं से साइन इन करें।" },
  login_short_user: { en: "The username needs at least {n} letters.", hi: "यूज़रनेम में कम से कम {n} अक्षर चाहिए।" },
  login_short_pass: { en: "The password needs at least {n} letters or numbers.", hi: "पासवर्ड में कम से कम {n} अक्षर या अंक चाहिए।" },
  login_taken: { en: "Someone else already has this username. Please pick another.", hi: "यह यूज़रनेम किसी और का है। कृपया दूसरा चुनें।" },
  login_error: { en: "Couldn't save. Please try again.", hi: "सेव नहीं हो सका। कृपया फिर कोशिश करें।" },

  // the call
  call_connecting: { en: "Connecting…", hi: "जोड़ा जा रहा है…" },
  call_allow_mic: { en: "Please allow the microphone to start", hi: "शुरू करने के लिए माइक्रोफ़ोन की अनुमति दें" },
  call_live: { en: "Connected. Speak after VoiceMitra greets you.", hi: "जुड़ गए। VoiceMitra के नमस्ते के बाद बोलें।" },
  call_hold: { en: "Connecting you to the doctor. Please hold.", hi: "आपको डॉक्टर से जोड़ा जा रहा है। कृपया रुकें।" },
  call_briefing: { en: "{name} is being briefed. Please hold.", hi: "{name} को जानकारी दी जा रही है। कृपया रुकें।" },
  call_merged: { en: "{name} has joined. Please speak.", hi: "{name} जुड़ गए हैं। कृपया बोलें।" },
  call_ended: { en: "Call ended", hi: "कॉल समाप्त हुई" },
  call_failed: { en: "Couldn't start the call ({err}).", hi: "कॉल शुरू नहीं हो सकी ({err})।" },
  mic_blocked: {
    en: "The microphone is blocked. Allow it in your browser settings, then try again.",
    hi: "माइक्रोफ़ोन बंद है। ब्राउज़र की सेटिंग में अनुमति देकर फिर कोशिश करें।",
  },
  end_call: { en: "End call", hi: "कॉल खत्म करें" },
  type_reply: { en: "Type your reply", hi: "अपना जवाब लिखें" },
  who_you: { en: "You", hi: "आप" },
  who_agent: { en: "VoiceMitra", hi: "VoiceMitra" },
} satisfies Record<string, Entry>;

export type MessageKey = keyof typeof MESSAGES;

export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>): string {
  const entry: Entry | undefined = MESSAGES[key];
  const text = entry ? entry[lang] || entry.en : key;
  return vars ? text.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? "")) : text;
}

// --- the chosen language, remembered on this device ------------------------------------------

const KEY = "vm_lang";
const listeners = new Set<() => void>();

function browserDefault(): Lang {
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("hi") ? "hi" : "en";
}

function snapshot(): Lang {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "en" || stored === "hi") return stored;
  } catch {
    /* storage blocked */
  }
  return browserDefault();
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  window.addEventListener("storage", fn);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", fn);
  };
}

export function setLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang);
  } catch {
    /* ignore */
  }
  document.documentElement.lang = lang;
  listeners.forEach((fn) => fn());
}

/** `t(key, vars)` in the reader's language, plus the language itself. Server render uses English. */
export function useT() {
  const lang = useSyncExternalStore(subscribe, snapshot, (): Lang => "en");
  return {
    lang,
    t: (key: MessageKey, vars?: Record<string, string | number>) => translate(lang, key, vars),
  };
}
