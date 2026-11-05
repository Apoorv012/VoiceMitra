package com.voicemitra.patient.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.FavoriteBorder
import androidx.compose.material.icons.outlined.Medication
import androidx.compose.material.icons.outlined.GraphicEq
import androidx.compose.material.icons.outlined.NotificationsActive
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.Hyphens
import androidx.compose.ui.text.style.LineBreak
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.voicemitra.patient.App
import com.voicemitra.patient.data.PatientHome
import com.voicemitra.patient.data.Slot

/** What the Talk button should say: start a call, one is starting, or go back to the one in progress. */
enum class TalkState { Idle, Starting, InCall }

/** The "Today" tab: web/src/app/patients/[id]/page.tsx. */
@Composable
fun TodayTab(patientId: String, talk: TalkState, onTalk: () -> Unit) {
    val loaded = rememberLoaded(patientId, refreshMs = 30_000) { App.instance.api.home(patientId) }
    TabPage {
        LoadedContent(loaded) { TodayBody(it, talk, onTalk) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TodayBody(h: PatientHome, talk: TalkState, onTalk: () -> Unit) {
    val s = LocalStrings.current
    val c = Vm.colors
    val now = LocalNow.current()
    val tz = h.timezone

    // Hello
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Eyebrow("${greetingOf(tz, s, now)} · ${fullDateToday(tz, s.lang, now)}")
        H1(s.fill(s.greeting, "name" to h.patient.name.substringBefore(' ')))
    }

    // The one big thing to do here.
    VmCard(color = c.sage, border = null, padding = 24.dp, spacing = 18.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(72.dp).background(c.accent, CircleShape), contentAlignment = Alignment.Center) {
                Icon(Icons.Outlined.GraphicEq, null, tint = if (c.dark) c.onBtn else Color.White, modifier = Modifier.size(38.dp))
            }
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                H2(s.talkTitle)
                Text(s.talkSub, color = c.ink2, style = MaterialTheme.typography.bodyMedium)
            }
        }
        when (talk) {
            TalkState.InCall -> VmButton(s.talkInCall, onTalk, kind = BtnKind.Good, icon = Icons.Outlined.Call)
            else -> VmButton(if (talk == TalkState.Starting) s.talkStarting else s.talkBtn, onTalk,
                icon = Icons.Outlined.Call, busy = talk == TalkState.Starting)
        }
        Text(
            h.lastCheckin?.let { s.fill(s.lastCheckin, "when" to whenLabel(it.at, tz, s, now)) } ?: s.noCheckinYet,
            color = c.muted, style = MaterialTheme.typography.bodySmall,
        )
    }

    // Next dose
    h.nextDose?.let { next ->
        Row(
            Modifier.fillMaxWidth().background(c.accentSoft, RoundedCornerShape(24.dp)).padding(20.dp)
                .semantics(mergeDescendants = true) { contentDescription = s.nextDose },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconCircle(Icons.Outlined.Medication, size = 56.dp, bg = c.page, fg = c.accent)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Eyebrow(s.nextDose, color = c.accent)
                Text(
                    buildAnnotatedString {
                        dueTogether(h, next).forEachIndexed { i, d ->
                            if (i > 0) append(", ")
                            withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(d.medicine) }
                            withStyle(SpanStyle(color = c.ink2, fontWeight = FontWeight.Normal)) { append(" · ${d.dose}") }
                        }
                    },
                    style = MaterialTheme.typography.titleLarge, color = c.ink,
                )
                val whenText = "${dayLabel(next.at, tz, s, now)}, ${timeOf(next.at, tz)}" +
                    if (next.state != "due") " · ${inWords(next.at, s, now)}" else ""
                Text(whenText, style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Medium), color = c.accent)
            }
        }
    }

    // Today's medicines
    VmCard(padding = 0.dp, spacing = 0.dp) {
        H2(s.todaysMeds, Modifier.padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 8.dp))
        if (h.today.isEmpty()) EmptyState(Icons.Outlined.Medication, s.noneToday)
        h.today.forEachIndexed { i, slot ->
            if (i > 0) HorizontalDivider(color = c.line)
            val isNext = h.nextDose?.let { it.dosageId == slot.dosageId && it.at == slot.at } == true
            DoseRow(slot, tz, highlight = isNext)
        }
        Spacer(Modifier.height(6.dp))
    }

    // This week
    if (h.week.isNotEmpty()) VmCard {
        H2(s.thisWeek)
        val a = h.adherence
        val total = a.taken + a.missed + a.unrecorded
        val anyScheduled = h.week.any { it.state != "none" }
        if (anyScheduled) {
            if (total > 0) Text(s.fill(s.weekSummary, "taken" to a.taken, "total" to total),
                style = MaterialTheme.typography.bodyMedium, color = c.ink2)
            Row(Modifier.fillMaxWidth().padding(top = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                h.week.forEach { d ->
                    val today = isToday(d.date, tz, now)
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(weekdayOf(d.date, s.lang), style = MaterialTheme.typography.labelMedium,
                            color = if (today) c.accent else c.muted, maxLines = 1)
                        DayDot(d.state, size = 36.dp, ring = today)
                    }
                }
            }
            FlowRow(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(top = 4.dp)) {
                listOf("good" to s.dayGood, "mixed" to s.dayMixed, "missed" to s.dayMissed, "unknown" to s.dayUnknown).forEach { (st, label) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        DayDot(st, size = 22.dp)
                        Spacer(Modifier.width(6.dp))
                        Text(label, style = MaterialTheme.typography.bodySmall, color = c.ink2)
                    }
                }
            }
            if (a.unrecorded > 0) Text(s.fill(s.weekUnchecked, "n" to a.unrecorded), style = MaterialTheme.typography.bodySmall, color = c.muted)
        } else {
            Muted(s.weekNone)
        }
    }

    // How you're doing
    h.howDoing?.let { hd ->
        VmCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                H2(s.howDoing, Modifier.weight(1f))
                Text(dayLabel(hd.at, tz, s, now), style = MaterialTheme.typography.bodySmall, color = c.muted)
            }
            when (hd.band) {
                "ok" -> Chip(s.doingOk, Icons.Outlined.Check, Tone.Good, large = true)
                "watch" -> Chip(s.doingWatch, Icons.Outlined.WarningAmber, Tone.Warn, large = true)
                else -> Chip(s.doingUrgent, Icons.Outlined.WarningAmber, Tone.Crit, large = true)
            }
            Text(hd.summary, color = c.ink2, style = MaterialTheme.typography.bodyLarge)
        }
    }

    // Reminders the patient asked for
    if (h.reminders.isNotEmpty()) Callout(Icons.Outlined.NotificationsActive, Tone.Accent) {
        Eyebrow(s.reminder, color = c.accent)
        h.reminders.forEach { r ->
            Text(s.fill(s.reminderAt, "time" to "${dayLabel(r, tz, s, now)}, ${timeOf(r, tz)}"),
                style = MaterialTheme.typography.bodyLarge, color = c.ink)
        }
    }

    h.caregiver?.let { cg ->
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp), horizontalArrangement = Arrangement.Center) {
            Icon(Icons.Outlined.FavoriteBorder, null, tint = c.muted, modifier = Modifier.size(20.dp).padding(top = 2.dp))
            Spacer(Modifier.width(6.dp))
            Text(s.fill(s.caregiverLine, "name" to cg.name, "relation" to cg.relation), color = c.muted,
                style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
        }
    }
}

/** Everything due at the same time as the next dose. */
private fun dueTogether(h: PatientHome, next: Slot): List<Slot> =
    h.today.filter { it.at == next.at }.ifEmpty { listOf(next) }

/** `.dose`: time, medicine + dose, state. The next dose is tinted. */
@Composable
private fun DoseRow(slot: Slot, tz: String, highlight: Boolean) {
    val c = Vm.colors
    Row(
        Modifier.fillMaxWidth()
            .then(if (highlight) Modifier.background(c.accentSoft) else Modifier)
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(timeOf(slot.at, tz), style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
            color = c.ink, modifier = Modifier.widthIn(min = 96.dp))
        Column(Modifier.weight(1f).padding(end = 8.dp)) {
            Text(slot.medicine, style = MaterialTheme.typography.titleMedium.copy(hyphens = Hyphens.None, lineBreak = LineBreak.Paragraph), color = c.ink)
            Text(slot.dose, style = MaterialTheme.typography.bodyMedium, color = c.muted)
        }
        SlotChip(slot.state)
    }
}
