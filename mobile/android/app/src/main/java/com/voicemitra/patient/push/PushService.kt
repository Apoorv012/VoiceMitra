package com.voicemitra.patient.push

import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.voicemitra.patient.App
import kotlinx.coroutines.launch

/** FCM data messages (mobile/API.md "Push"): `ring` and `call_ended`. Wakes the app even when locked. */
class PushService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val app = App.instance
        val pairing = app.settings.value.pairing ?: return
        if (data["patient_id"] != pairing.patientId) return  // a token left over from an earlier pairing
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
