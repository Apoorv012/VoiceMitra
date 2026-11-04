package com.voicemitra.patient

import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.Prefs
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.clock
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BasicsTest {
    @Test
    fun serverUrlIsTidiedUp() {
        assertEquals("https://voicemitra.example.com", Prefs.normaliseUrl("  voicemitra.example.com/ "))
        assertEquals("http://192.168.1.5:8000", Prefs.normaliseUrl("http://192.168.1.5:8000/"))
        assertEquals("", Prefs.normaliseUrl("   "))
    }

    @Test
    fun timesAreShownInThePatientsZone() {
        // 03:00 UTC is 8:30 in India.
        assertTrue(clock("2026-11-04T03:00:00Z", "Asia/Kolkata", Lang.EN).startsWith("8:30"))
        assertTrue(clock("2026-11-04T08:30:00+05:30", "Asia/Kolkata", Lang.HI).startsWith("8:30"))
        assertEquals("", clock("not a time", "Asia/Kolkata", Lang.EN))
    }

    @Test
    fun templatesFillIn() {
        val s = Strings.EN
        assertEquals("Hello, Sunita", s.fill(s.greeting, "name" to "Sunita"))
        assertEquals("नमस्ते, Sunita", Strings.HI.fill(Strings.HI.greeting, "name" to "Sunita"))
    }
}
