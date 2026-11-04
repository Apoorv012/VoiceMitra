package com.voicemitra.patient

import android.app.Application
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.ProcessLifecycleOwner
import com.voicemitra.patient.call.CallManager
import com.voicemitra.patient.call.CallState
import com.voicemitra.patient.call.Notifications
import com.voicemitra.patient.call.PatientSocket
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import com.voicemitra.patient.data.Api
import com.voicemitra.patient.data.Prefs
import com.voicemitra.patient.data.Settings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.runBlocking

/** The app's few long-lived objects. No DI framework: there are only a handful. */
class App : Application() {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    lateinit var prefs: Prefs private set
    lateinit var settings: StateFlow<Settings> private set
    lateinit var api: Api private set
    lateinit var calls: CallManager private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        prefs = Prefs(this)
        // Read once up front (a few ms, local file) so a ring arriving at a cold start knows the server.
        val initial = runBlocking { prefs.current() }
        settings = prefs.settings.stateIn(scope, SharingStarted.Eagerly, initial)
        api = Api { settings.value.serverUrl }
        Notifications.createChannels(this)
        calls = CallManager(this)
        holdSocket()
    }

    /** The patient socket is open while the app is on screen or a call is on (and the phone is signed in). */
    private fun holdSocket() {
        val socket = PatientSocket(this)
        val lifecycle = ProcessLifecycleOwner.get().lifecycle
        val foreground = MutableStateFlow(lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED))
        lifecycle.addObserver(LifecycleEventObserver { _, _ ->
            foreground.value = lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
        })
        scope.launch {
            combine(settings, calls.state, foreground) { s, call, fg ->
                val busy = call !is CallState.Idle && call !is CallState.Ended
                s.pairing?.patientId?.takeIf { fg || busy }?.let { it to s.serverUrl }
            }.distinctUntilChanged().collect { want ->
                socket.stop()
                if (want != null) socket.start(want.first)
            }
        }
    }

    companion object {
        lateinit var instance: App private set
    }
}
