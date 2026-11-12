package com.voicemitra.patient

import android.Manifest
import android.app.Application
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import com.voicemitra.patient.call.CallScreen
import com.voicemitra.patient.call.CallState
import com.voicemitra.patient.call.Line
import com.voicemitra.patient.data.Adherence
import com.voicemitra.patient.data.Alert
import com.voicemitra.patient.data.Caregiver
import com.voicemitra.patient.data.Checkin
import com.voicemitra.patient.data.Day
import com.voicemitra.patient.data.HowDoing
import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.Medicine
import com.voicemitra.patient.data.Pairing
import com.voicemitra.patient.data.PatientHistory
import com.voicemitra.patient.data.PatientHome
import com.voicemitra.patient.data.PatientMedicines
import com.voicemitra.patient.data.Person
import com.voicemitra.patient.data.Settings
import com.voicemitra.patient.data.Slot
import com.voicemitra.patient.ui.CodeScreen
import com.voicemitra.patient.ui.HistoryBody
import com.voicemitra.patient.ui.LocalNow
import com.voicemitra.patient.ui.LocalStrings
import com.voicemitra.patient.ui.LoginScreen
import com.voicemitra.patient.ui.MeBody
import com.voicemitra.patient.ui.MedicinesBody
import com.voicemitra.patient.ui.ErrorState
import com.voicemitra.patient.ui.H1
import com.voicemitra.patient.ui.SetupScreen
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.TabPage
import com.voicemitra.patient.ui.TalkState
import com.voicemitra.patient.ui.TodayBody
import com.voicemitra.patient.ui.VoiceMitraTheme
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import java.time.ZonedDateTime

/**
 * Every screen rendered to a PNG on the JVM (Robolectric's native graphics; no emulator), at a typical
 * phone size: 1080x2400 px at 420 dpi = 411x914 dp, light/dark x English/Hindi, inside the app's real
 * frame (header + tab bar). The clock is fixed: Thursday 5 November 2026, 1:40 PM in India.
 *
 *     ./gradlew.bat screenshots        -> mobile/android/screenshots/<nn_screen>_<en|hi>_<light|dark>.png
 *
 * Plain `testDebugUnitTest` runs these too, but only draws (records nothing).
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(application = Application::class, qualifiers = "w411dp-h914dp-420dpi")
class ScreenshotTest {
    private val out = File(System.getProperty("vm.shots") ?: "../screenshots")
    private val now = ZonedDateTime.parse("2026-11-05T13:40:00+05:30[Asia/Kolkata]")

    /** Render `content` light and dark, in English and Hindi, inside the app frame (`tab` = signed in). */
    private fun shoot(
        name: String, tab: Screen? = null, frame: Boolean = true, signedIn: Boolean = tab != null,
        content: @Composable (Lang) -> Unit,
    ) {
        for (dark in listOf(false, true)) {
            RuntimeEnvironment.setQualifiers(if (dark) "+night" else "+notnight")
            for (lang in listOf(Lang.EN, Lang.HI)) {
                val file = File(out, "${name}_${lang.name.lowercase()}_${if (dark) "dark" else "light"}.png")
                captureRoboImage(file.path) {
                    CompositionLocalProvider(LocalNow provides { now }) {
                        VoiceMitraTheme(Strings.of(lang), dark = dark) {
                            if (frame) AppFrame(lang, {}, tab = tab, onTab = {}) { content(lang) }
                            else content(lang)
                        }
                    }
                }
            }
        }
    }

    @Test
    fun login() = shoot("01_login") { lang -> LoginScreen(onUseCode = {}, settings = SampleData.settings(lang)) }

    @Test
    fun codePad() = shoot("02_code") { CodeScreen(onUseLogin = {}, initial = "482") }

    @Test
    fun today() = shoot("03_today", tab = Screen.Today) {
        TabPage { TodayBody(SampleData.home, TalkState.Idle, onTalk = {}) }
    }

    @Test
    fun medicines() = shoot("04_medicines", tab = Screen.Medicines) {
        TabPage {
            H1(LocalStrings.current.medsTitle)
            MedicinesBody(SampleData.medicines)
        }
    }

    @Test
    fun history() = shoot("05_history", tab = Screen.History) {
        TabPage {
            H1(LocalStrings.current.historyTitle)
            HistoryBody(SampleData.history)
        }
    }

    @Test
    fun me() = shoot("06_me", tab = Screen.Me) { lang ->
        TabPage {
            MeBody("Sunita Verma", SampleData.home, SampleData.settings(lang), setupLeft = 2, {}, {}, {}, {})
        }
    }

    @Test
    fun signOutDialog() = shoot("06_me_signout", tab = Screen.Me) { lang ->
        TabPage {
            MeBody("Sunita Verma", SampleData.home, SampleData.settings(lang), setupLeft = 2, {}, {}, {}, {}, confirmAtStart = true)
        }
    }

    @Test
    fun setupChecklist() {
        // Some ticks done: microphone allowed, notifications on; battery and full-screen still to do.
        shadowOf(ApplicationProvider.getApplicationContext<Application>()).grantPermissions(Manifest.permission.RECORD_AUDIO)
        shoot("07_setup", tab = null, signedIn = true) { SetupScreen(onDone = {}) }
    }

    // Full-length pages (a tall "phone"), so everything below the fold can be checked too.
    @Test
    @Config(qualifiers = "w411dp-h2300dp-420dpi")
    fun fullLength() {
        shoot("03_today_full", tab = Screen.Today) { TabPage { TodayBody(SampleData.home, TalkState.Idle, onTalk = {}) } }
        shoot("04_medicines_full", tab = Screen.Medicines) {
            TabPage { H1(LocalStrings.current.medsTitle); MedicinesBody(SampleData.medicines) }
        }
        shoot("05_history_full", tab = Screen.History) {
            TabPage { H1(LocalStrings.current.historyTitle); HistoryBody(SampleData.history) }
        }
        shadowOf(ApplicationProvider.getApplicationContext<Application>()).grantPermissions(Manifest.permission.RECORD_AUDIO)
        shoot("07_setup_full", signedIn = true) { SetupScreen(onDone = {}) }
    }

    @Test
    fun incomingCall() = shoot("08_incoming", frame = false) {
        CallScreen(CallState.Ringing("c1"), emptyList(), {}, {}, {}, {}, {})
    }

    @Test
    fun inCall() = shoot("09_in_call", frame = false) {
        CallScreen(
            CallState.InCall("c1", startedAt = System.currentTimeMillis() - 83_000, muted = true, agentJoined = true),
            SampleData.transcript, {}, {}, {}, {}, {},
        )
    }

    @Test
    fun offline() = shoot("11_offline", tab = Screen.Today) {
        TabPage { ErrorState(LocalStrings.current.netError, onRetry = {}, offline = true) }
    }

}

/** Realistic sample data for screenshots (the day is Thursday 5 November 2026). */
object SampleData {
    private fun slot(name: String, dose: String, at: String, state: String) =
        Slot(dosageId = name, medicine = name, dose = dose, at = at, state = state)

    fun settings(lang: Lang) = Settings("https://test-voicemitra.apoorvm.com", lang, Pairing("d", "t", "p1", "Sunita Verma"))

    val home = PatientHome(
        timezone = "Asia/Kolkata",
        patient = Person(id = "p1", name = "Sunita Verma", age = 72),
        allergies = listOf("Penicillin"),
        today = listOf(
            slot("Metformin", "500 mg", "2026-11-05T08:30:00+05:30", "taken"),
            slot("Amlodipine", "5 mg", "2026-11-05T08:30:00+05:30", "missed"),
            slot("Metformin", "500 mg", "2026-11-05T14:00:00+05:30", "upcoming"),
            slot("Atorvastatin", "10 mg", "2026-11-05T21:00:00+05:30", "upcoming"),
        ),
        nextDose = slot("Metformin", "500 mg", "2026-11-05T14:00:00+05:30", "upcoming"),
        week = listOf(
            Day("2026-10-30", "good", 3, 3), Day("2026-10-31", "good", 3, 3), Day("2026-11-01", "mixed", 2, 3),
            Day("2026-11-02", "good", 3, 3), Day("2026-11-03", "unknown", 0, 3), Day("2026-11-04", "good", 3, 3),
            Day("2026-11-05", "mixed", 1, 4),
        ),
        adherence = Adherence(taken = 15, missed = 2, unrecorded = 3),
        lastCheckin = Checkin(at = "2026-11-05T08:42:00+05:30"),
        howDoing = HowDoing(at = "2026-11-05T08:42:00+05:30", summary = "Slight headache since yesterday, otherwise fine.", band = "ok"),
        reminders = listOf("2026-11-05T15:00:00+05:30"),
        caregiver = Caregiver("Rahul", "son"),
    )

    val medicines = PatientMedicines(
        allergies = listOf("Penicillin"),
        medicines = listOf(
            Medicine("m1", "Metformin", "500 mg", "daily", times = listOf("08:30", "14:00"), toDate = "2026-12-31", daysLeft = 56, taken = 12, known = 13),
            Medicine("m2", "Amlodipine", "5 mg", "daily", times = listOf("08:30"), taken = 4, known = 6),
            Medicine("m3", "Vitamin D3", "60,000 IU", "weekly", times = listOf("09:00"), taken = 1, known = 1),
            Medicine("m4", "Amoxicillin", "250 mg", "daily", times = listOf("08:00", "20:00"), toDate = "2026-10-20", active = false),
        ),
    )

    val history = PatientHistory(
        checkins = listOf(
            Checkin("c3", "2026-11-05T08:42:00+05:30", medicineStatus = "taken", patientStatus = "good",
                summary = "Took Metformin; forgot Amlodipine and will take it after lunch.", symptoms = listOf("headache")),
            Checkin("c2", "2026-11-04T20:05:00+05:30", medicineStatus = "taken", patientStatus = "good", summary = "All evening medicines taken."),
            Checkin("c2b", "2026-11-04T08:31:00+05:30"),  // nothing was logged on this call (e.g. it dropped)
            Checkin("c1", "2026-11-03T08:35:00+05:30", medicineStatus = "not_taken", patientStatus = "remedy",
                summary = "Felt dizzy in the morning; skipped breakfast and medicines.", symptoms = listOf("dizziness")),
        ),
        alerts = listOf(Alert("a1", "2026-11-03T08:40:00+05:30", "Sunita said she felt dizzy this morning and skipped her medicines.", "Rahul")),
    )

    val transcript = listOf(
        Line(false, "Namaste Sunita ji! Kya aapne subah 8:30 wali Metformin le li?"),
        Line(true, "Haan, le li thi. Amlodipine bhool gayi."),
        Line(false, "Koi baat nahi. Kya aap abhi Amlodipine le sakti hain?"),
    )
}
