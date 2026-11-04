package com.voicemitra.patient.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.voicemitra.patient.App
import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.Settings
import kotlinx.coroutines.launch

/** Language, server address, the setup checklist and log out. Reachable before and after signing in. */
@Composable
fun SettingsScreen(settings: Settings, onBack: () -> Unit, onSetup: (() -> Unit)?, onLogOut: (() -> Unit)?) {
    val s = LocalStrings.current
    val app = App.instance
    val scope = rememberCoroutineScope()
    var url by rememberSaveable { mutableStateOf(settings.serverUrl) }
    var saved by remember { mutableStateOf(false) }
    var confirmLogOut by remember { mutableStateOf(false) }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(s.settings, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })

        Panel {
            Text(s.language, style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                listOf(Lang.HI to "हिंदी", Lang.EN to "English").forEach { (lang, label) ->
                    FilterChip(
                        selected = settings.lang == lang,
                        onClick = { scope.launch { app.prefs.setLang(lang) } },
                        label = { Text(label, style = MaterialTheme.typography.titleMedium) },
                        modifier = Modifier.heightIn(min = 56.dp),
                    )
                }
            }
        }

        settings.pairing?.let { p ->
            Panel {
                Text(s.fill(s.signedInAs, "name" to p.patientName), style = MaterialTheme.typography.titleMedium)
                if (onSetup != null) SecondButton(s.setupChecklist, onSetup)
                if (onLogOut != null) SecondButton(s.logOut, { confirmLogOut = true })
            }
        }

        Panel {
            Text(s.serverUrl, style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = url,
                onValueChange = { url = it; saved = false },
                placeholder = { Text(s.serverUrlHint) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Done,
                    autoCorrectEnabled = false),
                modifier = Modifier.fillMaxWidth(),
            )
            BigButton(if (saved) s.saved else s.save, {
                scope.launch { app.prefs.setServerUrl(url); saved = true }
            })
        }

        TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) {
            Text(s.back, style = MaterialTheme.typography.labelLarge)
        }
    }

    if (confirmLogOut && onLogOut != null) {
        AlertDialog(
            onDismissRequest = { confirmLogOut = false },
            text = { Text(s.logOutConfirm, style = MaterialTheme.typography.bodyLarge) },
            confirmButton = { TextButton(onClick = { confirmLogOut = false; onLogOut() }) { Text(s.logOut) } },
            dismissButton = { TextButton(onClick = { confirmLogOut = false }) { Text(s.cancel) } },
        )
    }
}
