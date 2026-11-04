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
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.PhoneInTalk
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.voicemitra.patient.App
import com.voicemitra.patient.ui.LocalStrings
import com.voicemitra.patient.ui.StatusColors
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.VoiceMitraTheme
import kotlinx.coroutines.delay

/**
 * The call screen, for ringing and for the call itself. Opens over the lock screen and turns the screen
 * on (the ring notification's full-screen intent), like the phone's own incoming-call screen.
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

@Composable
private fun CallScreen(
    state: CallState,
    transcript: List<Line>,
    onAnswer: () -> Unit,
    onDecline: () -> Unit,
    onHangUp: () -> Unit,
    onMute: (Boolean) -> Unit,
    onSpeaker: (Boolean) -> Unit,
) {
    val s = LocalStrings.current
    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(
            Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(32.dp))
            Box(
                Modifier.size(120.dp).background(MaterialTheme.colorScheme.secondary, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Filled.PhoneInTalk, null, tint = Color.White, modifier = Modifier.size(64.dp))
            }
            Spacer(Modifier.height(20.dp))
            Text("VoiceMitra", style = MaterialTheme.typography.displaySmall)
            Spacer(Modifier.height(8.dp))
            Text(
                statusLine(state, s),
                style = MaterialTheme.typography.titleMedium,
                textAlign = TextAlign.Center,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
            if (state is CallState.InCall) CallTimer(state.startedAt)

            Box(Modifier.weight(1f).fillMaxWidth().padding(vertical = 16.dp)) {
                if (state is CallState.InCall || state is CallState.Connecting) Transcript(transcript, s)
            }

            when (state) {
                is CallState.Ringing -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                    BigRoundButton(Icons.Filled.CallEnd, s.decline, StatusColors.hangUp, onDecline)
                    BigRoundButton(Icons.Filled.Call, s.answer, StatusColors.answer, onAnswer)
                }
                is CallState.InCall, is CallState.Connecting, CallState.Starting -> {
                    val inCall = state as? CallState.InCall
                    if (inCall != null) {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            ToggleButton(
                                icon = if (inCall.muted) Icons.Filled.MicOff else Icons.Filled.Mic,
                                label = if (inCall.muted) s.unmute else s.mute,
                                on = inCall.muted,
                                onClick = { onMute(!inCall.muted) },
                            )
                            ToggleButton(
                                icon = Icons.AutoMirrored.Filled.VolumeUp,
                                label = if (inCall.speaker) s.speaker else s.earpiece,
                                on = inCall.speaker,
                                onClick = { onSpeaker(!inCall.speaker) },
                            )
                        }
                        Spacer(Modifier.height(24.dp))
                    }
                    BigRoundButton(Icons.Filled.CallEnd, s.hangUp, StatusColors.hangUp, onHangUp)
                }
                else -> Unit
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}

private fun statusLine(state: CallState, s: Strings): String = when (state) {
    is CallState.Ringing -> s.incomingTitle
    CallState.Starting, is CallState.Connecting -> s.callConnecting
    is CallState.InCall -> if (state.reconnecting) s.callReconnecting else s.callLive
    is CallState.Ended -> when (state.why) {
        EndReason.Failed -> s.callFailed
        EndReason.AlreadyOver -> s.callOver
        EndReason.MicDenied -> s.micNeeded
        else -> s.callEnded
    }
    CallState.Idle -> s.callEnded
}

@Composable
private fun CallTimer(startedAt: Long) {
    val now = remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(startedAt) {
        while (true) {
            now.longValue = System.currentTimeMillis()
            delay(1000)
        }
    }
    val secs = ((now.longValue - startedAt) / 1000).coerceAtLeast(0)
    Text("%d:%02d".format(secs / 60, secs % 60), style = MaterialTheme.typography.titleLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun Transcript(lines: List<Line>, s: Strings) {
    val list = rememberLazyListState()
    LaunchedEffect(lines.size) { if (lines.isNotEmpty()) list.animateScrollToItem(lines.size - 1) }
    LazyColumn(state = list, verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxSize()) {
        items(lines) { line ->
            val bg = if (line.fromPatient) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface
            Column(Modifier.fillMaxWidth().background(bg, RoundedCornerShape(16.dp)).padding(12.dp)) {
                Text(if (line.fromPatient) s.youSaid else s.agentSaid, style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(line.text, style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}

@Composable
private fun BigRoundButton(icon: ImageVector, label: String, color: Color, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        FilledIconButton(
            onClick = onClick,
            modifier = Modifier.size(88.dp),
            colors = IconButtonDefaults.filledIconButtonColors(containerColor = color, contentColor = Color.White),
        ) {
            Icon(icon, contentDescription = label, modifier = Modifier.size(44.dp))
        }
        Spacer(Modifier.height(8.dp))
        Text(label, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
private fun ToggleButton(icon: ImageVector, label: String, on: Boolean, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        FilledIconButton(
            onClick = onClick,
            modifier = Modifier.size(72.dp),
            colors = IconButtonDefaults.filledIconButtonColors(
                containerColor = if (on) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
                contentColor = if (on) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
            ),
        ) {
            Icon(icon, contentDescription = label, modifier = Modifier.size(34.dp))
        }
        Spacer(Modifier.height(6.dp))
        Text(label, style = MaterialTheme.typography.labelMedium)
    }
}
