package com.voicemitra.patient.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.MedicalServices
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.voicemitra.patient.App
import com.voicemitra.patient.data.Alert
import com.voicemitra.patient.data.Checkin
import com.voicemitra.patient.data.PatientHistory

/** The "History" tab: web/src/app/patients/[id]/history/page.tsx -- check-ins and family alerts, newest first. */
@Composable
fun HistoryTab(patientId: String) {
    val loaded = rememberLoaded(patientId) { App.instance.api.history(patientId) }
    TabPage {
        H1(LocalStrings.current.historyTitle)
        LoadedContent(loaded) { HistoryBody(it) }
    }
}

private class Item(val at: String, val checkin: Checkin? = null, val alert: Alert? = null)

@Composable
fun HistoryBody(data: PatientHistory) {
    val s = LocalStrings.current
    val items = (data.checkins.map { Item(it.at, checkin = it) } + data.alerts.map { Item(it.at, alert = it) })
        .sortedByDescending { it.at }
    if (items.isEmpty()) {
        VmCard { EmptyState(Icons.Outlined.History, s.noHistory) }
        return
    }
    Column {
        items.forEachIndexed { i, item -> TimelineItem(item, data.timezone, last = i == items.lastIndex) }
    }
}

/** `.timeline > li`: a dot on a line, the time, then the card. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TimelineItem(item: Item, tz: String, last: Boolean) {
    val s = LocalStrings.current
    val c = Vm.colors
    val now = LocalNow.current()
    val ch = item.checkin
    val tone: Color = when {
        item.alert != null -> c.warn
        ch?.doctorConnected == true || ch?.patientStatus == "urgent" -> c.crit
        ch?.patientStatus == "remedy" -> c.warn
        else -> c.good
    }
    Row(Modifier.height(IntrinsicSize.Min)) {
        Box(Modifier.width(28.dp).fillMaxHeight()) {
            if (!last) Box(Modifier.padding(start = 7.dp, top = 10.dp).width(2.dp).fillMaxHeight().background(c.line))
            Box(Modifier.padding(top = 5.dp).size(16.dp).background(c.surface, CircleShape).border(3.dp, tone, CircleShape))
        }
        Column(Modifier.weight(1f).padding(bottom = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("${dayLabel(item.at, tz, s, now)}, ${timeOf(item.at, tz)}", style = MaterialTheme.typography.labelMedium, color = c.muted)
            if (ch != null) VmCard(spacing = 10.dp) {
                Text(s.checkin, style = MaterialTheme.typography.titleMedium, color = c.ink)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    when (ch.medicineStatus) {
                        "taken" -> Chip(s.medStatusTaken, Icons.Outlined.Check, Tone.Good)
                        "not_taken" -> Chip(s.medStatusNotTaken, Icons.Outlined.Close, Tone.Crit)
                        null -> Unit
                        else -> Chip(s.medStatusUnsure, Icons.Outlined.HelpOutline, Tone.Neutral)
                    }
                    if (ch.escalated) Chip(if (ch.doctorConnected) s.doctorJoined else s.escalated, Icons.Outlined.MedicalServices, Tone.Crit)
                }
                if (ch.symptoms.isNotEmpty()) Text(s.fill(s.mentioned, "list" to ch.symptoms.joinToString(", ")),
                    style = MaterialTheme.typography.bodyMedium, color = c.ink2)
                ch.summary?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = c.ink2) }
                if (ch.summary.isNullOrBlank() && ch.symptoms.isEmpty() && ch.medicineStatus == null && !ch.escalated) {
                    Text(s.nothingRecorded, style = MaterialTheme.typography.bodyMedium, color = c.muted)
                }
            }
            item.alert?.let { a ->
                Callout(Icons.Outlined.FavoriteBorder, Tone.Warn) {
                    Text(s.familyTold + (a.caregiver?.let { " · $it" } ?: ""), style = MaterialTheme.typography.titleMedium)
                    Text(a.message, style = MaterialTheme.typography.bodyMedium)
                }
            }
            Spacer(Modifier.height(0.dp))
        }
    }
}
