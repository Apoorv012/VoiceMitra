package com.voicemitra.patient.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.voicemitra.patient.App
import com.voicemitra.patient.data.Lang
import com.voicemitra.patient.data.PatientHome
import com.voicemitra.patient.data.Slot
import kotlinx.coroutines.delay
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Times are ISO with an offset; show them in the patient's own time zone (`home.timezone`). */
fun clock(iso: String, zone: String, lang: Lang): String = try {
    val z = try { ZoneId.of(zone) } catch (_: Exception) { ZoneId.of("Asia/Kolkata") }
    val locale = if (lang == Lang.HI) Locale.forLanguageTag("hi-IN") else Locale.forLanguageTag("en-IN")
    OffsetDateTime.parse(iso).atZoneSameInstant(z).format(DateTimeFormatter.ofPattern("h:mm a", locale))
} catch (_: Exception) {
    ""
}

@Composable
fun HomeScreen(patientId: String, lang: Lang, onTalk: () -> Unit, talkBusy: Boolean) {
    val s = LocalStrings.current
    val app = App.instance
    var home by remember { mutableStateOf<PatientHome?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var attempt by remember { mutableIntStateOf(0) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle

    // Load whenever the screen is showing (comes back to the front after a call, too) and every minute.
    LaunchedEffect(patientId, attempt) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            while (true) {
                try {
                    home = app.api.home(patientId)
                    error = null
                } catch (e: Exception) {
                    error = s.explain(e)
                }
                delay(60_000)
            }
        }
    }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        val h = home
        Text(
            s.fill(s.greeting, "name" to (h?.patient?.name ?: app.settings.value.pairing?.patientName ?: "")),
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.semantics { heading() },
        )

        // The one big thing to do here.
        Button(
            onClick = onTalk,
            enabled = !talkBusy,
            modifier = Modifier.fillMaxWidth().heightIn(min = 96.dp),
            shape = RoundedCornerShape(28.dp),
            colors = ButtonDefaults.buttonColors(containerColor = StatusColors.answer, contentColor = Color.White),
        ) {
            Icon(Icons.Filled.Call, null, Modifier.size(36.dp))
            Spacer(Modifier.width(14.dp))
            Column {
                Text(if (talkBusy) s.talkStarting else s.talkTitle, style = MaterialTheme.typography.titleLarge)
                Text(s.talkSub, style = MaterialTheme.typography.bodySmall)
            }
        }

        if (error != null && h == null) ErrorBox(error!!) { attempt++ }
        if (h == null && error == null) Text(s.loading, style = MaterialTheme.typography.bodyLarge)

        if (h != null) {
            h.nextDose?.let { next ->
                Panel {
                    Text(s.nextDose, style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Schedule, null, Modifier.size(32.dp), tint = MaterialTheme.colorScheme.secondary)
                        Spacer(Modifier.width(10.dp))
                        Text(clock(next.at, h.timezone, lang), style = MaterialTheme.typography.headlineSmall)
                    }
                    Text(dueTogether(h, next).joinToString(", ") { "${it.medicine} (${it.dose})" },
                        style = MaterialTheme.typography.bodyLarge)
                }
            }
            h.reminders.firstOrNull()?.let {
                Panel { Text(s.fill(s.reminderAt, "time" to clock(it, h.timezone, lang)), style = MaterialTheme.typography.bodyLarge) }
            }
            Panel {
                Text(s.todaysMeds, style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
                if (h.today.isEmpty()) Text(s.noneToday, style = MaterialTheme.typography.bodyLarge)
                h.today.forEachIndexed { i, slot ->
                    if (i > 0) HorizontalDivider()
                    SlotRow(slot, h.timezone, lang)
                }
            }
            if (error != null) ErrorBox(error!!) { attempt++ }
        }
    }
}

/** Everything due at the same time as the next dose. */
private fun dueTogether(h: PatientHome, next: Slot): List<Slot> =
    h.today.filter { it.at == next.at }.ifEmpty { listOf(next) }

@Composable
private fun SlotRow(slot: Slot, zone: String, lang: Lang) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(slot.medicine, style = MaterialTheme.typography.titleMedium)
            Text("${clock(slot.at, zone, lang)} · ${slot.dose}", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        StateChip(slot.state)
    }
}

@Composable
private fun StateChip(state: String) {
    val s = LocalStrings.current
    val (label, fg, bg) = when (state) {
        "taken" -> Triple(s.doseTaken, StatusColors.good, StatusColors.goodSoft)
        "partial" -> Triple(s.dosePartial, StatusColors.warn, StatusColors.warnSoft)
        "missed" -> Triple(s.doseMissed, StatusColors.crit, StatusColors.critSoft)
        "later" -> Triple(s.doseLater, StatusColors.warn, StatusColors.warnSoft)
        "unknown" -> Triple(s.doseUnknown, StatusColors.warn, StatusColors.warnSoft)
        "skipped" -> Triple(s.doseSkipped, StatusColors.warn, StatusColors.warnSoft)
        "due" -> Triple(s.doseDue, StatusColors.crit, StatusColors.critSoft)
        "no_checkin" -> Triple(s.doseNoCheckin, MaterialTheme.colorScheme.onSurfaceVariant, MaterialTheme.colorScheme.surfaceVariant)
        else -> Triple(s.doseUpcoming, MaterialTheme.colorScheme.onSurfaceVariant, MaterialTheme.colorScheme.surfaceVariant)
    }
    Text(label, color = fg, style = MaterialTheme.typography.labelMedium,
        modifier = Modifier.background(bg, RoundedCornerShape(50)).padding(horizontal = 12.dp, vertical = 6.dp))
}
