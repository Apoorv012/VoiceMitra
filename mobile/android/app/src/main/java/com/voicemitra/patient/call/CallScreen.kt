package com.voicemitra.patient.call

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.CallEnd
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.MicOff
import androidx.compose.material.icons.outlined.PhoneInTalk
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.clickable
import com.voicemitra.patient.ui.BtnKind
import com.voicemitra.patient.ui.Eyebrow
import com.voicemitra.patient.ui.LocalStrings
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.Vm
import com.voicemitra.patient.ui.VmButton
import kotlinx.coroutines.delay

/** Ringing gets its own unmistakable screen; connecting / connected / ended share the call sheet. */
@Composable
internal fun CallScreen(
    state: CallState,
    transcript: List<Line>,
    onAnswer: () -> Unit,
    onDecline: () -> Unit,
    onHangUp: () -> Unit,
    onMute: (Boolean) -> Unit,
    onSpeaker: (Boolean) -> Unit,
) {
    if (state is CallState.Ringing) IncomingCall(onAnswer, onDecline)
    else CallSheet(state, transcript, onHangUp, onMute, onSpeaker)
}

// Deep brand green behind the ringing screen in both themes, so it can't be mistaken for anything else.
private val RingBg = Color(0xFF12261A)
private val RingRing = Color(0xFF8FBC72)

/**
 * Like the phone's own incoming-call screen: who is calling, then two big buttons. Answer is the bigger
 * one. The push carries no reason for the call, so the line under the name just says "Calling…".
 */
@Composable
private fun IncomingCall(onAnswer: () -> Unit, onDecline: () -> Unit) {
    val s = LocalStrings.current
    val c = Vm.colors
    Column(
        Modifier.fillMaxSize().background(RingBg).safeDrawingPadding().padding(horizontal = 24.dp, vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.weight(1f))
        // The caller's picture, with two still rings around it (a call is coming in).
        Box(contentAlignment = Alignment.Center) {
            Box(Modifier.size(248.dp).border(2.dp, RingRing.copy(alpha = 0.18f), CircleShape))
            Box(Modifier.size(208.dp).border(3.dp, RingRing.copy(alpha = 0.35f), CircleShape))
            Box(Modifier.size(164.dp).background(RingRing, CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.Mic, null, tint = RingBg, modifier = Modifier.size(80.dp))
            }
        }
        Spacer(Modifier.height(40.dp))
        Text("VoiceMitra", color = Color.White, style = MaterialTheme.typography.displaySmall)
        Spacer(Modifier.height(10.dp))
        Text(s.calling, color = Color.White.copy(alpha = 0.85f), style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Medium),
            textAlign = TextAlign.Center, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Assertive })
        Spacer(Modifier.weight(1.2f))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.Bottom) {
            RoundAction(Icons.Outlined.CallEnd, s.decline, c.crit, Color.White, 92.dp, onDecline)
            RoundAction(Icons.Outlined.Call, s.answer, c.good, Color.White, 120.dp, onAnswer)
        }
        Spacer(Modifier.height(16.dp))
    }
}

/** The call itself: web/src/components/call/CallSheet.tsx. */
@Composable
private fun CallSheet(
    state: CallState,
    transcript: List<Line>,
    onHangUp: () -> Unit,
    onMute: (Boolean) -> Unit,
    onSpeaker: (Boolean) -> Unit,
) {
    val s = LocalStrings.current
    val c = Vm.colors
    Column(Modifier.fillMaxSize().background(c.page).safeDrawingPadding()) {
        Column(
            Modifier.fillMaxWidth().padding(top = 32.dp, start = 20.dp, end = 20.dp, bottom = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Box(Modifier.size(104.dp).background(c.accent, CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.PhoneInTalk, null, tint = Color.White, modifier = Modifier.size(52.dp))
            }
            Text("VoiceMitra", style = MaterialTheme.typography.headlineMedium, color = c.ink)
            Text(
                statusLine(state, s),
                style = MaterialTheme.typography.titleMedium,
                color = if (state is CallState.Ended && state.why != EndReason.Finished) c.critInk else c.ink2,
                textAlign = TextAlign.Center,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
            if (state is CallState.InCall) CallTimer(state.startedAt)
        }

        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (state is CallState.InCall || state is CallState.Connecting) Transcript(transcript, s)
        }

        HorizontalDivider(color = c.line)
        Column(
            Modifier.fillMaxWidth().background(c.surface).padding(horizontal = 20.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            val inCall = state as? CallState.InCall
            if (inCall != null) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                ToggleAction(
                    icon = if (inCall.muted) Icons.Outlined.MicOff else Icons.Outlined.Mic,
                    label = if (inCall.muted) s.unmute else s.mute, on = inCall.muted,
                ) { onMute(!inCall.muted) }
                ToggleAction(
                    icon = Icons.AutoMirrored.Outlined.VolumeUp,
                    label = if (inCall.speaker) s.speaker else s.earpiece, on = inCall.speaker,
                ) { onSpeaker(!inCall.speaker) }
            }
            if (state !is CallState.Ended && state !is CallState.Idle) {
                VmButton(s.hangUp, onHangUp, kind = BtnKind.Danger, icon = Icons.Outlined.CallEnd)
            }
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
    Text("%d:%02d".format(secs / 60, secs % 60), style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
        color = Vm.colors.ink)
}

/** `.bubble`: VoiceMitra on the left on grey, the patient on the right in the dark button colour. */
@Composable
private fun Transcript(lines: List<Line>, s: Strings) {
    val c = Vm.colors
    val list = rememberLazyListState()
    LaunchedEffect(lines.size) { if (lines.isNotEmpty()) list.animateScrollToItem(lines.size - 1) }
    LazyColumn(
        state = list,
        verticalArrangement = Arrangement.spacedBy(10.dp),
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(vertical = 8.dp),
    ) {
        items(lines) { line ->
            Box(Modifier.fillMaxWidth(), contentAlignment = if (line.fromPatient) Alignment.CenterEnd else Alignment.CenterStart) {
                Column(
                    Modifier.widthIn(max = 320.dp)
                        .background(if (line.fromPatient) c.btn else c.surface, RoundedCornerShape(20.dp))
                        .then(if (line.fromPatient) Modifier else Modifier.border(1.dp, c.line, RoundedCornerShape(20.dp)))
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                ) {
                    val fg = if (line.fromPatient) c.onBtn else c.ink
                    Eyebrow(if (line.fromPatient) s.youSaid else s.agentSaid, color = fg.copy(alpha = 0.75f))
                    Text(line.text, style = MaterialTheme.typography.bodyLarge, color = fg)
                }
            }
        }
    }
}

@Composable
private fun RoundAction(icon: ImageVector, label: String, bg: Color, fg: Color, size: Dp, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier.size(size).background(bg, CircleShape)
                .clickable(role = Role.Button, onClick = onClick)
                .semantics { contentDescription = label },
            contentAlignment = Alignment.Center,
        ) { Icon(icon, null, tint = fg, modifier = Modifier.size(size * 0.46f)) }
        Spacer(Modifier.height(12.dp))
        Text(label, color = Color.White, style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
private fun ToggleAction(icon: ImageVector, label: String, on: Boolean, onClick: () -> Unit) {
    val c = Vm.colors
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier.size(76.dp)
                .background(if (on) c.btn else c.sunken, CircleShape)
                .then(if (on) Modifier else Modifier.border(1.dp, c.lineStrong, CircleShape))
                .clickable(role = Role.Switch, onClick = onClick)
                .semantics { contentDescription = label; stateDescription = if (on) "on" else "off"; role = Role.Switch },
            contentAlignment = Alignment.Center,
        ) { Icon(icon, null, tint = if (on) c.onBtn else c.ink, modifier = Modifier.size(34.dp)) }
        Spacer(Modifier.height(8.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = c.ink)
    }
}
