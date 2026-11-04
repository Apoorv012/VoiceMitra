package com.voicemitra.patient.call

import android.Manifest
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat

/**
 * Keeps the app alive (and the microphone allowed) while a call is connecting or connected, so it
 * survives the screen locking. The call itself lives in [CallManager]; this only holds the foreground.
 */
class CallService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val micGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_PHONE_CALL or
                (if (micGranted) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0)
        } else {
            0
        }
        try {
            ServiceCompat.startForeground(this, Notifications.ID_ONGOING, Notifications.ongoing(this), type)
        } catch (e: Exception) {
            // Not allowed right now (e.g. started from the background on Android 14+): the call still
            // works while the screen is on.
            Log.w("CallService", "startForeground failed", e)
            stopSelf()
        }
        return START_NOT_STICKY
    }

    companion object {
        fun start(context: Context) {
            try {
                ContextCompat.startForegroundService(context, Intent(context, CallService::class.java))
            } catch (e: Exception) {
                Log.w("CallService", "could not start", e)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, CallService::class.java))
        }
    }
}
