package com.voicemitra.patient.ui

import android.os.Build
import androidx.compose.foundation.border
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Backspace
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
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

@Composable
private fun AuthFrame(title: String, sub: String, content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })
        Text(sub, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        content()
    }
}

/** The main way in: the username + password the family set on the web app (mobile/API.md "Identity: login"). */
@Composable
fun LoginScreen(onUseCode: () -> Unit, onPickPatient: (() -> Unit)?) {
    val s = LocalStrings.current
    val app = App.instance
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    var username by rememberSaveable { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var show by rememberSaveable { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun submit() {
        if (busy) return
        if (username.isBlank() || password.isEmpty()) {
            error = s.fillBoth
            return
        }
        focus.clearFocus()
        busy = true
        error = null
        scope.launch {
            try {
                val token = PushToken.get(app)
                val res = app.api.login(username, password, token, deviceName())
                app.signedIn(res, token)
            } catch (e: Exception) {
                error = s.explain(e, on401 = s.wrongLogin)
            } finally {
                busy = false
            }
        }
    }

    AuthFrame(s.loginTitle, s.loginSub) {
        OutlinedTextField(
            value = username,
            onValueChange = { username = it; error = null },
            label = { Text(s.username) },
            singleLine = true,
            textStyle = MaterialTheme.typography.titleLarge,
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.None, autoCorrectEnabled = false,
                keyboardType = KeyboardType.Ascii, imeAction = ImeAction.Next,
            ),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = password,
            onValueChange = { password = it; error = null },
            label = { Text(s.password) },
            singleLine = true,
            textStyle = MaterialTheme.typography.titleLarge,
            visualTransformation = if (show) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done,
                autoCorrectEnabled = false),
            keyboardActions = KeyboardActions(onDone = { submit() }),
            trailingIcon = {
                IconButton(onClick = { show = !show }) {
                    Icon(if (show) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                        contentDescription = if (show) s.hidePassword else s.showPassword)
                }
            },
            modifier = Modifier.fillMaxWidth(),
        )
        TextButton(onClick = { show = !show }, modifier = Modifier.heightIn(min = 48.dp)) {
            Text(if (show) s.hidePassword else s.showPassword, style = MaterialTheme.typography.labelMedium)
        }
        error?.let { ErrorBox(it) }
        BigButton(if (busy) s.signingIn else s.signIn, ::submit, busy = busy)
        Spacer(Modifier.height(8.dp))
        SecondButton(s.useCode, onUseCode)
        if (onPickPatient != null) TextButton(onClick = onPickPatient, modifier = Modifier.fillMaxWidth()) {
            Text(s.pickPatient, style = MaterialTheme.typography.labelMedium)
        }
    }
}

/** The fallback: the 6-digit code from the web app's "Connect a phone" card, on a big number pad. */
@Composable
fun CodeScreen(onUseLogin: () -> Unit) {
    val s = LocalStrings.current
    val app = App.instance
    val scope = rememberCoroutineScope()
    var code by rememberSaveable { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun submit() {
        if (busy || code.length != 6) return
        busy = true
        error = null
        scope.launch {
            try {
                val token = PushToken.get(app)
                app.signedIn(app.api.pair(code, token, deviceName()), token)
            } catch (e: Exception) {
                error = s.explain(e, on400 = s.wrongCode)
                code = ""
            } finally {
                busy = false
            }
        }
    }
    // Six digits typed: connect straight away.
    LaunchedEffect(code) { if (code.length == 6) submit() }

    AuthFrame(s.codeTitle, s.codeSub) {
        // The code so far, in six boxes.
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            repeat(6) { i ->
                Box(
                    Modifier.weight(1f).aspectRatio(0.8f)
                        .border(2.dp, if (i == code.length) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline,
                            RoundedCornerShape(12.dp))
                        .semantics { contentDescription = s.fill(s.codeDigit, "n" to (i + 1)) + ": " + (code.getOrNull(i) ?: "") },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(code.getOrNull(i)?.toString() ?: "", style = TextStyle(fontSize = 34.sp, fontWeight = FontWeight.Bold))
                }
            }
        }
        error?.let { ErrorBox(it) }
        NumberPad(
            onDigit = { if (code.length < 6 && !busy) { code += it; error = null } },
            onDelete = { if (!busy) code = code.dropLast(1) },
            deleteLabel = s.deleteDigit,
        )
        BigButton(s.connect, ::submit, enabled = code.length == 6, busy = busy)
        SecondButton(s.useLogin, onUseLogin)
    }
}

@Composable
private fun NumberPad(onDigit: (Char) -> Unit, onDelete: () -> Unit, deleteLabel: String) {
    val rows = listOf("123", "456", "789", " 0<")
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        rows.forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { key ->
                    val mod = Modifier.weight(1f).heightIn(min = 68.dp)
                    when (key) {
                        ' ' -> Spacer(mod)
                        '<' -> FilledTonalButton(onClick = onDelete, modifier = mod, shape = RoundedCornerShape(18.dp)) {
                            Icon(Icons.AutoMirrored.Filled.Backspace, contentDescription = deleteLabel)
                        }
                        else -> FilledTonalButton(onClick = { onDigit(key) }, modifier = mod, shape = RoundedCornerShape(18.dp)) {
                            Text(key.toString(), style = TextStyle(fontSize = 30.sp, fontWeight = FontWeight.SemiBold))
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
    val app = App.instance
    val scope = rememberCoroutineScope()
    var people by remember { mutableStateOf<List<Person>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    LaunchedEffect(attempt) {
        error = null
        try {
            people = app.api.people().patients
        } catch (e: Exception) {
            error = s.explain(e)
        }
    }
    AuthFrame(s.pickPatient, s.pickPatientSub) {
        error?.let { ErrorBox(it) { attempt++ } }
        val list = people
        if (list == null && error == null) Text(s.loading)
        if (list != null && list.isEmpty()) Text(s.nobody)
        list?.forEach { p ->
            SecondButton(p.name, onClick = {
                scope.launch { app.prefs.savePairing(Pairing("debug", "debug", p.id, p.name), null) }
            })
        }
        TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
            Text(s.back, style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
        }
    }
}
