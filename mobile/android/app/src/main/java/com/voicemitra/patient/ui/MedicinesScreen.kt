package com.voicemitra.patient.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Medication
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.voicemitra.patient.App
import com.voicemitra.patient.data.Medicine
import com.voicemitra.patient.data.PatientMedicines

/** The "Medicines" tab: web/src/app/patients/[id]/medicines/page.tsx. */
@Composable
fun MedicinesTab(patientId: String) {
    val loaded = rememberLoaded(patientId) { App.instance.api.medicines(patientId) }
    TabPage {
        H1(LocalStrings.current.medsTitle)
        LoadedContent(loaded) { MedicinesBody(it) }
    }
}

@Composable
fun MedicinesBody(data: PatientMedicines) {
    val s = LocalStrings.current
    AllergiesCard(data.allergies)
    if (data.medicines.isEmpty()) VmCard { EmptyState(Icons.Outlined.Medication, s.noMeds) }

    val current = data.medicines.filter { it.active }
    val past = data.medicines.filter { !it.active }
    if (current.isNotEmpty()) {
        Eyebrow(s.medCurrent)
        current.forEach { MedicineCard(it) }
    }
    if (past.isNotEmpty()) {
        Eyebrow(s.medPast)
        past.forEach { MedicineCard(it) }
    }
}

@Composable
private fun MedicineCard(m: Medicine) {
    val s = LocalStrings.current
    val c = Vm.colors
    VmCard(Modifier.alpha(if (m.active) 1f else 0.7f)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(null, Icons.Outlined.Medication, size = 52.dp, bg = c.accentSoft, fg = c.accent)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                H2(m.name)
                Text(m.dose, color = c.ink2, style = MaterialTheme.typography.bodyLarge)
            }
        }
        Row(verticalAlignment = Alignment.Top) {
            Icon(Icons.Outlined.Schedule, null, tint = c.ink2, modifier = Modifier.size(22.dp))
            Spacer(Modifier.width(8.dp))
            Text(schedule(m, s), style = MaterialTheme.typography.bodyLarge, color = c.ink)
        }
        val parts = buildList {
            m.toDate?.let { add(s.fill(s.medUntil, "date" to dayOfDate(it, s.lang))) }
            if (m.active && m.daysLeft != null) add(if (m.daysLeft == 0) s.medLastDay else s.fill(s.medDaysLeft, "n" to m.daysLeft))
        }
        if (parts.isNotEmpty()) Text(parts.joinToString(" · "), color = c.muted, style = MaterialTheme.typography.bodyMedium)
        if (m.active && m.known > 0) {
            val pct = Math.round(100f * m.taken / m.known)
            Meter(pct)
            Text(s.fill(s.medWeek, "taken" to m.taken, "known" to m.known), color = c.muted, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun schedule(m: Medicine, s: Strings): String {
    val times = if (m.times.isEmpty()) "—" else m.times.joinToString(" ${s.and} ") { clockLabel(it) }
    val every = m.frequency == "every_x_day" && m.intervalDays != null
    val template = when {
        every -> s.medEvery
        m.frequency == "weekly" -> s.medWeekly
        m.frequency == "fixed_times" -> s.medFixed
        else -> s.medDaily
    }
    return s.fill(template, "times" to times, "n" to (m.intervalDays ?: 0))
}

/** `.meter`: green from 80 %, amber from 50 %, red below. */
@Composable
private fun Meter(pct: Int) {
    val c = Vm.colors
    val color = when {
        pct >= 80 -> c.good
        pct >= 50 -> c.warn
        else -> c.crit
    }
    Box(Modifier.fillMaxWidth().height(10.dp).background(c.neutralSoft, CircleShape).semantics { contentDescription = "$pct%" }) {
        Box(Modifier.fillMaxWidth(pct.coerceIn(0, 100) / 100f).fillMaxHeight().background(color, CircleShape))
    }
}

/** Allergies as a card with a shield (amber when there are any): Medicines and Me. */
@Composable
fun AllergiesCard(allergies: List<String>) {
    val s = LocalStrings.current
    IconCard(
        Icons.Outlined.Shield, s.allergies,
        if (allergies.isEmpty()) s.noAllergies else allergies.joinToString(", "),
        tone = if (allergies.isNotEmpty()) Tone.Warn else null,
    )
}

