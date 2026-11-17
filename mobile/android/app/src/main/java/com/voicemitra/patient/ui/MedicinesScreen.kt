package com.voicemitra.patient.ui

import android.app.DatePickerDialog
import android.app.TimePickerDialog
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.CalendarToday
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Medication
import androidx.compose.material.icons.outlined.Remove
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import com.voicemitra.patient.App
import com.voicemitra.patient.data.ApiException
import com.voicemitra.patient.data.Medicine
import com.voicemitra.patient.data.OwnMedicineBody
import com.voicemitra.patient.data.PatientMedicines
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import java.time.LocalDate

/**
 * The "Medicines" tab: web/src/app/patients/[id]/medicines/page.tsx. Two kinds: the doctor's prescription
 * (entered by the clinic, read-only here) and the patient's own medicines, which they add, change and remove.
 */
@Composable
fun MedicinesTab(patientId: String) {
    val s = LocalStrings.current
    val loaded = rememberLoaded(patientId) { App.instance.api.medicines(patientId) }
    // null = the list; Adding / Editing = the form instead of the list.
    var form by remember { mutableStateOf<FormMode?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var confirming by remember { mutableStateOf<Medicine?>(null) }
    var removing by remember { mutableStateOf(false) }
    var removeError by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    BackHandler(enabled = form != null) { form = null }

    val f = form
    if (f != null) {
        TabPage {
            OwnMedicineForm(patientId, (f as? FormMode.Editing)?.m,
                onDone = { name -> form = null; notice = s.fill(s.medSaved, "name" to name); loaded.retry() },
                onCancel = { form = null })
        }
        return
    }

    TabPage {
        H1(s.medsTitle)
        LoadedContent(loaded) { data ->
            MedicinesBody(
                data, notice = notice, onDismissNotice = { notice = null },
                onAdd = { notice = null; form = FormMode.Adding },
                onEdit = { notice = null; form = FormMode.Editing(it) },
                onRemove = { removeError = false; confirming = it },
            )
        }
    }

    confirming?.let { m ->
        AlertDialog(
            onDismissRequest = { if (!removing) confirming = null },
            title = { Text(s.fill(s.medRemoveQ, "name" to m.name), style = MaterialTheme.typography.titleLarge) },
            text = { if (removeError) Text(s.medRemoveError, color = Vm.colors.critInk, style = MaterialTheme.typography.bodyLarge) },
            confirmButton = {
                TextButton(enabled = !removing, onClick = {
                    removing = true
                    scope.launch {
                        try {
                            val res = App.instance.api.removeMedicine(patientId, m.dosageId)
                            notice = s.fill(if (res.outcome == "stopped") s.medStopped else s.medDeleted, "name" to m.name)
                            confirming = null
                            loaded.retry()
                        } catch (e: CancellationException) {
                            throw e
                        } catch (_: Exception) {
                            removeError = true
                        } finally {
                            removing = false
                        }
                    }
                }) { Text(s.medRemoveYes, color = Vm.colors.critInk, style = MaterialTheme.typography.labelLarge) }
            },
            dismissButton = {
                TextButton(enabled = !removing, onClick = { confirming = null }) {
                    Text(s.medKeep, style = MaterialTheme.typography.labelLarge)
                }
            },
            containerColor = Vm.colors.surface,
        )
    }
}

sealed interface FormMode {
    data object Adding : FormMode
    data class Editing(val m: Medicine) : FormMode
}

/** The list. Without the callbacks (screenshots) it shows the patient's own medicines without buttons. */
@Composable
fun MedicinesBody(
    data: PatientMedicines,
    notice: String? = null,
    onDismissNotice: () -> Unit = {},
    onAdd: (() -> Unit)? = null,
    onEdit: ((Medicine) -> Unit)? = null,
    onRemove: ((Medicine) -> Unit)? = null,
) {
    val s = LocalStrings.current
    val c = Vm.colors
    AllergiesCard(data.allergies)

    if (notice != null) {
        Callout(Icons.Outlined.CheckCircle, Tone.Good) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(notice, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.weight(1f))
                IconButton(onClick = onDismissNotice, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.Outlined.Close, contentDescription = s.close, tint = c.ink2)
                }
            }
        }
    }

    val prescribed = data.medicines.filter { it.active && !it.isOwn }
    val own = data.medicines.filter { it.active && it.isOwn }
    val past = data.medicines.filter { !it.active }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Eyebrow(s.medFromDoctor)
        Muted(s.medFromDoctorSub, small = false)
        if (prescribed.isEmpty()) VmCard { EmptyState(Icons.Outlined.Medication, s.medDoctorNone) }
        prescribed.forEach { MedicineCard(it) }
    }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Eyebrow(s.medOwn)
        Muted(s.medOwnSub, small = false)
        if (own.isEmpty()) Muted(s.medOwnNone, small = false)
        own.forEach { MedicineCard(it, onEdit, onRemove) }
        if (onAdd != null) VmButton(s.medAdd, onAdd, icon = Icons.Outlined.Add)
    }

    if (past.isNotEmpty()) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Eyebrow(s.medPast)
            past.forEach { if (it.isOwn) MedicineCard(it, onEdit, onRemove) else MedicineCard(it) }
        }
    }
}

@Composable
private fun MedicineCard(m: Medicine, onEdit: ((Medicine) -> Unit)? = null, onRemove: ((Medicine) -> Unit)? = null) {
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
        if (!m.active && m.isOwn) Chip(s.medOwnTag, null, Tone.Neutral)
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
        if (m.isOwn && onEdit != null && onRemove != null) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                VmButton(s.medEdit, { onEdit(m) }, Modifier.weight(1f), kind = BtnKind.Secondary, icon = Icons.Outlined.Edit, xl = false)
                VmButton(s.medRemove, { onRemove(m) }, Modifier.weight(1f), kind = BtnKind.DangerSoft, icon = Icons.Outlined.DeleteOutline, xl = false)
            }
        }
    }
}

// --- add / change one of the patient's own medicines --------------------------------------------

private const val MAX_TIMES = 6

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = Vm.colors.surface, unfocusedContainerColor = Vm.colors.surface,
    focusedBorderColor = Vm.colors.accent, unfocusedBorderColor = Vm.colors.lineStrong,
    focusedLabelColor = Vm.colors.accent, unfocusedLabelColor = Vm.colors.muted,
    focusedTextColor = Vm.colors.ink, unfocusedTextColor = Vm.colors.ink, cursorColor = Vm.colors.accent,
)

/** A big tappable box showing a value (a time or a date); tapping opens the phone's own picker. */
@Composable
private fun PickerBox(value: String, icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val c = Vm.colors
    Row(
        modifier
            .heightIn(min = 64.dp)
            .background(c.surface, RoundedCornerShape(16.dp))
            .border(BorderStroke(1.5.dp, c.lineStrong), RoundedCornerShape(16.dp))
            .clickable(role = Role.Button, onClickLabel = label, onClick = onClick)
            .padding(horizontal = 18.dp)
            .semantics { contentDescription = "$label: $value" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = c.ink2, modifier = Modifier.size(24.dp))
        Spacer(Modifier.width(12.dp))
        Text(value, style = MaterialTheme.typography.titleLarge, color = c.ink)
    }
}

@Composable
fun OwnMedicineForm(patientId: String, editing: Medicine?, onDone: (String) -> Unit, onCancel: () -> Unit) {
    val s = LocalStrings.current
    val c = Vm.colors
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var name by remember { mutableStateOf(editing?.name ?: "") }
    var dose by remember { mutableStateOf(editing?.dose ?: "") }
    val times = remember { mutableStateListOf<String>().apply { addAll(editing?.times?.ifEmpty { null } ?: listOf("08:00")) } }
    var often by remember {
        mutableStateOf(when (editing?.frequency) { "weekly" -> "weekly"; "every_x_day" -> "every_x_day"; else -> "fixed_times" })
    }
    var every by remember { mutableIntStateOf(editing?.intervalDays ?: 2) }
    var from by remember { mutableStateOf(editing?.fromDate?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: LocalDate.now()) }
    var until by remember { mutableStateOf(editing?.toDate?.let { runCatching { LocalDate.parse(it) }.getOrNull() }) }
    var busy by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf<String?>(null) }

    fun pickTime(current: String?, onPicked: (String) -> Unit) {
        val (h, m) = (current ?: "20:00").split(":").map { it.toIntOrNull() ?: 0 }
        TimePickerDialog(context, { _, hh, mm -> onPicked("%02d:%02d".format(hh, mm)) }, h, m, false).show()
    }

    fun pickDate(current: LocalDate, onPicked: (LocalDate) -> Unit) {
        DatePickerDialog(context, { _, y, mo, d -> onPicked(LocalDate.of(y, mo + 1, d)) },
            current.year, current.monthValue - 1, current.dayOfMonth).show()
    }

    fun save() {
        val cleanTimes = times.distinct().sorted()
        problem = when {
            name.isBlank() -> s.fNeedName
            dose.isBlank() -> s.fNeedDose
            until?.isBefore(from) == true -> s.fBadDates
            else -> null
        }
        if (problem != null || cleanTimes.isEmpty()) return
        val body = OwnMedicineBody(
            name = name.trim(), dose = dose.trim(), frequency = often, times = cleanTimes,
            intervalDays = if (often == "every_x_day") every else null,
            fromDate = from.toString(), toDate = until?.toString(),
        )
        busy = true
        scope.launch {
            try {
                if (editing != null) App.instance.api.updateMedicine(patientId, editing.dosageId, body)
                else App.instance.api.addOwnMedicine(patientId, body)
                onDone(body.name)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                problem = if (e is ApiException && e.code == 422) s.fSaveError else s.explain(e)
            } finally {
                busy = false
            }
        }
    }

    H1(if (editing != null) s.fill(s.fEditTitle, "name" to editing.name) else s.fAddTitle)

    OutlinedTextField(
        value = name, onValueChange = { name = it.take(80); problem = null }, label = { Text(s.fName) },
        singleLine = true, shape = RoundedCornerShape(16.dp), colors = fieldColors(),
        textStyle = MaterialTheme.typography.titleLarge,
        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words, imeAction = ImeAction.Next),
        modifier = Modifier.fillMaxWidth().heightIn(min = 68.dp),
    )
    OutlinedTextField(
        value = dose, onValueChange = { dose = it.take(80); problem = null }, label = { Text(s.fDose) },
        singleLine = true, shape = RoundedCornerShape(16.dp), colors = fieldColors(),
        textStyle = MaterialTheme.typography.titleLarge,
        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Done),
        modifier = Modifier.fillMaxWidth().heightIn(min = 68.dp),
    )

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Eyebrow(s.fTimes)
        times.forEachIndexed { i, t ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                PickerBox(clockLabel(t), Icons.Outlined.Schedule, s.fTimes, Modifier.weight(1f)) { pickTime(t) { times[i] = it } }
                if (times.size > 1) {
                    IconButton(onClick = { times.removeAt(i) }, modifier = Modifier.size(56.dp)) {
                        Icon(Icons.Outlined.Close, contentDescription = s.fRemoveTime, tint = c.ink2)
                    }
                }
            }
        }
        if (times.size < MAX_TIMES) {
            VmButton(s.fAddTime, { pickTime(null) { if (it !in times) times.add(it) } }, kind = BtnKind.Secondary,
                icon = Icons.Outlined.Add, xl = false)
        }
    }

    Column(Modifier.selectableGroup(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Eyebrow(s.fHowOften)
        listOf("fixed_times" to s.fEveryDay, "weekly" to s.fOnceWeek, "every_x_day" to s.fEveryFew).forEach { (v, label) ->
            Row(
                Modifier.fillMaxWidth().heightIn(min = 56.dp)
                    .selectable(selected = often == v, role = Role.RadioButton, onClick = { often = v }),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = often == v, onClick = null,
                    colors = RadioButtonDefaults.colors(selectedColor = c.accent, unselectedColor = c.ink2))
                Spacer(Modifier.width(12.dp))
                Text(label, style = MaterialTheme.typography.bodyLarge, color = c.ink)
            }
        }
        if (often == "weekly") Muted(s.fWeekHint, small = false)
        if (often == "every_x_day") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { every = (every - 1).coerceAtLeast(2) }, enabled = every > 2, modifier = Modifier.size(56.dp)) {
                    Icon(Icons.Outlined.Remove, contentDescription = s.fFewer, tint = c.ink)
                }
                Text(s.fill(s.fEveryN, "n" to every), style = MaterialTheme.typography.titleLarge, color = c.ink,
                    modifier = Modifier.padding(horizontal = 8.dp))
                IconButton(onClick = { every = (every + 1).coerceAtMost(90) }, enabled = every < 90, modifier = Modifier.size(56.dp)) {
                    Icon(Icons.Outlined.Add, contentDescription = s.fMore, tint = c.ink)
                }
            }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Eyebrow(s.fFrom)
        PickerBox(dayOfDate(from.toString(), s.lang), Icons.Outlined.CalendarToday, s.fFrom, Modifier.fillMaxWidth()) {
            pickDate(from) { from = it; problem = null }
        }
        Eyebrow(s.fUntil)
        Row(verticalAlignment = Alignment.CenterVertically) {
            PickerBox(until?.let { dayOfDate(it.toString(), s.lang) } ?: s.fNoEnd, Icons.Outlined.CalendarToday, s.fUntil,
                Modifier.weight(1f)) { pickDate(until ?: from) { until = it; problem = null } }
            if (until != null) {
                IconButton(onClick = { until = null }, modifier = Modifier.size(56.dp)) {
                    Icon(Icons.Outlined.Close, contentDescription = s.fClearEnd, tint = c.ink2)
                }
            }
        }
    }

    problem?.let { p ->
        Callout(Icons.Outlined.ErrorOutline, Tone.Crit) { Text(p, style = MaterialTheme.typography.bodyLarge) }
    }

    VmButton(s.fSave, { save() }, busy = busy)
    VmButton(s.fCancel, onCancel, kind = BtnKind.Secondary, enabled = !busy, xl = false)
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
