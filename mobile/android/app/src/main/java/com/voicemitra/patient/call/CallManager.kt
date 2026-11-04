package com.voicemitra.patient.call

import android.content.Context
import android.util.Log
import com.twilio.audioswitch.AudioDevice
import com.voicemitra.patient.App
import com.voicemitra.patient.data.ApiException
import com.voicemitra.patient.data.VoiceJoin
import io.livekit.android.AudioOptions
import io.livekit.android.LiveKit
import io.livekit.android.LiveKitOverrides
import io.livekit.android.audio.AudioSwitchHandler
import io.livekit.android.events.DisconnectReason
import io.livekit.android.events.RoomEvent
import io.livekit.android.room.Room
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Where the one call this phone can be in has got to. */
sealed interface CallState {
    data object Idle : CallState
    data class Ringing(val callId: String) : CallState
    /** Talk now pressed: asking the backend to start a call. */
    data object Starting : CallState
    data class Connecting(val callId: String?) : CallState
    data class InCall(
        val callId: String,
        val startedAt: Long,
        val muted: Boolean = false,
        val speaker: Boolean = true,
        val reconnecting: Boolean = false,
        val agentJoined: Boolean = false,
    ) : CallState
    data class Ended(val why: EndReason) : CallState
}

enum class EndReason { Finished, Declined, Missed, AlreadyOver, Failed, MicDenied }

data class Line(val fromPatient: Boolean, val text: String)

/**
 * The call engine: rings (from an FCM push or the patient socket -- one code path), answers by joining
 * the LiveKit room the backend made (mobile/API.md "Calls"), and hangs up. Single instance in [App].
 *
 * Audio defaults to the loudspeaker (elderly users hold the phone in front of them); a Bluetooth or
 * wired headset wins when one is plugged in. If the network drops, LiveKit reconnects by itself; if
 * that fails, the room is joined again for as long as the backend still has the call.
 */
class CallManager(private val app: App) {
    private val _state = MutableStateFlow<CallState>(CallState.Idle)
    val state: StateFlow<CallState> = _state.asStateFlow()

    private val _transcript = MutableStateFlow<List<Line>>(emptyList())
    val transcript: StateFlow<List<Line>> = _transcript.asStateFlow()

    private var room: Room? = null
    private var audio: AudioSwitchHandler? = null
    private var ringTimeout: Job? = null
    private var callJob: Job? = null
    private var endedJob: Job? = null
    private val declined = ArrayDeque<String>()  // call ids not to ring for again (e.g. from the socket snapshot)
    private var leaving = false

    private val scope get() = app.scope

    // --- ringing ---------------------------------------------------------------------------------

    /** A call started for this patient (push `ring`, or the socket's `voice_call` / snapshot). */
    fun onRing(callId: String) {
        val s = _state.value
        if (callId in declined) return
        if (s is CallState.Ringing && s.callId == callId) return
        if (s !is CallState.Idle && s !is CallState.Ended) return  // already busy with a call
        if (app.settings.value.pairing == null) return
        endedJob?.cancel()
        _state.value = CallState.Ringing(callId)
        Notifications.showIncoming(app, callId)
        ringTimeout?.cancel()
        ringTimeout = scope.launch {
            delay(Notifications.RING_MS)
            if ((_state.value as? CallState.Ringing)?.callId == callId) {
                Notifications.cancelIncoming(app)
                remember(callId)
                finish(EndReason.Missed)
            }
        }
    }

    /** The backend says the call is over (push `call_ended`, socket `voice_call_ended`). */
    fun onRemoteEnded(callId: String?) {
        when (val s = _state.value) {
            is CallState.Ringing -> if (callId == null || s.callId == callId) {
                ringTimeout?.cancel()
                Notifications.cancelIncoming(app)
                remember(s.callId)
                finish(EndReason.Missed)
            }
            is CallState.InCall -> if (callId == null || s.callId == callId) leave(EndReason.Finished, tellServer = false)
            is CallState.Connecting -> if (callId != null && s.callId == callId) leave(EndReason.Finished, tellServer = false)
            else -> Unit
        }
    }

    fun decline() {
        val s = _state.value as? CallState.Ringing ?: return
        ringTimeout?.cancel()
        Notifications.cancelIncoming(app)
        remember(s.callId)
        finish(EndReason.Declined)
        endOnServer()
    }

    // --- joining ---------------------------------------------------------------------------------

    /** Answer the ringing call. Call from an activity (a microphone service can't start from the background). */
    fun answer(context: Context) {
        val s = _state.value as? CallState.Ringing ?: return
        ringTimeout?.cancel()
        Notifications.cancelIncoming(app)
        _state.value = CallState.Connecting(s.callId)
        CallService.start(context)
        callJob = scope.launch { joinCurrent(expectCallId = s.callId) }
    }

    /** "Talk to VoiceMitra": start a call and join it. */
    fun talkNow(context: Context) {
        val s = _state.value
        if (s !is CallState.Idle && s !is CallState.Ended) return
        val pairing = app.settings.value.pairing ?: return
        endedJob?.cancel()
        _transcript.value = emptyList()
        _state.value = CallState.Starting
        CallService.start(context)
        callJob = scope.launch {
            try {
                app.api.startVoiceCall(pairing.patientId, pairing.deviceToken)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.w(TAG, "could not start a call", e)
                finish(EndReason.Failed)
                return@launch
            }
            _state.value = CallState.Connecting(null)
            joinCurrent(expectCallId = null)
        }
    }

    private suspend fun joinCurrent(expectCallId: String?) {
        val patientId = app.settings.value.pairing?.patientId ?: return finish(EndReason.Failed)
        val join: VoiceJoin? = try {
            app.api.voiceCall(patientId)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "join info failed", e)
            return finish(EndReason.Failed)
        }
        if (join == null || (expectCallId != null && join.callId != expectCallId)) {
            return finish(EndReason.AlreadyOver)
        }
        if (expectCallId != null) _transcript.value = emptyList()
        connect(join, attempt = 0)
    }

    private suspend fun connect(join: VoiceJoin, attempt: Int) {
        leaving = false
        val handler = AudioSwitchHandler(app).apply {
            // Loudspeaker unless a headset is connected.
            preferredDeviceList = listOf(
                AudioDevice.BluetoothHeadset::class.java,
                AudioDevice.WiredHeadset::class.java,
                AudioDevice.Speakerphone::class.java,
                AudioDevice.Earpiece::class.java,
            )
        }
        val r = LiveKit.create(app, overrides = LiveKitOverrides(audioOptions = AudioOptions(audioHandler = handler)))
        room = r
        audio = handler
        val events = scope.launch { watch(r, join) }
        try {
            r.connect(join.url, join.token)
            r.localParticipant.setMicrophoneEnabled(true)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w(TAG, "LiveKit connect failed (attempt $attempt)", e)
            events.cancel()
            release()
            if (attempt < MAX_REJOINS && stillOn(join.callId)) {
                delay(REJOIN_DELAY_MS)
                return connect(join, attempt + 1)
            }
            return finish(EndReason.Failed)
        }
        val prev = _state.value as? CallState.InCall
        _state.value = CallState.InCall(
            callId = join.callId,
            startedAt = prev?.startedAt ?: System.currentTimeMillis(),
            muted = false,
            speaker = prev?.speaker ?: true,
            agentJoined = r.remoteParticipants.isNotEmpty(),
        )
        if (prev != null && !prev.speaker) setSpeaker(false)
    }

    private suspend fun watch(r: Room, join: VoiceJoin) {
        r.events.events.collect { e ->
            val s = _state.value as? CallState.InCall
            when (e) {
                is RoomEvent.Reconnecting -> if (s != null) _state.value = s.copy(reconnecting = true)
                is RoomEvent.Reconnected -> if (s != null) _state.value = s.copy(reconnecting = false)
                is RoomEvent.ParticipantConnected -> if (s != null) _state.value = s.copy(agentJoined = true)
                is RoomEvent.ParticipantDisconnected ->
                    // The agent left: the backend has finished the call.
                    if (s != null && s.agentJoined && r.remoteParticipants.isEmpty()) leave(EndReason.Finished, tellServer = false)
                is RoomEvent.Disconnected -> if (!leaving) onDropped(e.reason, join)
                else -> Unit
            }
        }
    }

    private fun onDropped(reason: DisconnectReason?, join: VoiceJoin) {
        Log.i(TAG, "room disconnected: $reason")
        release()
        // Pushed out by another `patient` (e.g. the web page), or the room closed: the call isn't ours any more.
        if (reason == DisconnectReason.DUPLICATE_IDENTITY || reason == DisconnectReason.ROOM_DELETED ||
            reason == DisconnectReason.PARTICIPANT_REMOVED
        ) return finish(EndReason.Finished)
        // Lost the network for longer than LiveKit's own retries: join again while the call still exists.
        (_state.value as? CallState.InCall)?.let { _state.value = it.copy(reconnecting = true) }
        callJob = scope.launch {
            if (stillOn(join.callId)) connect(join, attempt = 1) else finish(EndReason.Finished)
        }
    }

    private suspend fun stillOn(callId: String): Boolean {
        val patientId = app.settings.value.pairing?.patientId ?: return false
        repeat(3) {
            try {
                return app.api.voiceCall(patientId)?.callId == callId
            } catch (e: ApiException) {
                return false
            } catch (_: Exception) {
                delay(REJOIN_DELAY_MS)  // no network yet
            }
        }
        return false
    }

    // --- during the call -------------------------------------------------------------------------

    fun setMuted(muted: Boolean) {
        val s = _state.value as? CallState.InCall ?: return
        val r = room ?: return
        _state.value = s.copy(muted = muted)
        scope.launch {
            try {
                r.localParticipant.setMicrophoneEnabled(!muted)
            } catch (e: Exception) {
                Log.w(TAG, "mute failed", e)
            }
        }
    }

    fun setSpeaker(on: Boolean) {
        val handler = audio ?: return
        val want = handler.availableAudioDevices.firstOrNull {
            if (on) it is AudioDevice.Speakerphone else it !is AudioDevice.Speakerphone
        } ?: return
        handler.selectDevice(want)
        (_state.value as? CallState.InCall)?.let { _state.value = it.copy(speaker = on) }
    }

    fun hangUp() {
        when (_state.value) {
            is CallState.Ringing -> decline()
            is CallState.InCall, is CallState.Connecting, CallState.Starting -> leave(EndReason.Finished, tellServer = true)
            else -> Unit
        }
    }

    /** No microphone permission: the call can't go ahead (end it, so the caregiver isn't kept waiting). */
    fun onMicDenied() {
        (_state.value as? CallState.Ringing)?.let {
            ringTimeout?.cancel()
            Notifications.cancelIncoming(app)
            remember(it.callId)
        }
        leave(EndReason.MicDenied, tellServer = true)
    }

    /** A transcript line from the patient socket (`log_entry`). */
    fun onLogEntry(callId: String?, type: String, text: String?) {
        if (text.isNullOrBlank()) return
        val s = _state.value
        val current = (s as? CallState.InCall)?.callId ?: (s as? CallState.Connecting)?.callId
        if (callId != null && current != null && callId != current) return
        when (type) {
            "patient_said" -> _transcript.value = _transcript.value + Line(true, text)
            "agent_said" -> _transcript.value = _transcript.value + Line(false, text)
        }
    }

    // --- ending ----------------------------------------------------------------------------------

    private fun leave(why: EndReason, tellServer: Boolean) {
        callJob?.cancel()
        leaving = true
        release()
        if (tellServer) endOnServer()
        finish(why)
    }

    private fun endOnServer() {
        val patientId = app.settings.value.pairing?.patientId ?: return
        scope.launch {
            try {
                app.api.endCall(patientId)
            } catch (e: Exception) {
                Log.w(TAG, "call/end failed", e)
            }
        }
    }

    private fun release() {
        room?.let {
            try {
                it.disconnect()
                it.release()
            } catch (e: Exception) {
                Log.w(TAG, "room release failed", e)
            }
        }
        room = null
        audio = null
    }

    /** Show why the call ended for a moment, then go back to idle. */
    private fun finish(why: EndReason) {
        CallService.stop(app)
        _state.value = CallState.Ended(why)
        endedJob?.cancel()
        endedJob = scope.launch {
            delay(ENDED_SHOWN_MS)
            if (_state.value is CallState.Ended) _state.value = CallState.Idle
        }
    }

    private fun remember(callId: String) {
        declined.addLast(callId)
        while (declined.size > 20) declined.removeFirst()
    }

    private companion object {
        const val TAG = "CallManager"
        const val MAX_REJOINS = 5
        const val REJOIN_DELAY_MS = 3_000L
        const val ENDED_SHOWN_MS = 2_500L
    }
}
