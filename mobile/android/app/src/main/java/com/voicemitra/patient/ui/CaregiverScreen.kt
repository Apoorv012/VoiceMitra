package com.voicemitra.patient.ui

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.Call
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.KeyboardArrowUp
import androidx.compose.material.icons.outlined.Medication
import androidx.compose.material.icons.outlined.NotificationsOff
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.voicemitra.patient.App
import com.voicemitra.patient.BuildConfig
import com.voicemitra.patient.call.Notifications
import com.voicemitra.patient.caregiver.caregiverEvents
import com.voicemitra.patient.data.ApiException
import com.voicemitra.patient.data.CaregiverAlert
import com.voicemitra.patient.data.CaregiverHome
import com.voicemitra.patient.data.Pairing
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * A family contact's phone (mobile/API.md "Caregivers in the apps"): the website's caregiver page
 * (web/src/app/caregivers/[id]/page.tsx). Loads `GET /api/app/caregivers/{id}/home` while on screen,
 * again on every caregiver-socket message, every minute, and on pull-down. 401/404 = no longer signed in
 * (or no longer the family contact): forget the login. Read-only apart from "Mark as seen"; no Talk now,
 * no ringing.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaregiverHomeTab(pairing: Pairing, onLogOut: () -> Unit) {
    val app = App.instance
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val caregiverId = pairing.caregiverId ?: return
    var data by remember(caregiverId) { mutableStateOf<CaregiverHome?>(null) }
    var error by remember(caregiverId) { mutableStateOf<Throwable?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf<String?>(null) }  // the alert being marked seen ("all" = all of them)
    val refreshes = remember { Channel<Unit>(Channel.CONFLATED) }

    suspend fun load() {
        try {
            data = app.api.caregiverHome(caregiverId)
            error = null
            Notifications.cancelAlert(context)  // they're looking at it
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            if (e is ApiException && (e.code == 401 || e.code == 404)) {
                app.signedOutNotice.value = e.code == 404
                app.prefs.clearPairing()  // signed out elsewhere, or no longer the family contact
                return
            }
            error = e
        }
    }

    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(caregiverId) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            launch { caregiverEvents(app.api, caregiverId).collect { refreshes.trySend(Unit) } }
            launch { while (true) { delay(60_000); refreshes.trySend(Unit) } }
            refreshes.trySend(Unit)
            for (r in refreshes) load()
        }
    }

    // New alerts arrive as notifications: ask once (Android 13+), and offer it again on the page while off.
    var notificationsOff by remember { mutableStateOf(false) }
    var tick by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) { lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) { tick++ } }
    LaunchedEffect(tick) { notificationsOff = !NotificationManagerCompat.from(context).areNotificationsEnabled() }
    var asked by rememberSaveable { mutableStateOf(false) }
    val askNotifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { tick++ }
    LaunchedEffect(notificationsOff) {
        if (notificationsOff && !asked && Build.VERSION.SDK_INT >= 33) {
            asked = true
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
    val fixNotifications = {
        if (Build.VERSION.SDK_INT >= 33 && !asked) {
            asked = true
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            Setup.open(context, listOf(Setup.notificationSettings(context)))
        }
    }

    fun markSeen(alertId: String?) {
        if (busy != null) return
        busy = alertId ?: "all"
        scope.launch {
            try {
                if (alertId == null) app.api.markAllAlertsSeen(caregiverId) else app.api.markAlertSeen(caregiverId, alertId)
                load()
            } catch (e: Exception) {
                error = e
            } finally {
                busy = null
            }
        }
    }

    val s = LocalStrings.current
    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = {
            scope.launch {
                refreshing = true
                load()
                refreshing = false
            }
        },
        modifier = Modifier.fillMaxSize(),
    ) {
        TabPage {
            val home = data
            val err = error
            when {
                home != null -> {
                    CaregiverBody(home, busy, ::markSeen, onLogOut, notificationsOff, fixNotifications)
                    if (err != null) ErrorState(s.explain(err), { scope.launch { load() } }, offline = err.isOffline())
                }
                err != null -> ErrorState(s.explain(err), { scope.launch { load() } }, offline = err.isOffline())
                else -> LoadingState()
            }
        }
    }
}

/** The caregiver home's content, without loading (shared with the screenshots). */
@Composable
fun CaregiverBody(
    h: CaregiverHome,
    busy: String?,
    onSeen: (String?) -> Unit,  // null = all
    onLogOut: () -> Unit,
    notificationsOff: Boolean = false,
    onNotifications: () -> Unit = {},
    earlierOpenAtStart: Boolean = false,  // screenshots: show the earlier alerts
    confirmAtStart: Boolean = false,      // screenshots: show the sign-out dialog
) {
    val s = LocalStrings.current
    val c = Vm.colors
    val now = LocalNow.current()
    val tz = h.timezone
    val patientFirst = h.patient.name.trim().substringBefore(' ')
    val fresh = h.alerts.filter { it.seenAt == null }
    val seen = h.alerts.filter { it.seenAt != null }
    var earlierOpen by rememberSaveable { mutableStateOf(earlierOpenAtStart) }
    var confirmLogOut by remember { mutableStateOf(confirmAtStart) }

    fun label(a: CaregiverAlert) = when {
        a.urgent -> s.cgUrgent
        a.trigger == "unreachable" -> s.cgUnreachable
        else -> s.cgUnwell
    }

    // Hello
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Eyebrow(s.fill(s.cgLookingAfter, "name" to h.patient.name))
        H1(s.fill(s.greeting, "name" to h.caregiver.name.trim().substringBefore(' ')))
    }

    if (h.inCall) Callout(Icons.Outlined.Call, Tone.Accent) {
        Text(s.fill(s.cgInCall, "name" to patientFirst), style = MaterialTheme.typography.bodyLarge)
    }

    if (notificationsOff) Callout(Icons.Outlined.NotificationsOff, Tone.Warn) {
        Text(s.cgNotifyOff, style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(8.dp))
        VmButton(s.cgNotifyOn, onNotifications, kind = BtnKind.Secondary, xl = false)
    }

    // Alerts
    VmCard(spacing = 14.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            H2(s.cgAlerts, Modifier.weight(1f).semantics { heading() })
            if (fresh.isNotEmpty()) Chip(s.fill(s.cgNew, "n" to fresh.size), null, Tone.Crit)
        }
        if (h.alerts.isEmpty()) Muted(s.fill(s.cgNoAlerts, "name" to patientFirst), small = false)
        else if (fresh.isEmpty()) Muted(s.cgNoNew, small = false)
        fresh.forEach { a ->
            Callout(Icons.Outlined.WarningAmber, if (a.urgent) Tone.Crit else Tone.Warn) {
                Text("${label(a)} · ${whenLabel(a.at, tz, s, now)}",
                    style = MaterialTheme.typography.titleMedium)
                Text(a.message, style = MaterialTheme.typography.bodyLarge, color = c.ink)
                Spacer(Modifier.height(10.dp))
                VmButton(s.cgMarkSeen, { onSeen(a.id) }, kind = BtnKind.Secondary, icon = Icons.Outlined.Check,
                    xl = false, enabled = busy == null, busy = busy == a.id)
            }
        }
        if (fresh.size > 1) VmButton(s.cgMarkAllSeen, { onSeen(null) }, kind = BtnKind.Ghost, xl = false,
            enabled = busy == null, busy = busy == "all")
        if (seen.isNotEmpty()) {
            Row(
                Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable(role = Role.Button) { earlierOpen = !earlierOpen }
                    .semantics { stateDescription = if (earlierOpen) "open" else "closed" },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("${s.cgEarlier} (${seen.size})", style = MaterialTheme.typography.titleMedium, color = c.ink2,
                    modifier = Modifier.weight(1f))
                Icon(if (earlierOpen) Icons.Outlined.KeyboardArrowUp else Icons.Outlined.KeyboardArrowDown, null, tint = c.muted)
            }
            if (earlierOpen) seen.forEachIndexed { i, a ->
                if (i > 0) HorizontalDivider(color = c.line)
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        "${label(a)} · ${whenLabel(a.at, tz, s, now)}",
                        style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold), color = c.ink,
                    )
                    Text(a.message, style = MaterialTheme.typography.bodyLarge, color = c.ink2)
                    a.seenAt?.let {
                        Text(s.fill(s.cgSeen, "when" to whenLabel(it, tz, s, now)), style = MaterialTheme.typography.bodySmall,
                            color = c.muted)
                    }
                }
            }
        }
    }

    // Today's medicines
    VmCard(padding = 0.dp, spacing = 0.dp) {
        H2(s.fill(s.cgTodaysMeds, "name" to patientFirst), Modifier.padding(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 8.dp))
        if (h.today.isEmpty()) EmptyState(Icons.Outlined.Medication, s.noneToday)
        h.today.forEachIndexed { i, slot ->
            if (i > 0) HorizontalDivider(color = c.line)
            val isNext = h.nextDose?.let { it.dosageId == slot.dosageId && it.at == slot.at } == true
            DoseRow(slot, tz, highlight = isNext)
        }
        Text(
            h.lastCheckin?.let { s.fill(s.cgLastCheckin, "when" to whenLabel(it.at, tz, s, now)) } ?: s.noCheckinYet,
            color = c.muted, style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(start = 20.dp, end = 20.dp, top = 6.dp, bottom = 16.dp),
        )
    }

    // This week
    if (h.week.isNotEmpty()) WeekCard(h.week, h.adherence, tz)

    // How they're doing
    h.howDoing?.let { hd ->
        VmCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                H2(s.fill(s.cgHowDoing, "name" to patientFirst), Modifier.weight(1f))
                Text(dayLabel(hd.at, tz, s, now), style = MaterialTheme.typography.bodySmall, color = c.muted)
            }
            Text(hd.summary, color = c.ink2, style = MaterialTheme.typography.bodyLarge)
        }
    }

    VmButton(s.logOut, { confirmLogOut = true }, kind = BtnKind.DangerSoft, icon = Icons.AutoMirrored.Outlined.Logout)
    Box(Modifier.fillMaxWidth()) {
        Text(s.fill(s.version, "v" to BuildConfig.VERSION_NAME), color = c.muted, style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    }

    if (confirmLogOut) {
        AlertDialog(
            onDismissRequest = { confirmLogOut = false },
            icon = { Icon(Icons.AutoMirrored.Outlined.Logout, null, tint = c.critInk) },
            title = { Text(s.logOut, style = MaterialTheme.typography.headlineSmall) },
            text = { Text(s.cgLogOutConfirm, style = MaterialTheme.typography.bodyLarge, color = c.ink2) },
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
