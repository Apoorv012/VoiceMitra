package com.voicemitra.patient.call

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.voicemitra.patient.App
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.VoiceMitraTheme

/**
 * The call screen (drawn by [CallScreen]), for ringing and for the call itself. Opens over the lock screen
 * and turns the screen on (the ring notification's full-screen intent), like the phone's own call screen.
 */
class CallActivity : ComponentActivity() {
    private val calls get() = App.instance.calls
    private var answerAfterMic = false

    private val askMic = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            if (answerAfterMic) calls.answer(this) else calls.talkNow(this)
        } else if (answerAfterMic) {
            calls.onMicDenied()  // says why, then closes
        } else {
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        showOverLockScreen()
        enableEdgeToEdge()
        setContent {
            val settings by App.instance.settings.collectAsStateWithLifecycle()
            val state by calls.state.collectAsStateWithLifecycle()
            val transcript by calls.transcript.collectAsStateWithLifecycle()
            VoiceMitraTheme(Strings.of(settings.lang)) {
                // Close once the call is over (the screen opens before Talk now's call exists, so only
                // after it has been active).
                var wasActive by remember { mutableStateOf(false) }
                LaunchedEffect(state) {
                    if (state !is CallState.Idle) wasActive = true else if (wasActive) finish()
                }
                CallScreen(
                    state = state,
                    transcript = transcript,
                    onAnswer = ::answer,
                    onDecline = calls::decline,
                    onHangUp = calls::hangUp,
                    onMute = calls::setMuted,
                    onSpeaker = calls::setSpeaker,
                )
            }
        }
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        when (intent?.action) {
            ACTION_SHOW -> if (calls.state.value is CallState.Idle) finish()  // a stale notification
            ACTION_ANSWER -> answer()
            ACTION_TALK -> {
                answerAfterMic = false
                if (hasMic()) calls.talkNow(this) else askMic.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
    }

    private fun answer() {
        answerAfterMic = true
        if (hasMic()) calls.answer(this) else askMic.launch(Manifest.permission.RECORD_AUDIO)
    }

    private fun hasMic() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun showOverLockScreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    companion object {
        const val ACTION_SHOW = "com.voicemitra.patient.SHOW_CALL"
        const val ACTION_ANSWER = "com.voicemitra.patient.ANSWER"
        const val ACTION_TALK = "com.voicemitra.patient.TALK"

        fun intent(context: Context, action: String, callId: String?): Intent =
            Intent(context, CallActivity::class.java)
                .setAction(action)
                .putExtra("call_id", callId)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
    }
}
