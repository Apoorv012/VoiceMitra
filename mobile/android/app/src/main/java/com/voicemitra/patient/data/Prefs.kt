package com.voicemitra.patient.data

import android.content.Context
import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.voicemitra.patient.BuildConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.store by preferencesDataStore(name = "voicemitra")

/**
 * Who this phone belongs to, after logging in or pairing (mobile/API.md). A family contact's phone
 * (`role` caregiver, C1) has `caregiverId`; `patientId` is then the patient they look after.
 */
data class Pairing(
    val deviceId: String,
    val deviceToken: String,
    val patientId: String,
    val patientName: String,
    val role: String = ROLE_PATIENT,
    val caregiverId: String? = null,
    val caregiverName: String? = null,
) {
    /** A caregiver phone: the caregiver home only -- no patient socket, no ringing. */
    val isCaregiver get() = role == ROLE_CAREGIVER && caregiverId != null

    /** "Sunita Devi" -> "Sunita" (notifications, headings). */
    val patientFirstName get() = patientName.trim().substringBefore(' ')

    companion object {
        const val ROLE_PATIENT = "patient"
        const val ROLE_CAREGIVER = "caregiver"

        /** What the server said (a missing or unknown role = patient). */
        fun roleOf(raw: String?) = if (raw == ROLE_CAREGIVER) ROLE_CAREGIVER else ROLE_PATIENT
    }
}

data class Settings(
    val serverUrl: String,
    val lang: Lang,
    val pairing: Pairing?,
)

enum class Lang { EN, HI }

/**
 * Everything the app remembers, in app-private storage (not backed up: `allowBackup=false`). The device
 * token is the phone's only credential; it never leaves this file except in the `X-Device-Token` header.
 */
class Prefs(private val context: Context) {
    private object K {
        val server = stringPreferencesKey("server_url")
        val lang = stringPreferencesKey("lang")
        val deviceId = stringPreferencesKey("device_id")
        val deviceToken = stringPreferencesKey("device_token")
        val patientId = stringPreferencesKey("patient_id")
        val patientName = stringPreferencesKey("patient_name")
        val role = stringPreferencesKey("role")
        val caregiverId = stringPreferencesKey("caregiver_id")
        val caregiverName = stringPreferencesKey("caregiver_name")
        val pushToken = stringPreferencesKey("push_token_sent")
    }

    val settings: Flow<Settings> = context.store.data.map { it.toSettings() }

    suspend fun current(): Settings = context.store.data.first().toSettings()

    private fun Preferences.toSettings(): Settings {
        val pairing = run {
            val id = this[K.deviceId] ?: return@run null
            val token = this[K.deviceToken] ?: return@run null
            val patient = this[K.patientId] ?: return@run null
            Pairing(id, token, patient, this[K.patientName] ?: "", Pairing.roleOf(this[K.role]), this[K.caregiverId],
                this[K.caregiverName])
        }
        return Settings(
            serverUrl = this[K.server]?.takeIf { it.isNotBlank() } ?: BuildConfig.DEFAULT_SERVER_URL,
            lang = if (this[K.lang] == "hi") Lang.HI else if (this[K.lang] == "en") Lang.EN else systemLang(),
            pairing = pairing,
        )
    }

    private fun systemLang(): Lang =
        if (context.resources.configuration.locales[0].language == "hi") Lang.HI else Lang.EN

    suspend fun setServerUrl(url: String) = context.store.edit { it[K.server] = normaliseUrl(url) }

    suspend fun setLang(lang: Lang) = context.store.edit { it[K.lang] = if (lang == Lang.HI) "hi" else "en" }

    suspend fun savePairing(p: Pairing, pushTokenSent: String?) = context.store.edit {
        it[K.deviceId] = p.deviceId
        it[K.deviceToken] = p.deviceToken
        it[K.patientId] = p.patientId
        it[K.patientName] = p.patientName
        it.putIdentity(p.role, p.caregiverId, p.caregiverName)
        if (pushTokenSent != null) it[K.pushToken] = pushTokenSent else it.remove(K.pushToken)
    }

    /** The launch check (`GET /api/devices/{id}`) says who this phone is now: keep names and role current. */
    suspend fun updateIdentity(patientName: String, role: String, caregiverId: String?, caregiverName: String?) =
        context.store.edit {
            if (it[K.deviceId] == null) return@edit  // signed out meanwhile
            it[K.patientName] = patientName
            it.putIdentity(role, caregiverId, caregiverName)
        }

    private fun MutablePreferences.putIdentity(role: String, caregiverId: String?, caregiverName: String?) {
        this[K.role] = role
        if (caregiverId != null) this[K.caregiverId] = caregiverId else remove(K.caregiverId)
        if (caregiverName != null) this[K.caregiverName] = caregiverName else remove(K.caregiverName)
    }

    suspend fun clearPairing() = context.store.edit {
        it.remove(K.deviceId); it.remove(K.deviceToken); it.remove(K.patientId); it.remove(K.patientName)
        it.remove(K.role); it.remove(K.caregiverId); it.remove(K.caregiverName)
        it.remove(K.pushToken)
    }

    suspend fun pushTokenSent(): String? = context.store.data.first()[K.pushToken]

    suspend fun setPushTokenSent(token: String) = context.store.edit { it[K.pushToken] = token }

    companion object {
        /** "example.com/" -> "https://example.com": what people type into a settings field. */
        fun normaliseUrl(raw: String): String {
            var url = raw.trim().trimEnd('/')
            if (url.isEmpty()) return ""
            if (!url.startsWith("http://") && !url.startsWith("https://")) url = "https://$url"
            return url
        }
    }
}
