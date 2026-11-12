package com.voicemitra.patient

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Home
import androidx.compose.material.icons.outlined.Medication
import androidx.compose.material.icons.outlined.AccountCircle
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Medication
import androidx.compose.material3.HorizontalDivider
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.repeatOnLifecycle
import com.voicemitra.patient.call.CallActivity
import com.voicemitra.patient.call.CallState
import com.voicemitra.patient.data.ApiException
import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.Pairing
import com.voicemitra.patient.push.PushToken
import com.voicemitra.patient.ui.BrandMark
import com.voicemitra.patient.ui.CodeScreen
import com.voicemitra.patient.ui.HistoryTab
import com.voicemitra.patient.ui.LangSwitch
import com.voicemitra.patient.ui.LocalStrings
import com.voicemitra.patient.ui.LoginScreen
import com.voicemitra.patient.ui.MeTab
import com.voicemitra.patient.ui.MedicinesTab
import com.voicemitra.patient.ui.Setup
import com.voicemitra.patient.ui.SetupScreen
import com.voicemitra.patient.ui.Strings
import com.voicemitra.patient.ui.TalkState
import com.voicemitra.patient.ui.TodayTab
import com.voicemitra.patient.ui.Vm
import com.voicemitra.patient.ui.VoiceMitraTheme
import kotlinx.coroutines.launch

/** Signed out: login (with the server address under Advanced), the code pad, the debug picker. Signed in: the four tabs, plus the setup checklist. */
enum class Screen { Login, Code, Today, Medicines, History, Me, Setup }

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

@Composable
private fun Root() {
    val app = App.instance
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val settings by app.settings.collectAsStateWithLifecycle()
    val callState by app.calls.state.collectAsStateWithLifecycle()
    val pairing = settings.pairing

    var authScreen by rememberSaveable { mutableStateOf(Screen.Login) }
    var screen by rememberSaveable { mutableStateOf(Screen.Today) }
    var setupShown by rememberSaveable { mutableStateOf(false) }

    // How many setup items are still missing: re-checked whenever the app comes back to the front.
    var setupLeft by remember { mutableIntStateOf(0) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(Unit) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            setupLeft = Setup.items().count { !Setup.isDone(context, it) }
        }
    }

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
    BackHandler(enabled = current !in setOf(Screen.Login, Screen.Today)) {
        if (pairing == null) authScreen = Screen.Login else screen = Screen.Today
    }

    val talk = when (callState) {
        CallState.Starting, is CallState.Connecting -> TalkState.Starting
        is CallState.InCall -> TalkState.InCall
        else -> TalkState.Idle
    }

    AppFrame(
        lang = settings.lang,
        onLang = { scope.launch { app.prefs.setLang(it) } },
        tab = if (pairing != null && current != Screen.Setup) current else null,
        onTab = { screen = it },
    ) {
        when (current) {
            Screen.Login -> LoginScreen(
                onUseCode = { authScreen = Screen.Code },
                settings = settings,
            )
            Screen.Code -> CodeScreen(onUseLogin = { authScreen = Screen.Login })
            Screen.Today -> TodayTab(pairing!!.patientId, talk) {
                context.startActivity(CallActivity.intent(context, if (talk == TalkState.InCall) CallActivity.ACTION_SHOW else CallActivity.ACTION_TALK, null))
            }
            Screen.Medicines -> MedicinesTab(pairing!!.patientId)
            Screen.History -> HistoryTab(pairing!!.patientId)
            Screen.Me -> MeTab(settings, setupLeft, onSetup = { screen = Screen.Setup }, onLogOut = {
                val p = pairing ?: return@MeTab
                scope.launch {
                    if (!p.isDebug) try {
                        app.api.unpair(p)
                    } catch (e: Exception) {
                        Log.w("Main", "unpair failed; forgetting locally anyway", e)
                    }
                    app.prefs.clearPairing()
                    authScreen = Screen.Login
                    screen = Screen.Today
                    setupShown = false
                }
            })
            Screen.Setup -> SetupScreen(onDone = { screen = Screen.Today })
        }
    }
}

/**
 * The web patient app's frame: a header (brand mark, name, EN/हि switch) and, when signed in, the
 * four-tab bar at the bottom (`.p-head`, `.tabbar`). Shared with the screenshots.
 */
@Composable
fun AppFrame(
    lang: Lang,
    onLang: (Lang) -> Unit,
    tab: Screen?,
    onTab: (Screen) -> Unit,
    content: @Composable () -> Unit,
) {
    val c = Vm.colors
    Column(Modifier.fillMaxSize().background(c.page)) {
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(start = 20.dp, end = 12.dp, top = 12.dp, bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BrandMark(40.dp)
            Spacer(Modifier.width(12.dp))
            Text("VoiceMitra", style = MaterialTheme.typography.titleLarge, color = c.ink, modifier = Modifier.weight(1f))
            LangSwitch(lang, onLang)
        }
        Box(Modifier.weight(1f).fillMaxWidth().then(if (tab == null) Modifier.windowInsetsPadding(WindowInsets.ime) else Modifier)) {
            content()
        }
        if (tab != null) TabBar(tab, onTab)
        else Spacer(Modifier.navigationBarsPadding())
    }
}

/** Bottom navigation (Material 3 style, as on the iPhone app): the selected tab is filled and green. */
@Composable
private fun TabBar(current: Screen, onTab: (Screen) -> Unit) {
    val s = LocalStrings.current
    val c = Vm.colors
    data class Tab(val screen: Screen, val on: ImageVector, val off: ImageVector, val label: String)
    val tabs = listOf(
        Tab(Screen.Today, Icons.Filled.Home, Icons.Outlined.Home, s.tabToday),
        Tab(Screen.Medicines, Icons.Filled.Medication, Icons.Outlined.Medication, s.tabMedicines),
        Tab(Screen.History, Icons.Filled.History, Icons.Outlined.History, s.tabHistory),
        Tab(Screen.Me, Icons.Filled.AccountCircle, Icons.Outlined.AccountCircle, s.tabMe),
    )
    Column(Modifier.fillMaxWidth().background(c.surface)) {
        HorizontalDivider(color = c.line)
        Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 8.dp, vertical = 6.dp)) {
            tabs.forEach { t ->
                val on = t.screen == current
                Column(
                    Modifier.weight(1f).heightIn(min = 68.dp)
                        .clickable(role = Role.Tab) { onTab(t.screen) }
                        .semantics { selected = on }
                        .padding(vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Box(
                        Modifier.background(if (on) c.accentSoft else androidx.compose.ui.graphics.Color.Transparent, CircleShape)
                            .padding(horizontal = 20.dp, vertical = 4.dp),
                    ) { Icon(if (on) t.on else t.off, null, tint = if (on) c.accent else c.muted, modifier = Modifier.size(30.dp)) }
                    Spacer(Modifier.height(4.dp))
                    Text(t.label, style = MaterialTheme.typography.labelMedium, color = if (on) c.accent else c.muted, maxLines = 1)
                }
            }
        }
    }
}
