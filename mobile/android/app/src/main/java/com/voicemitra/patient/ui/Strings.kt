package com.voicemitra.patient.ui

import com.voicemitra.patient.data.Lang

/**
 * Every word the patient sees, in English and Hindi, side by side. Wording is the web app's
 * (web/src/lib/i18n.tsx) wherever the same thing is said there: simple spoken Hindi, "aap" form.
 * Kept in code (not Android resources) so the language can be switched inside the app.
 */
@Suppress("PropertyName")
class Strings private constructor(val lang: Lang) {
    private val hi = lang == Lang.HI
    private fun t(en: String, hi: String) = if (this.hi) hi else en

    fun fill(template: String, vararg vars: Pair<String, Any>): String =
        vars.fold(template) { acc, (k, v) -> acc.replace("{$k}", v.toString()) }

    // time and greetings
    val today = t("Today", "आज")
    val yesterday = t("Yesterday", "कल")
    val now = t("now", "अभी")
    val inMin = t("in {n} min", "{n} मिनट में")
    val inHours = t("in {n} h", "{n} घंटे में")
    val goodMorning = t("Good morning", "सुप्रभात")
    val goodAfternoon = t("Good afternoon", "नमस्कार")
    val goodEvening = t("Good evening", "शुभ संध्या")
    val greeting = t("Hello, {name}", "नमस्ते, {name}")
    val and = t("and", "और")
    val yearsOld = t("{n} years old", "{n} वर्ष")

    // common
    val loading = t("Loading…", "लोड हो रहा है…")
    val loadError = t("Couldn't load this. Please check your connection.", "यह लोड नहीं हो सका। कृपया अपना इंटरनेट जाँचें।")
    val netError = t("No internet right now. Please check your connection and try again.",
        "अभी इंटरनेट नहीं है। कृपया अपना इंटरनेट जाँचकर फिर कोशिश करें।")
    val serverError = t("Something went wrong on our side. Please try again in a minute.",
        "हमारी तरफ़ कुछ गड़बड़ हुई। कृपया एक मिनट बाद फिर कोशिश करें।")
    val retry = t("Try again", "फिर कोशिश करें")
    val back = t("Back", "वापस")
    val close = t("Close", "बंद करें")
    val cancel = t("Cancel", "रद्द करें")
    val save = t("Save", "सेव करें")
    val saved = t("Saved", "सेव हो गया")

    // tabs
    val tabToday = t("Today", "आज")
    val tabMedicines = t("Medicines", "दवाइयाँ")
    val tabHistory = t("History", "इतिहास")
    val tabMe = t("Me", "मैं")

    // sign in (username + password, the main way in)
    val loginTitle = t("Sign in", "लॉगिन करें")
    val loginSub = t("Use the username and password your family set up for you.",
        "वही यूज़रनेम और पासवर्ड डालें जो आपके परिवार ने बनाया है।")
    val username = t("Username", "यूज़रनेम")
    val password = t("Password", "पासवर्ड")
    val showPassword = t("Show password", "पासवर्ड दिखाएँ")
    val hidePassword = t("Hide password", "पासवर्ड छिपाएँ")
    val signIn = t("Sign in", "लॉगिन करें")
    val signingIn = t("Signing in…", "लॉगिन हो रहा है…")
    val wrongLogin = t("Wrong username or password. Please check and try again.",
        "यूज़रनेम या पासवर्ड गलत है। कृपया जाँचकर फिर कोशिश करें।")
    val tooManyTries = t("Too many tries. Please wait 10 minutes, then try again.",
        "बहुत बार कोशिश हो गई। कृपया 10 मिनट रुककर फिर कोशिश करें।")
    val fillBoth = t("Please type both your username and password.", "कृपया यूज़रनेम और पासवर्ड दोनों लिखें।")
    val useCode = t("Use a code instead", "कोड से जोड़ें")
    val useLogin = t("Sign in with a username instead", "यूज़रनेम से लॉगिन करें")

    // pairing code (the fallback)
    val codeTitle = t("Type your code", "अपना कोड लिखें")
    val codeSub = t("On the computer, open VoiceMitra, go to “Me”, tap “Get a code” and type the 6 numbers here.",
        "कंप्यूटर पर VoiceMitra खोलें, “मैं” में जाएँ, “कोड पाएँ” दबाएँ और वे 6 अंक यहाँ लिखें।")
    val codeDigit = t("Digit {n}", "अंक {n}")
    val deleteDigit = t("Delete", "मिटाएँ")
    val connect = t("Connect", "जोड़ें")
    val wrongCode = t("That code didn't work. It may have expired. Please get a new code and try again.",
        "यह कोड नहीं चला। शायद इसका समय निकल गया। कृपया नया कोड लेकर फिर कोशिश करें।")

    // debug picker
    val pickPatient = t("Choose a patient (test builds only)", "मरीज़ चुनें (सिर्फ़ टेस्ट के लिए)")
    val pickPatientSub = t("Skips sign-in. Push rings won't reach this phone.", "लॉगिन छोड़ देता है। इस फ़ोन पर पुश कॉल नहीं आएगी।")
    val nobody = t("No one here yet.", "अभी यहाँ कोई नहीं है।")

    // today: talk card
    val talkTitle = t("Talk to VoiceMitra", "VoiceMitra से बात करें")
    val talkSub = t("A quick check-in takes about 2 minutes.", "छोटी-सी बातचीत में लगभग 2 मिनट लगते हैं।")
    val talkBtn = t("Start check-in", "बातचीत शुरू करें")
    val talkStarting = t("Starting…", "शुरू हो रहा है…")
    val talkInCall = t("Return to your call", "अपनी कॉल पर लौटें")
    val talkError = t("Couldn't start the call. Please try again.", "कॉल शुरू नहीं हो सकी। कृपया फिर कोशिश करें।")
    val lastCheckin = t("Last check-in {when}", "पिछली बातचीत {when}")
    val noCheckinYet = t("No check-ins yet", "अभी तक कोई बातचीत नहीं हुई")

    // today: doses
    val nextDose = t("Next dose", "अगली दवा")
    val todaysMeds = t("Today's medicines", "आज की दवाइयाँ")
    val noneToday = t("No medicines are scheduled for today.", "आज कोई दवा तय नहीं है।")
    val doseTaken = t("Taken", "ले ली")
    val dosePartial = t("Partly taken", "आधी ली")
    val doseMissed = t("Missed", "छूट गई")
    val doseLater = t("Taking later", "बाद में लेंगे")
    val doseUnknown = t("Not sure", "पक्का नहीं")
    val doseSkipped = t("Skipped on advice", "सलाह पर छोड़ी")
    val doseUpcoming = t("Upcoming", "आने वाली")
    val doseDue = t("Due now", "अभी लेनी है")
    val doseNoCheckin = t("Not checked", "पूछा नहीं गया")

    // today: the week
    val thisWeek = t("This week", "इस हफ़्ते")
    val weekSummary = t("{taken} of {total} doses taken", "{total} में से {taken} खुराकें ली गईं")
    val weekNone = t("Nothing was scheduled this week.", "इस हफ़्ते कुछ तय नहीं था।")
    val weekUnchecked = t("{n} not checked", "{n} के बारे में पूछा नहीं गया")
    val dayGood = t("All taken", "सब ली")
    val dayMixed = t("Some missed", "कुछ छूटीं")
    val dayMissed = t("Missed", "छूट गईं")
    val dayUnknown = t("Not checked", "पूछा नहीं गया")

    // today: how you're doing
    val howDoing = t("How you're doing", "आपकी सेहत")
    val doingOk = t("Looks fine", "सब ठीक लगा")
    val doingWatch = t("Worth telling your doctor", "डॉक्टर को बताना ठीक रहेगा")
    val doingUrgent = t("Needs a doctor's attention", "डॉक्टर को दिखाना ज़रूरी है")
    val reminder = t("Reminder", "रिमाइंडर")
    val reminderAt = t("VoiceMitra will call you at {time}", "VoiceMitra आपको {time} पर कॉल करेगा")
    val caregiverLine = t("{name} ({relation}) is told if we can't reach you or you're not feeling well.",
        "अगर आपसे बात न हो सके या आपकी तबीयत ठीक न हो, तो {name} ({relation}) को बताया जाता है।")

    // medicines
    val medsTitle = t("Your medicines", "आपकी दवाइयाँ")
    val allergies = t("Allergies", "एलर्जी")
    val noAllergies = t("No known allergies", "कोई ज्ञात एलर्जी नहीं")
    val medCurrent = t("Current", "अभी की")
    val medPast = t("Finished", "पूरी हो चुकीं")
    val medDaily = t("Every day at {times}", "रोज़ {times}")
    val medWeekly = t("Once a week at {times}", "हफ़्ते में एक बार, {times}")
    val medFixed = t("At {times}", "{times} पर")
    val medEvery = t("Every {n} days at {times}", "हर {n} दिन, {times}")
    val medUntil = t("until {date}", "{date} तक")
    val medDaysLeft = t("{n} days left", "{n} दिन बाकी")
    val medLastDay = t("Last day today", "आज आख़िरी दिन है")
    val medWeek = t("{taken} of {known} taken this week", "इस हफ़्ते {known} में से {taken} ली")
    val noMeds = t("No medicines on your list yet.", "आपकी सूची में अभी कोई दवा नहीं है।")

    // history
    val historyTitle = t("Your check-ins", "आपकी बातचीत")
    val checkin = t("Check-in call", "जाँच-बातचीत")
    val doctorJoined = t("A doctor joined this call", "इस कॉल में डॉक्टर जुड़े")
    val escalated = t("A doctor was contacted", "डॉक्टर से संपर्क किया गया")
    val mentioned = t("You mentioned: {list}", "आपने बताया: {list}")
    val nothingRecorded = t("Nothing was recorded on this call.", "इस कॉल में कुछ दर्ज नहीं हुआ।")
    val noHistory = t("No check-ins yet.", "अभी तक कोई बातचीत नहीं हुई।")
    val familyTold = t("Family were told", "परिवार को बताया गया")
    val medStatusTaken = t("Medicine taken", "दवा ली")
    val medStatusNotTaken = t("Medicine not taken", "दवा नहीं ली")
    val medStatusUnsure = t("Unsure about medicine", "दवा के बारे में पक्का नहीं")

    // me + settings
    val caregiver = t("Family contact", "परिवार का संपर्क")
    val language = t("Language", "भाषा")
    val settings = t("Settings", "सेटिंग")
    val serverUrl = t("Server address", "सर्वर का पता")
    val serverUrlHint = t("e.g. https://voicemitra.example.com", "जैसे https://voicemitra.example.com")
    val signedInAs = t("Signed in as {name}", "{name} के रूप में लॉगिन")
    val logOut = t("Sign out", "साइन आउट")
    val logOutConfirm = t("Sign out? You won't get calls on this phone until you sign in again.",
        "साइन आउट करें? दोबारा साइन इन करने तक इस फ़ोन पर कॉल नहीं आएगी।")
    val thisPhone = t("This phone", "यह फ़ोन")
    val phoneReady = t("VoiceMitra can ring this phone, even when it's locked.", "फ़ोन लॉक होने पर भी VoiceMitra की कॉल इस फ़ोन पर बजेगी।")
    val phoneFix = t("{n} settings to fix so VoiceMitra can ring you. Tap to fix.",
        "{n} सेटिंग ठीक करनी हैं ताकि VoiceMitra की कॉल बजे। ठीक करने के लिए दबाएँ।")
    val version = t("VoiceMitra {v}", "VoiceMitra {v}")
    val setupChecklist = t("Phone setup", "फ़ोन की सेटिंग")
    val setupAllGood = t("Ready to ring", "कॉल के लिए तैयार")
    val setupNeeded = t("{n} to fix", "{n} ठीक करना है")
    val advanced = t("Advanced", "और सेटिंग")

    // the call
    val incomingTitle = t("VoiceMitra is calling", "VoiceMitra कॉल कर रहा है")
    val incomingSub = t("About your medicines", "आपकी दवाइयों के बारे में")
    val calling = t("Calling…", "कॉल आ रही है…")
    val answer = t("Answer", "उठाएँ")
    val decline = t("Decline", "काटें")
    val callConnecting = t("Connecting…", "जोड़ा जा रहा है…")
    val callLive = t("Connected. Speak after VoiceMitra greets you.", "जुड़ गए। VoiceMitra के नमस्ते के बाद बोलें।")
    val callReconnecting = t("The line dropped. Reconnecting…", "लाइन कट गई। फिर से जोड़ा जा रहा है…")
    val callEnded = t("Call ended", "कॉल समाप्त हुई")
    val callFailed = t("Couldn't connect the call. Please try again.", "कॉल नहीं जुड़ सकी। कृपया फिर कोशिश करें।")
    val callOver = t("This call has already ended.", "यह कॉल पहले ही खत्म हो चुकी है।")
    val hangUp = t("End call", "कॉल खत्म करें")
    val mute = t("Mute", "आवाज़ बंद")
    val unmute = t("Unmute", "आवाज़ चालू")
    val speaker = t("Speaker", "स्पीकर")
    val earpiece = t("Phone", "फ़ोन")
    val micNeeded = t("VoiceMitra needs the microphone to hear you. Please allow it.",
        "आपकी बात सुनने के लिए VoiceMitra को माइक्रोफ़ोन चाहिए। कृपया अनुमति दें।")
    val youSaid = t("You", "आप")
    val agentSaid = t("VoiceMitra", "VoiceMitra")
    val ongoingTitle = t("On a call with VoiceMitra", "VoiceMitra से कॉल चल रही है")
    val channelCalls = t("Incoming calls", "आने वाली कॉल")
    val channelOngoing = t("Ongoing call", "चल रही कॉल")

    // setup checklist
    val setupTitle = t("Set up your phone", "अपना फ़ोन तैयार करें")
    val setupSub = t("So VoiceMitra can ring you even when the phone is locked. Tap each one that isn't ticked.",
        "ताकि फ़ोन लॉक होने पर भी VoiceMitra की कॉल बजे। जिस पर सही का निशान नहीं है, उसे दबाएँ।")
    val setupDone = t("All set. Your phone will ring for VoiceMitra calls.", "सब तैयार है। VoiceMitra की कॉल आपके फ़ोन पर बजेगी।")
    val permNotifications = t("Show calls", "कॉल दिखाना")
    val permNotificationsWhy = t("Lets VoiceMitra show its call on your screen.", "VoiceMitra अपनी कॉल आपकी स्क्रीन पर दिखा सके।")
    val permFullScreen = t("Ring on the lock screen", "लॉक स्क्रीन पर बजना")
    val permFullScreenWhy = t("Shows the call over the lock screen, like a normal call.", "आम कॉल की तरह लॉक स्क्रीन पर कॉल दिखे।")
    val permMic = t("Microphone", "माइक्रोफ़ोन")
    val permMicWhy = t("So VoiceMitra can hear you.", "ताकि VoiceMitra आपकी बात सुन सके।")
    val permBattery = t("Keep running in the background", "पीछे चलते रहना")
    val permBatteryWhy = t("Stops the phone from putting VoiceMitra to sleep. Choose “Allow”.", "फ़ोन VoiceMitra को बंद न करे। “Allow” चुनें।")
    val permAutostart = t("Allow auto-start", "ऑटो-स्टार्ट चालू करें")
    val permAutostartWhy = t("This phone has an extra setting: turn on “Auto-start” (or “Auto-launch”) for VoiceMitra.",
        "इस फ़ोन में एक और सेटिंग है: VoiceMitra के लिए “Auto-start” (या “Auto-launch”) चालू करें।")
    val allow = t("Allow", "अनुमति दें")
    val openSettings = t("Open settings", "सेटिंग खोलें")
    val continueBtn = t("Continue", "आगे बढ़ें")
    val skipForNow = t("Skip for now", "अभी छोड़ें")

    companion object {
        val EN = Strings(Lang.EN)
        val HI = Strings(Lang.HI)
        fun of(lang: Lang): Strings = if (lang == Lang.HI) HI else EN
    }
}
