package com.voicemitra.patient.ui

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.CheckCircle
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.core.content.getSystemService
import androidx.core.net.toUri
import androidx.annotation.RequiresApi
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle

/** One thing the phone must allow for VoiceMitra to ring it when locked. */
enum class SetupItem { Notifications, FullScreen, Mic, Battery, Autostart }

object Setup {
    /** Phones whose makers add their own "auto-start" switch that stops background push. */
    private val autostartMakers = setOf("xiaomi", "redmi", "poco", "oppo", "realme", "vivo", "iqoo", "oneplus", "huawei", "honor")

    fun hasAutostartSetting() = Build.MANUFACTURER.lowercase() in autostartMakers

    fun isDone(context: Context, item: SetupItem): Boolean = when (item) {
        SetupItem.Notifications -> NotificationManagerCompat.from(context).areNotificationsEnabled()
        SetupItem.FullScreen -> Build.VERSION.SDK_INT < 34 ||
            context.getSystemService<NotificationManager>()?.canUseFullScreenIntent() == true
        SetupItem.Mic -> ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        SetupItem.Battery -> context.getSystemService<PowerManager>()?.isIgnoringBatteryOptimizations(context.packageName) == true
        // Can't be read back: counts as done once the patient has been to that page.
        SetupItem.Autostart -> !hasAutostartSetting() || context.getSharedPreferences("setup", 0).getBoolean("autostart_seen", false)
    }

    fun items(): List<SetupItem> = SetupItem.entries.filter { it != SetupItem.Autostart || hasAutostartSetting() }

    fun allDone(context: Context) = items().all { isDone(context, it) }

    @SuppressLint("BatteryLife")  // a calling app that must ring when idle is the allowed use
    fun batteryIntent(context: Context) =
        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, "package:${context.packageName}".toUri())

    @RequiresApi(34)
    fun fullScreenIntent(context: Context) =
        Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, "package:${context.packageName}".toUri())

    fun notificationSettings(context: Context) =
        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)

    fun appDetails(context: Context) =
        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, "package:${context.packageName}".toUri())

    /** The makers' own auto-start pages (they move between versions: try each, then the app's settings). */
    fun autostartIntents(context: Context): List<Intent> = listOf(
        ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
        ComponentName("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity"),
        ComponentName("com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity"),
        ComponentName("com.oplus.safecenter", "com.oplus.safecenter.permission.startup.StartupAppListActivity"),
        ComponentName("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity"),
        ComponentName("com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.BgStartUpManager"),
        ComponentName("com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"),
    ).map { Intent().setComponent(it) } + appDetails(context)

    fun open(context: Context, intents: List<Intent>) {
        for (i in intents) {
            try {
                context.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                return
            } catch (_: Exception) {
                // not on this phone: try the next
            }
        }
    }
}

/**
 * First-run checklist (and re-checked on every launch): without these a locked phone may not ring.
 * Each row shows a green tick when done; tapping a row asks for it or opens the right settings page.
 */
@Composable
fun SetupScreen(onDone: () -> Unit) {
    val s = LocalStrings.current
    val context = LocalContext.current
    var tick by remember { mutableIntStateOf(0) }  // re-read the states when we come back from Settings
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(Unit) { lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) { tick++ } }

    val askNotifications = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) Setup.open(context, listOf(Setup.notificationSettings(context)))
        tick++
    }
    val askMic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) Setup.open(context, listOf(Setup.appDetails(context)))
        tick++
    }
    var askedOnce by remember { mutableStateOf(setOf<SetupItem>()) }

    fun fix(item: SetupItem) {
        val first = item !in askedOnce
        askedOnce = askedOnce + item
        when (item) {
            SetupItem.Notifications ->
                if (Build.VERSION.SDK_INT >= 33 && first) askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
                else Setup.open(context, listOf(Setup.notificationSettings(context)))
            SetupItem.FullScreen -> Setup.open(
                context,
                if (Build.VERSION.SDK_INT >= 34) listOf(Setup.fullScreenIntent(context), Setup.appDetails(context))
                else listOf(Setup.appDetails(context)),
            )
            SetupItem.Mic -> if (first) askMic.launch(Manifest.permission.RECORD_AUDIO) else Setup.open(context, listOf(Setup.appDetails(context)))
            SetupItem.Battery -> Setup.open(context, listOf(Setup.batteryIntent(context), Setup.appDetails(context)))
            SetupItem.Autostart -> {
                context.getSharedPreferences("setup", 0).edit { putBoolean("autostart_seen", true) }
                Setup.open(context, Setup.autostartIntents(context))
            }
        }
    }

    val items = remember { Setup.items() }
    val done = remember(tick) { items.associateWith { Setup.isDone(context, it) } }

    val firstToDo = items.firstOrNull { done[it] != true }
    TabPage {
        H1(s.setupTitle)
        Text(s.setupSub, style = MaterialTheme.typography.bodyLarge, color = Vm.colors.ink2)
        items.forEach { item ->
            val (title, why) = when (item) {
                SetupItem.Notifications -> s.permNotifications to s.permNotificationsWhy
                SetupItem.FullScreen -> s.permFullScreen to s.permFullScreenWhy
                SetupItem.Mic -> s.permMic to s.permMicWhy
                SetupItem.Battery -> s.permBattery to s.permBatteryWhy
                SetupItem.Autostart -> s.permAutostart to s.permAutostartWhy
            }
            val ok = done[item] == true
            VmCard(spacing = 14.dp) {
                Row(verticalAlignment = Alignment.Top) {
                    Tick(ok)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(title, style = MaterialTheme.typography.titleMedium, color = Vm.colors.ink)
                        Text(why, style = MaterialTheme.typography.bodyMedium, color = Vm.colors.ink2)
                    }
                }
                // One clear next step: the first unticked item gets the dark button, the rest outlined.
                if (!ok) VmButton(
                    if (item == SetupItem.Notifications || item == SetupItem.Mic) s.allow else s.openSettings,
                    { fix(item) },
                    kind = if (item == firstToDo) BtnKind.Primary else BtnKind.Secondary,
                    xl = false,
                )
            }
        }
        if (firstToDo == null) {
            Callout(Icons.Outlined.CheckCircle, Tone.Good) { Text(s.setupDone, style = MaterialTheme.typography.titleMedium) }
            VmButton(s.continueBtn, onDone)
        } else {
            VmButton(s.skipForNow, onDone, kind = BtnKind.Ghost, xl = false)
        }
    }
}

/** A green tick when done, an empty ring when not (with the word, for TalkBack). */
@Composable
private fun Tick(ok: Boolean) {
    val c = Vm.colors
    Box(
        Modifier.size(40.dp)
            .background(if (ok) c.goodSoft else Color.Transparent, CircleShape)
            .then(if (ok) Modifier else Modifier.border(2.dp, c.lineStrong, CircleShape))
            .semantics { stateDescription = if (ok) "✓" else "✗" },
        contentAlignment = Alignment.Center,
    ) {
        if (ok) Icon(Icons.Outlined.Check, null, tint = c.goodInk, modifier = Modifier.size(24.dp))
    }
}
