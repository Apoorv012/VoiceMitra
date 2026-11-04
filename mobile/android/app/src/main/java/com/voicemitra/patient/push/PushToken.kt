package com.voicemitra.patient.push

import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import com.voicemitra.patient.App
import com.voicemitra.patient.BuildConfig
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

object PushToken {
    /**
     * This phone's FCM registration token, or null (no Firebase config in this build, or no network).
     * Firebase Messaging 26 deprecates tokens in favour of Firebase Installation IDs (`register()` ->
     * `onRegistered(fid)`, sent with `Message(fid=...)` on the backend). Tokens still work on both sides;
     * moving to FIDs is a contract change (mobile/API.md) for later.
     */
    @Suppress("DEPRECATION")
    suspend fun get(app: App): String? {
        if (!BuildConfig.HAS_FIREBASE || FirebaseApp.getApps(app).isEmpty()) return null
        return withTimeoutOrNull(10_000) {
            suspendCancellableCoroutine { cont ->
                FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
                    if (!task.isSuccessful) Log.w("PushToken", "no FCM token", task.exception)
                    cont.resume(if (task.isSuccessful) task.result else null)
                }
            }
        }
    }

    /** Tell the backend about a new token (FCM rotates them), once per token. */
    suspend fun sendIfChanged(app: App, token: String?) {
        val pairing = app.settings.value.pairing ?: return
        val t = token ?: get(app) ?: return
        if (app.prefs.pushTokenSent() == t) return
        try {
            app.api.updatePushToken(pairing, t)
            app.prefs.setPushTokenSent(t)
        } catch (e: Exception) {
            Log.w("PushToken", "could not send the push token", e)
        }
    }
}
