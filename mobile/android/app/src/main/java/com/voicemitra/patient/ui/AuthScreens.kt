package com.voicemitra.patient.ui

import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Backspace
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.Mic
import androidx.compose.material.icons.outlined.Pin
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.voicemitra.patient.App
import com.voicemitra.patient.data.Pairing
import com.voicemitra.patient.data.PairResponse
import com.voicemitra.patient.data.Person
import com.voicemitra.patient.push.PushToken
import kotlinx.coroutines.launch

fun deviceName(): String {
    val maker = Build.MANUFACTURER.replaceFirstChar { it.uppercase() }
    return if (Build.MODEL.startsWith(maker, ignoreCase = true)) Build.MODEL else "$maker ${Build.MODEL}"
}

/** Store what login/pairing returned. The FCM token went with the request, so it's already on the server. */
suspend fun App.signedIn(res: PairResponse, pushToken: String?) {
    prefs.savePairing(Pairing(res.deviceId, res.deviceToken, res.patientId, res.patientName), pushToken)
}

/** The web header's brand mark: a mic in a rounded green square. */
@Composable
fun BrandMark(size: Dp = 40.dp) {
    Box(Modifier.size(size).background(Vm.colors.accent, RoundedCornerShape(size * 0.32f)), contentAlignment = Alignment.Center) {
        Icon(Icons.Outlined.Mic, null, tint = Color.White, modifier = Modifier.size(size * 0.55f))
    }
}

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = Vm.colors.surface, unfocusedContainerColor = Vm.colors.surface,
    focusedBorderColor = Vm.colors.accent, unfocusedBorderColor = Vm.colors.lineStrong,
    focusedLabelColor = Vm.colors.accent, unfocusedLabelColor = Vm.colors.muted,
    focusedTextColor = Vm.colors.ink, unfocusedTextColor = Vm.colors.ink, cursorColor = Vm.colors.accent,
)

@Composable
private fun AuthHeading(title: String, sub: String, icon: ImageVector? = null) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth().padding(top = 8.dp)) {
        if (icon == null) BrandMark(64.dp)
        else Avatar(null, icon, size = 64.dp, bg = Vm.colors.accentSoft, fg = Vm.colors.accent)
        Spacer(Modifier.height(4.dp))
        H1(title)
        Text(sub, style = MaterialTheme.typography.bodyLarge, color = Vm.colors.ink2)
    }
}

/** The main way in: the username + password the family set on the web app (mobile/API.md "Identity: login"). */
@Composable
fun LoginScreen(onUseCode: () -> Unit, onPickPatient: (() -> Unit)?, settings: com.voicemitra.patient.data.Settings? = null) {
    val s = LocalStrings.current
    val app by lazy { App.instance }  // looked up on use, so the screen also renders without the app (screenshots)
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    var username by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var show by rememberSaveable { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var blank by remember { mutableStateOf(false) }

    fun submit() {
        if (busy) return
        if (username.isBlank() || password.isEmpty()) {
            blank = true
            return
        }
        focus.clearFocus()
        busy = true
        error = null
        scope.launch {
            try {
                val token = PushToken.get(app)
                app.signedIn(app.api.login(username, password, token, deviceName()), token)
            } catch (e: Exception) {
                error = e
            } finally {
                busy = false
            }
        }
    }

    TabPage {
        AuthHeading(s.loginTitle, s.loginSub)
        OutlinedTextField(
            value = username,
            onValueChange = { username = it; error = null; blank = false },
            label = { Text(s.username) },
            singleLine = true,
            shape = RoundedCornerShape(16.dp),
            colors = fieldColors(),
            textStyle = MaterialTheme.typography.titleLarge,
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false,
                keyboardType = KeyboardType.Ascii, imeAction = ImeAction.Next,
            ),
            modifier = Modifier.fillMaxWidth().heightIn(min = 68.dp),
        )
        OutlinedTextField(
            value = password,
            onValueChange = { password = it; error = null; blank = false },
            label = { Text(s.password) },
            singleLine = true,
            shape = RoundedCornerShape(16.dp),
            colors = fieldColors(),
            textStyle = MaterialTheme.typography.titleLarge,
            visualTransformation = if (show) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done, autoCorrectEnabled = false),
            keyboardActions = KeyboardActions(onDone = { submit() }),
            trailingIcon = {
                IconButton(onClick = { show = !show }, modifier = Modifier.size(56.dp)) {
                    Icon(if (show) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                        contentDescription = if (show) s.hidePassword else s.showPassword, tint = Vm.colors.ink2)
                }
            },
            modifier = Modifier.fillMaxWidth().heightIn(min = 68.dp),
        )
        val err = error
        when {
            blank -> ErrorState(s.fillBoth, null)
            err != null -> ErrorState(s.explain(err, on401 = s.wrongLogin), null, offline = err.isOffline())
        }
        VmButton(if (busy) s.signingIn else s.signIn, ::submit, busy = busy)
        VmButton(s.useCode, onUseCode, kind = BtnKind.Secondary, icon = Icons.Outlined.Pin, xl = false)
        if (onPickPatient != null) VmButton(s.pickPatient, onPickPatient, kind = BtnKind.Ghost, xl = false)
        // The server address, folded away (the language switch is in the header).
        if (settings != null) Advanced(settings) { url -> scope.launch { app.prefs.setServerUrl(url) } }
    }
}

/** The fallback: the 6-digit code from the web app's "Connect a phone" card, on a big number pad. */
@Composable
fun CodeScreen(onUseLogin: () -> Unit, initial: String = "") {
    val s = LocalStrings.current
    val app by lazy { App.instance }
    val scope = rememberCoroutineScope()
    var code by rememberSaveable { mutableStateOf(initial) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<Throwable?>(null) }

    fun submit() {
        if (busy || code.length != 6) return
        busy = true
        error = null
        scope.launch {
            try {
                val token = PushToken.get(app)
                app.signedIn(app.api.pair(code, token, deviceName()), token)
            } catch (e: Exception) {
                error = e
                code = ""
            } finally {
                busy = false
            }
        }
    }
    // Six digits typed: connect straight away. (`initial` is only for screenshots.)
    LaunchedEffect(code) { if (code.length == 6 && initial.isEmpty()) submit() }

    TabPage {
        AuthHeading(s.codeTitle, s.codeSub, Icons.Outlined.Pin)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            repeat(6) { i ->
                val active = i == code.length
                Box(
                    Modifier.weight(1f).aspectRatio(0.78f)
                        .background(Vm.colors.surface, RoundedCornerShape(14.dp))
                        .border(if (active) 2.5.dp else 1.5.dp, if (active) Vm.colors.accent else Vm.colors.lineStrong, RoundedCornerShape(14.dp))
                        .semantics { contentDescription = s.fill(s.codeDigit, "n" to (i + 1)) + ": " + (code.getOrNull(i) ?: "") },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(code.getOrNull(i)?.toString() ?: "", color = Vm.colors.ink,
                        style = TextStyle(fontFamily = Jakarta, fontSize = 34.sp, fontWeight = FontWeight.Bold))
                }
            }
        }
        error?.let { ErrorState(s.explain(it, on400 = s.wrongCode), null, offline = it.isOffline()) }
        NumberPad(
            onDigit = { if (code.length < 6 && !busy) { code += it; error = null } },
            onDelete = { if (!busy) code = code.dropLast(1) },
            deleteLabel = s.deleteDigit,
        )
        VmButton(s.connect, ::submit, enabled = code.length == 6, busy = busy)
        VmButton(s.useLogin, onUseLogin, kind = BtnKind.Secondary, xl = false)
    }
}

@Composable
private fun NumberPad(onDigit: (Char) -> Unit, onDelete: () -> Unit, deleteLabel: String) {
    val c = Vm.colors
    val rows = listOf("123", "456", "789", " 0<")
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { key ->
                    val mod = Modifier.weight(1f).height(72.dp)
                    when (key) {
                        ' ' -> Spacer(mod)
                        '<' -> Box(
                            mod.clickable(role = Role.Button, onClick = onDelete).semantics { contentDescription = deleteLabel },
                            contentAlignment = Alignment.Center,
                        ) { Icon(Icons.AutoMirrored.Outlined.Backspace, null, tint = c.ink2, modifier = Modifier.size(32.dp)) }
                        else -> Box(
                            mod.background(c.surface, RoundedCornerShape(20.dp)).border(1.dp, c.line, RoundedCornerShape(20.dp))
                                .clickable(role = Role.Button) { onDigit(key) },
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(key.toString(), color = c.ink, style = TextStyle(fontFamily = Jakarta, fontSize = 32.sp, fontWeight = FontWeight.SemiBold))
                        }
                    }
                }
            }
        }
    }
}

/**
 * Debug builds only: pick a patient from `/api/app/people` without signing in. Nothing is registered with
 * the backend, so push rings don't reach this phone (the socket still rings it while the app is open).
 */
@Composable
fun PickPatientScreen(onBack: () -> Unit) {
    val s = LocalStrings.current
    val app by lazy { App.instance }
    val scope = rememberCoroutineScope()
    var people by remember { mutableStateOf<List<Person>?>(null) }
    var error by remember { mutableStateOf<Throwable?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    LaunchedEffect(attempt) {
        error = null
        try {
            people = app.api.people().patients
        } catch (e: Exception) {
            error = e
        }
    }
    TabPage {
        H1(s.pickPatient)
        Muted(s.pickPatientSub, small = false)
        error?.let { ErrorState(s.explain(it), { attempt++ }, it.isOffline()) }
        val list = people
        if (list == null && error == null) LoadingState()
        if (list != null && list.isEmpty()) EmptyState(Icons.Outlined.Mic, s.nobody)
        if (!list.isNullOrEmpty()) VmCard(padding = 0.dp, spacing = 0.dp) {
            list.forEach { p ->
                Row(
                    Modifier.fillMaxWidth()
                        .clickable { scope.launch { app.prefs.savePairing(Pairing("debug", "debug", p.id, p.name), null) } }
                        .heightIn(min = 64.dp).padding(horizontal = 20.dp, vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Avatar(initials(p.name), size = 44.dp)
                    Spacer(Modifier.width(14.dp))
                    Text(p.name, style = MaterialTheme.typography.titleMedium, color = Vm.colors.ink, modifier = Modifier.weight(1f))
                    Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, tint = Vm.colors.muted)
                }
            }
        }
        VmButton(s.back, onBack, kind = BtnKind.Ghost, xl = false)
    }
}
