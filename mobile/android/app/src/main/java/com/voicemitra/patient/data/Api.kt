package com.voicemitra.patient.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

// --- what the backend sends (mobile/API.md; field names as in the JSON) -----------------------

@Serializable
data class PairResponse(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_token") val deviceToken: String,
    @SerialName("patient_id") val patientId: String,
    @SerialName("patient_name") val patientName: String,
)

@Serializable
data class DeviceInfo(
    @SerialName("device_id") val deviceId: String,
    @SerialName("patient_id") val patientId: String,
    @SerialName("patient_name") val patientName: String,
)

@Serializable
data class Person(val id: String, val name: String, val age: Int? = null, val description: String? = null)

@Serializable
data class People(val patients: List<Person> = emptyList())

@Serializable
data class Slot(
    @SerialName("dosage_id") val dosageId: String,
    val medicine: String,
    val dose: String,
    val at: String,       // ISO time, with offset
    val state: String,    // taken|partial|missed|later|unknown|skipped|upcoming|due|no_checkin
)

@Serializable
data class Caregiver(val name: String, val relation: String)

@Serializable
data class Checkin(
    @SerialName("call_id") val callId: String = "",
    val at: String,
    @SerialName("medicine_status") val medicineStatus: String? = null,
    @SerialName("patient_status") val patientStatus: String? = null,
    val summary: String? = null,
    val symptoms: List<String> = emptyList(),
    val escalated: Boolean = false,
    @SerialName("doctor_connected") val doctorConnected: Boolean = false,
)

@Serializable
data class Day(val date: String, val state: String, val taken: Int = 0, val due: Int = 0)

@Serializable
data class Adherence(val taken: Int = 0, val missed: Int = 0, val unrecorded: Int = 0, val rate: Int? = null)

@Serializable
data class HowDoing(val at: String, val summary: String, val band: String)  // band: ok|watch|urgent

@Serializable
data class PatientHome(
    val timezone: String = "Asia/Kolkata",
    val patient: Person,
    val allergies: List<String> = emptyList(),
    val today: List<Slot> = emptyList(),
    @SerialName("next_dose") val nextDose: Slot? = null,
    val week: List<Day> = emptyList(),
    val adherence: Adherence = Adherence(),
    @SerialName("last_checkin") val lastCheckin: Checkin? = null,
    @SerialName("how_doing") val howDoing: HowDoing? = null,
    val reminders: List<String> = emptyList(),
    val caregiver: Caregiver? = null,
)

@Serializable
data class Medicine(
    @SerialName("dosage_id") val dosageId: String,
    val name: String,
    val dose: String,
    val frequency: String,                       // daily|weekly|every_x_day|fixed_times
    @SerialName("interval_days") val intervalDays: Int? = null,
    val times: List<String> = emptyList(),       // "21:00"
    @SerialName("to_date") val toDate: String? = null,
    val active: Boolean = true,
    @SerialName("days_left") val daysLeft: Int? = null,
    val taken: Int = 0,                          // last 7 days
    val known: Int = 0,
)

@Serializable
data class PatientMedicines(
    val timezone: String = "Asia/Kolkata",
    val allergies: List<String> = emptyList(),
    val medicines: List<Medicine> = emptyList(),
)

@Serializable
data class Alert(val id: String, val at: String, val message: String, val caregiver: String? = null, val urgent: Boolean = false)

@Serializable
data class PatientHistory(
    val timezone: String = "Asia/Kolkata",
    val checkins: List<Checkin> = emptyList(),
    val alerts: List<Alert> = emptyList(),
)

@Serializable
data class VoiceJoin(@SerialName("call_id") val callId: String, val url: String, val token: String)

@Serializable
private data class LoginBody(
    val username: String, val password: String, val platform: String,
    @SerialName("push_token") val pushToken: String?, val name: String?,
)

@Serializable
private data class PairBody(
    val code: String, val platform: String, @SerialName("push_token") val pushToken: String?, val name: String?,
)

@Serializable
private data class PushTokenBody(@SerialName("push_token") val pushToken: String?)

/** The server answered, but not with success. `code` is the HTTP status (401, 404, 429 ...). */
class ApiException(val code: Int, message: String) : Exception(message)

/**
 * The backend's REST API. Every call throws [ApiException] for an HTTP error or [IOException] when the
 * server can't be reached; screens turn both into plain words with a "Try again".
 */
class Api(private val baseUrl: () -> String) {
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val json = Json { ignoreUnknownKeys = true; explicitNulls = true }
    private val jsonType = "application/json".toMediaType()

    suspend fun login(username: String, password: String, pushToken: String?, name: String?): PairResponse =
        post("/api/auth/login", LoginBody(username.trim(), password, "android", pushToken, name), LoginBody.serializer(),
            PairResponse.serializer())

    suspend fun pair(code: String, pushToken: String?, name: String?): PairResponse =
        post("/api/devices/pair", PairBody(code, "android", pushToken, name), PairBody.serializer(), PairResponse.serializer())

    suspend fun device(p: Pairing): DeviceInfo =
        send(Request.Builder().url(url("/api/devices/${p.deviceId}")).header(TOKEN, p.deviceToken).get().build(),
            DeviceInfo.serializer())

    suspend fun updatePushToken(p: Pairing, pushToken: String?) {
        val body = json.encodeToString(PushTokenBody.serializer(), PushTokenBody(pushToken)).toRequestBody(jsonType)
        sendNoContent(Request.Builder().url(url("/api/devices/${p.deviceId}")).header(TOKEN, p.deviceToken).put(body).build())
    }

    suspend fun unpair(p: Pairing) =
        sendNoContent(Request.Builder().url(url("/api/devices/${p.deviceId}")).header(TOKEN, p.deviceToken).delete().build())

    suspend fun people(): People = send(Request.Builder().url(url("/api/app/people")).get().build(), People.serializer())

    suspend fun home(patientId: String): PatientHome =
        send(Request.Builder().url(url("/api/app/patients/$patientId/home")).get().build(), PatientHome.serializer())

    suspend fun medicines(patientId: String): PatientMedicines =
        send(Request.Builder().url(url("/api/app/patients/$patientId/medicines")).get().build(), PatientMedicines.serializer())

    suspend fun history(patientId: String): PatientHistory =
        send(Request.Builder().url(url("/api/app/patients/$patientId/history")).get().build(), PatientHistory.serializer())

    /** Talk now. The token tells the backend not to ring this phone for the call it is starting itself. */
    suspend fun startVoiceCall(patientId: String, deviceToken: String?) {
        val req = Request.Builder().url(url("/api/patients/$patientId/voice-call")).post(EMPTY)
        if (deviceToken != null) req.header(TOKEN, deviceToken)
        sendNoContent(req.build())
    }

    /** Join details for the call in progress; null when there is none (it already ended). */
    suspend fun voiceCall(patientId: String): VoiceJoin? = try {
        send(Request.Builder().url(url("/api/patients/$patientId/voice-call")).get().build(), VoiceJoin.serializer())
    } catch (e: ApiException) {
        if (e.code == 404) null else throw e
    }

    suspend fun endCall(patientId: String) =
        sendNoContent(Request.Builder().url(url("/api/patients/$patientId/call/end")).post(EMPTY).build())

    /** `wss://host/ws/patients/{id}/chat` for the patient's live events. */
    fun socketUrl(patientId: String): String =
        url("/ws/patients/$patientId/chat").replaceFirst("https://", "wss://").replaceFirst("http://", "ws://")

    // --- plumbing -------------------------------------------------------------------------------

    private fun url(path: String) = baseUrl().trimEnd('/') + path

    private suspend fun <B, T> post(path: String, body: B, bodySer: KSerializer<B>, outSer: KSerializer<T>): T {
        val rb = json.encodeToString(bodySer, body).toRequestBody(jsonType)
        return send(Request.Builder().url(url(path)).post(rb).build(), outSer)
    }

    private suspend fun <T> send(request: Request, ser: KSerializer<T>): T = withContext(Dispatchers.IO) {
        http.newCall(request).execute().use { res ->
            val text = res.body.string()
            if (!res.isSuccessful) throw ApiException(res.code, detail(text) ?: "HTTP ${res.code}")
            try {
                json.decodeFromString(ser, text)
            } catch (e: Exception) {
                throw IOException("unexpected reply from the server", e)
            }
        }
    }

    private suspend fun sendNoContent(request: Request) = withContext(Dispatchers.IO) {
        http.newCall(request).execute().use { res ->
            if (!res.isSuccessful) throw ApiException(res.code, detail(res.body.string()) ?: "HTTP ${res.code}")
        }
    }

    private fun detail(text: String): String? = try {
        json.decodeFromString(Detail.serializer(), text).detail
    } catch (_: Exception) {
        null
    }

    @Serializable
    private data class Detail(val detail: String? = null)

    private companion object {
        const val TOKEN = "X-Device-Token"
        val EMPTY: RequestBody = ByteArray(0).toRequestBody(null)
    }
}
