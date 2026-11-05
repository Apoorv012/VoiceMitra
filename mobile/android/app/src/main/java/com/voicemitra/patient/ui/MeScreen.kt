package com.voicemitra.patient.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.KeyboardArrowUp
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.voicemitra.patient.BuildConfig
import com.voicemitra.patient.App
import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.PatientHome
import com.voicemitra.patient.data.Settings
import kotlinx.coroutines.launch

/** EN / हि pill, as in the web app's header (`.lang-switch`). */
@Composable
fun LangSwitch(lang: Lang, onChange: (Lang) -> Unit) {
    val c = Vm.colors
    Row(Modifier.background(c.surface, CircleShape).border(1.dp, c.lineStrong, CircleShape).padding(3.dp)) {
        listOf(Lang.EN to "EN", Lang.HI to "हि").forEach { (l, label) ->
            val on = l == lang
            Text(
                label,
                color = if (on) androidx.compose.ui.graphics.Color.White else c.ink2,
                style = MaterialTheme.typography.labelMedium,
                modifier = Modifier
                    .background(if (on) c.accent else androidx.compose.ui.graphics.Color.Transparent, CircleShape)
                    .clickable(role = Role.Tab) { onChange(l) }
                    .semantics { selected = on; contentDescription = if (l == Lang.HI) "हिंदी" else "English" }
                    .heightIn(min = 44.dp)
                    .padding(horizontal = 16.dp, vertical = 12.dp),
            )
        }
    }
}

/** The "Me" tab: web/src/app/patients/[id]/me/page.tsx, plus this phone's own settings. */
@Composable
fun MeTab(settings: Settings, setupLeft: Int, onSetup: () -> Unit, onLogOut: () -> Unit) {
    val pairing = settings.pairing ?: return
    val app by lazy { App.instance }
    val scope = rememberCoroutineScope()
    val loaded = rememberLoaded(pairing.patientId) { app.api.home(pairing.patientId) }
    TabPage {
        MeBody(
            name = loaded.data?.patient?.name ?: pairing.patientName,
            home = loaded.data,
            settings = settings,
            setupLeft = setupLeft,
            onLang = { scope.launch { app.prefs.setLang(it) } },
            onSaveServer = { scope.launch { app.prefs.setServerUrl(it) } },
            onSetup = onSetup,
            onLogOut = onLogOut,
        )
        loaded.error?.let { if (loaded.data == null) ErrorState(LocalStrings.current.explain(it), loaded.retry, it.isOffline()) }
    }
}

@Suppress("UNUSED_PARAMETER")  // onLang: the language switch is in the header only (one place)
@Composable
fun MeBody(
    name: String,
    home: PatientHome?,
    settings: Settings,
    setupLeft: Int,
    onLang: (Lang) -> Unit,
    onSaveServer: (String) -> Unit,
    onSetup: () -> Unit,
    onLogOut: () -> Unit,
    confirmAtStart: Boolean = false,  // screenshots: show the sign-out dialog
) {
    val s = LocalStrings.current
    val c = Vm.colors
    var confirmLogOut by remember { mutableStateOf(confirmAtStart) }

    // Who
    Row(verticalAlignment = Alignment.CenterVertically) {
        Avatar(initials(name), size = 88.dp, bg = c.sage, fg = c.accent)
        Spacer(Modifier.width(18.dp))
        Column(Modifier.weight(1f)) {
            H1(name)
            home?.patient?.age?.let { Text(s.fill(s.yearsOld, "n" to it), color = c.ink2, style = MaterialTheme.typography.bodyLarge) }
        }
    }

    if (home != null) AllergiesCard(home.allergies)
    home?.caregiver?.let { cg -> IconCard(Icons.Outlined.FavoriteBorder, s.caregiver, "${cg.name} (${cg.relation})") }

    // This phone: can VoiceMitra ring it? (the setup checklist)
    IconCard(
        Icons.Outlined.PhoneAndroid, s.thisPhone,
        if (setupLeft == 0) s.phoneReady else s.fill(s.phoneFix, "n" to setupLeft),
        tone = if (setupLeft == 0) null else Tone.Warn,
        onClick = onSetup,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (setupLeft > 0) Box(Modifier.size(12.dp).background(c.warn, CircleShape))
            else Icon(Icons.Outlined.CheckCircle, null, tint = c.goodInk, modifier = Modifier.size(24.dp))
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, tint = if (setupLeft > 0) c.warnInk else c.muted)
        }
    }

    VmButton(s.logOut, { confirmLogOut = true }, kind = BtnKind.DangerSoft, icon = Icons.AutoMirrored.Outlined.Logout)

    Text(s.fill(s.version, "v" to BuildConfig.VERSION_NAME), color = c.muted, style = MaterialTheme.typography.bodyMedium,
        textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    Advanced(settings, onSaveServer)

    if (confirmLogOut) {
        AlertDialog(
            onDismissRequest = { confirmLogOut = false },
            icon = { Icon(Icons.AutoMirrored.Outlined.Logout, null, tint = c.critInk) },
            title = { Text(s.logOut, style = MaterialTheme.typography.headlineSmall) },
            text = { Text(s.logOutConfirm, style = MaterialTheme.typography.bodyLarge, color = c.ink2) },
            confirmButton = {
                VmButton(s.logOut, { confirmLogOut = false; onLogOut() }, kind = BtnKind.Danger, xl = false)
            },
            dismissButton = {
                VmButton(s.cancel, { confirmLogOut = false }, kind = BtnKind.Secondary, xl = false)
            },
            containerColor = c.surface,
            shape = RoundedCornerShape(28.dp),
        )
    }
}

/** The server address, folded away: patients never need it. */
@Composable
fun Advanced(settings: Settings, onSaveServer: (String) -> Unit) {
    val s = LocalStrings.current
    val c = Vm.colors
    var open by rememberSaveable { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth().clickable(role = Role.Button) { open = !open }.heightIn(min = 56.dp).padding(horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.Center,
        ) {
            Icon(Icons.Outlined.Tune, null, tint = c.muted, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(8.dp))
            Text(s.advanced, color = c.muted, style = MaterialTheme.typography.labelMedium)
            Icon(if (open) Icons.Outlined.KeyboardArrowUp else Icons.Outlined.KeyboardArrowDown, null, tint = c.muted)
        }
        if (open) VmCard { ServerField(settings, onSaveServer) }
    }
}

@Composable
private fun ServerField(settings: Settings, onSave: (String) -> Unit) {
    val s = LocalStrings.current
    var url by rememberSaveable(settings.serverUrl) { mutableStateOf(settings.serverUrl) }
    var saved by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(s.serverUrl, style = MaterialTheme.typography.bodyMedium, color = Vm.colors.muted)
        OutlinedTextField(
            value = url,
            onValueChange = { url = it; saved = false },
            placeholder = { Text(s.serverUrlHint) },
            singleLine = true,
            shape = RoundedCornerShape(14.dp),
            textStyle = MaterialTheme.typography.bodyLarge,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done, autoCorrectEnabled = false),
            modifier = Modifier.fillMaxWidth(),
        )
        VmButton(if (saved) s.saved else s.save, { onSave(url); saved = true }, kind = BtnKind.Secondary, xl = false)
    }
}
