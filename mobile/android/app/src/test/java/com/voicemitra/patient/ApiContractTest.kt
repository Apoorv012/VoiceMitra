package com.voicemitra.patient

import com.voicemitra.patient.data.Api
import com.voicemitra.patient.data.ApiException
import com.voicemitra.patient.data.Pairing
import com.voicemitra.patient.data.Person
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/**
 * The app's own API client against a running backend (mobile/API.md). Skipped unless a server is given:
 *
 *     ./gradlew.bat testDebugUnitTest -PvmServer=http://127.0.0.1:8100 -PvmStaff=<user>:<password>
 *
 * Use a backend on a throwaway database (MONGODB_DB_NAME ending in `test`) with at least one patient and a
 * staff login (`python -m backend.create_staff`): the test signs in as staff for its setup calls, sets the
 * patient's login and pairs/unpairs devices.
 */
class ApiContractTest {
    private val server = System.getProperty("vm.server").orEmpty()
    private val staff = System.getProperty("vm.staff").orEmpty()
    private var token: String? = null
    private val api = Api({ server }, { token })
    private var staffCookie = ""
    private val raw = OkHttpClient()
    private val json = "application/json".toMediaType()

    private fun call(method: String, path: String, body: String? = null): Pair<Int, String> {
        val rb = body?.toRequestBody(json) ?: if (method == "POST" || method == "PUT") "".toRequestBody(null) else null
        val req = Request.Builder().url(server + path).method(method, rb).header("Cookie", staffCookie).build()
        raw.newCall(req).execute().use { return it.code to it.body.string() }
    }

    private fun signInAsStaff() {
        val (user, password) = staff.split(":", limit = 2)
        val body = """{"username": "$user", "password": "$password"}""".toRequestBody(json)
        raw.newCall(Request.Builder().url("$server/api/auth/session").post(body).build()).execute().use {
            assertEquals(200, it.code)
            staffCookie = it.header("Set-Cookie")!!.substringBefore(";")
        }
    }

    private fun codeOf(block: suspend () -> Unit): Int = try {
        runBlocking { block() }
        200
    } catch (e: ApiException) {
        e.code
    }

    @Test
    fun loginPairCheckAndUnpair() = runBlocking {
        assumeTrue("no -PvmServer / -PvmStaff given", server.isNotEmpty() && staff.contains(":"))
        signInAsStaff()
        val (_, peopleJson) = call("GET", "/api/app/people")
        val patientId = Regex(""""patients"\s*:\s*\[\s*\{\s*"id"\s*:\s*"([^"]+)"""").find(peopleJson)!!.groupValues[1]
        val patient = Person(patientId, "")
        // Without a device token the server tells a phone nothing about the patient.
        assertEquals(401, codeOf { api.home(patient.id) })

        // Login (the main way in): wrong password -> 401, right one -> a device.
        val (status, _) = call("PUT", "/api/patients/${patient.id}/login",
            """{"username": "apptest-${patient.id.take(8)}", "password": "secret123"}""")
        assertEquals(204, status)
        assertEquals(401, codeOf { api.login("apptest-${patient.id.take(8)}", "nope", null, "JVM test") })
        val viaLogin = api.login("  APPTEST-${patient.id.take(8)} ", "secret123", "fcm-jvm-test", "JVM test")
        assertEquals(patient.id, viaLogin.patientId)
        val p1 = Pairing(viaLogin.deviceId, viaLogin.deviceToken, viaLogin.patientId, viaLogin.patientName)
        token = p1.deviceToken  // from here on every request carries it, as in the app
        assertEquals(patient.id, api.device(p1).patientId)
        api.updatePushToken(p1, "fcm-jvm-test-2")

        // Pairing code (the fallback): wrong code -> 400, the shown one -> a device.
        val (_, codeJson) = call("POST", "/api/patients/${patient.id}/pairing-code")
        val code = Regex(""""code"\s*:\s*"(\d{6})"""").find(codeJson)!!.groupValues[1]
        val wrong = ((code.toInt() + 1) % 1_000_000).toString().padStart(6, '0')
        assertEquals(400, codeOf { api.pair(wrong, null, null) })
        val viaCode = api.pair("${code.take(3)} ${code.drop(3)}", null, "JVM test 2")
        val p2 = Pairing(viaCode.deviceId, viaCode.deviceToken, viaCode.patientId, viaCode.patientName)

        // Reading the home screen and the (absent) call.
        assertEquals(patient.id, api.home(patient.id).patient.id)
        // The Medicines and History tabs parse what the backend sends (with a real prescription in it).
        val (rx, _) = call("POST", "/api/patients/${patient.id}/prescriptions", """{"medicines": [{"medicine_name": "Metformin",
            "dosage": "500 mg", "from_date": "2026-01-01", "frequency": "daily", "times": ["08:30", "20:00"]}]}""")
        assertEquals(200, rx)
        val meds = api.medicines(patient.id).medicines
        assertTrue(meds.any { it.name == "Metformin" && it.times == listOf("08:30", "20:00") })
        assertTrue(api.home(patient.id).today.isNotEmpty())
        api.history(patient.id)
        assertNull(api.voiceCall(patient.id))
        assertTrue(api.socketUrl(patient.id).startsWith("ws"))

        // Log out: the device is gone, a wrong token is refused.
        assertEquals(401, codeOf { api.device(p2.copy(deviceToken = "wrong")) })
        api.unpair(p1)
        api.unpair(p2)
        assertEquals(404, codeOf { api.device(p1) })
        call("DELETE", "/api/patients/${patient.id}/login")
        Unit
    }
}
