package com.voicemitra.patient

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.voicemitra.patient.call.CallActivity
import com.voicemitra.patient.call.CallState
import com.voicemitra.patient.data.ApiException
import com.voicemitra.patient.data.Pairing
import com.voicemitra.patient.push.PushToken
import com.voicemitra.patient.ui.CodeScreen
import com.voicemitra.patient.ui.HomeScreen
import com.voicemitra.patient.ui.LocalStrings
import com.voicemitra.patient.ui.LoginScreen
import com.voicemitra.patient.ui.PickPatientScreen
import com.voicemitra.patient.ui.SettingsScreen
import com.voicemitra.patient.ui.Setup
import com.voicemitra.patient.ui.SetupScreen
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.VoiceMitraTheme
import kotlinx.coroutines.launch

private enum class Screen { Login, Code, Pick, Home, Setup, Settings }

/** A debug-picker "pairing" (no device on the server): nothing to verify or unpair. */
val Pairing.isDebug get() = deviceId == "debug"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val app = App.instance
            val settings by app.settings.collectAsStateWithLifecycle()
            VoiceMitraTheme(Strings.of(settings.lang)) { Root() }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Root() {
    val app = App.instance
    val context = LocalContext.current
    val s = LocalStrings.current
    val scope = rememberCoroutineScope()
    val settings by app.settings.collectAsStateWithLifecycle()
    val callState by app.calls.state.collectAsStateWithLifecycle()
    val pairing = settings.pairing

    var authScreen by rememberSaveable { mutableStateOf(Screen.Login) }
    var screen by rememberSaveable { mutableStateOf(Screen.Home) }
    var setupShown by rememberSaveable { mutableStateOf(false) }

    // Signed in: check the phone is still paired, keep the push token current, and show the setup
    // checklist once per launch if anything is missing.
    LaunchedEffect(pairing?.deviceId) {
        val p = pairing ?: return@LaunchedEffect
        if (!setupShown && !Setup.allDone(context)) screen = Screen.Setup
        setupShown = true
        if (p.isDebug) return@LaunchedEffect
        try {
            app.api.device(p)
            PushToken.sendIfChanged(app, null)
        } catch (e: ApiException) {
            if (e.code == 401 || e.code == 404) app.prefs.clearPairing()  // unpaired elsewhere: sign in again
        } catch (e: Exception) {
            Log.i("Main", "couldn't check the pairing (offline?)", e)
        }
    }

    val current = if (pairing == null) authScreen else screen
    val showSettingsButton = current != Screen.Settings && current != Screen.Setup

    BackHandler(enabled = current == Screen.Settings || current == Screen.Code || current == Screen.Pick || current == Screen.Setup) {
        if (pairing == null) authScreen = Screen.Login else screen = Screen.Home
    }

    Surface(color = MaterialTheme.colorScheme.background, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding()) {
            TopAppBar(
                title = { Text("VoiceMitra", style = MaterialTheme.typography.titleLarge) },
                actions = {
                    if (showSettingsButton) IconButton(onClick = {
                        if (pairing == null) authScreen = Screen.Settings else screen = Screen.Settings
                    }) { Icon(Icons.Filled.Settings, contentDescription = s.settings) }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
            Box(Modifier.fillMaxSize()) {
                when (current) {
                    Screen.Login -> LoginScreen(
                        onUseCode = { authScreen = Screen.Code },
                        onPickPatient = if (BuildConfig.DEBUG) ({ authScreen = Screen.Pick }) else null,
                    )
                    Screen.Code -> CodeScreen(onUseLogin = { authScreen = Screen.Login })
                    Screen.Pick -> PickPatientScreen(onBack = { authScreen = Screen.Login })
                    Screen.Home -> HomeScreen(
                        patientId = pairing!!.patientId,
                        lang = settings.lang,
                        talkBusy = callState is CallState.Starting || callState is CallState.Connecting,
                        onTalk = {
                            context.startActivity(CallActivity.intent(context, CallActivity.ACTION_TALK, null))
                        },
                    )
                    Screen.Setup -> SetupScreen(onDone = { screen = Screen.Home })
                    Screen.Settings -> SettingsScreen(
                        settings = settings,
                        onBack = { if (pairing == null) authScreen = Screen.Login else screen = Screen.Home },
                        onSetup = { screen = Screen.Setup },
                        onLogOut = {
                            val p = pairing ?: return@SettingsScreen
                            scope.launch {
                                if (!p.isDebug) try {
                                    app.api.unpair(p)
                                } catch (e: Exception) {
                                    Log.w("Main", "unpair failed; forgetting locally anyway", e)
                                }
                                app.prefs.clearPairing()
                                authScreen = Screen.Login
                                screen = Screen.Home
                                setupShown = false
                            }
                        },
                    )
                }
            }
        }
    }
}
