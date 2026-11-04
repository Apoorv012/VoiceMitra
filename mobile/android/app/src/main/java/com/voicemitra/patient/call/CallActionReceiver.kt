package com.voicemitra.patient.call

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.voicemitra.patient.App

/** Decline / hang up from a notification button, without opening the app. */
class CallActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val calls = App.instance.calls
        when (intent.action) {
            ACTION_DECLINE -> calls.decline()
            ACTION_HANG_UP -> calls.hangUp()
        }
    }

    companion object {
        const val ACTION_DECLINE = "com.voicemitra.patient.DECLINE"
        const val ACTION_HANG_UP = "com.voicemitra.patient.HANG_UP"

        fun pending(context: Context, action: String, callId: String?): PendingIntent =
            PendingIntent.getBroadcast(
                context, action.hashCode(),
                Intent(context, CallActionReceiver::class.java).setAction(action).putExtra("call_id", callId),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
    }
}
