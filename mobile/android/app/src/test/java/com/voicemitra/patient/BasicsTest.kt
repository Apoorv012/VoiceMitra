package com.voicemitra.patient

import com.voicemitra.patient.data.DeviceInfo
import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.PairResponse
import com.voicemitra.patient.data.Pairing
import com.voicemitra.patient.data.Prefs
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.clock
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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

    private val json = Json { ignoreUnknownKeys = true }

    @Test
    fun aMissingRoleIsAPatient() {
        // An older server (before C1) sends no role.
        val old = json.decodeFromString(PairResponse.serializer(),
            """{"device_id": "d", "device_token": "t", "patient_id": "p", "patient_name": "Sunita"}""")
        assertEquals("patient", Pairing.roleOf(old.role))
        assertFalse(Pairing("d", "t", "p", "Sunita", Pairing.roleOf(old.role)).isCaregiver)

        val family = json.decodeFromString(PairResponse.serializer(), """{"device_id": "d", "device_token": "t",
            "role": "caregiver", "patient_id": "p", "patient_name": "Sunita Devi", "caregiver_id": "c1",
            "caregiver_name": "Rahul"}""")
        val p = Pairing(family.deviceId, family.deviceToken, family.patientId, family.patientName,
            Pairing.roleOf(family.role), family.caregiverId, family.caregiverName)
        assertTrue(p.isCaregiver)
        assertEquals("Sunita", p.patientFirstName)
        // A caregiver role without an id can't use the caregiver routes: treated as not a caregiver phone.
        assertFalse(p.copy(caregiverId = null).isCaregiver)

        val info = json.decodeFromString(DeviceInfo.serializer(), """{"device_id": "d", "role": "patient",
            "patient_id": "p", "patient_name": "Sunita", "caregiver_id": null, "caregiver_name": null}""")
        assertEquals("patient", Pairing.roleOf(info.role))
    }

    @Test
    fun alertNotificationCarriesNoHealthInformation() {
        val s = Strings.EN
        assertEquals("Update about Sunita", s.fill(s.alertTitle, "name" to "Sunita"))
        assertEquals("सुनीता के बारे में नई जानकारी", Strings.HI.fill(Strings.HI.alertTitle, "name" to "सुनीता"))
    }

    @Test
    fun templatesFillIn() {
        val s = Strings.EN
        assertEquals("Hello, Sunita", s.fill(s.greeting, "name" to "Sunita"))
        assertEquals("नमस्ते, Sunita", Strings.HI.fill(Strings.HI.greeting, "name" to "Sunita"))
    }
}
