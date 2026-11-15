package com.voicemitra.patient.push

import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.voicemitra.patient.App
import com.voicemitra.patient.call.Notifications
import kotlinx.coroutines.launch

/**
 * FCM data messages (mobile/API.md "Push"). A patient's phone: `ring` and `call_ended` (wakes the app even
 * when locked). A family contact's phone (C1): `alert` -> an ordinary notification; it never rings, so a
 * stale `ring` (e.g. a token left over from a patient sign-in) is ignored.
 */
class PushService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val app = App.instance
        val pairing = app.settings.value.pairing ?: return
        if (data["patient_id"] != pairing.patientId) return  // a token left over from an earlier pairing
        if (pairing.isCaregiver) {
            if (data["type"] == "alert" && data["caregiver_id"] == pairing.caregiverId) {
                Notifications.showAlert(app, pairing.patientFirstName)
            }
            return
        }
        val callId = data["call_id"] ?: return
        when (data["type"]) {
            "ring" -> app.scope.launch { app.calls.onRing(callId) }
            "call_ended" -> app.scope.launch { app.calls.onRemoteEnded(callId) }
        }
    }

    @Deprecated("FCM tokens are deprecated for FIDs; still delivered (see PushToken)")
    override fun onNewToken(token: String) {
        Log.i("PushService", "new FCM token")
        val app = App.instance
        app.scope.launch { PushToken.sendIfChanged(app, token) }
    }
}
