package com.voicemitra.patient.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Check
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.Shield
import androidx.compose.material.icons.outlined.WarningAmber
import androidx.compose.material.icons.outlined.WifiOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.voicemitra.patient.data.ApiException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import java.io.IOException

// The web app's building blocks (web/src/app/globals.css, web/src/components/ui.tsx), sized up for older
// hands: every main action is at least 56 dp tall.

// --- text ------------------------------------------------------------------------------------

@Composable
fun H1(text: String, modifier: Modifier = Modifier) = Text(
    text, color = Vm.colors.ink, modifier = modifier.semantics { heading() },
    // The web's tight heading spacing suits Latin letters; Devanagari is left at its natural spacing.
    style = MaterialTheme.typography.displaySmall.let {
        if (LocalStrings.current.lang == com.voicemitra.patient.data.Lang.HI) it.copy(letterSpacing = 0.sp) else it
    },
)

@Composable
fun H2(text: String, modifier: Modifier = Modifier) =
    Text(text, style = MaterialTheme.typography.titleLarge, color = Vm.colors.ink, modifier = modifier.semantics { heading() })

/** The small upper-case label above a heading ("GOOD MORNING · WEDNESDAY, 5 NOVEMBER"). */
@Composable
fun Eyebrow(text: String, color: Color = Vm.colors.muted, modifier: Modifier = Modifier) =
    Text(text.uppercase(), style = MaterialTheme.typography.labelSmall, color = color, modifier = modifier)

@Composable
fun Muted(text: String, modifier: Modifier = Modifier, small: Boolean = true) = Text(
    text, color = Vm.colors.muted, modifier = modifier,
    style = if (small) MaterialTheme.typography.bodyMedium else MaterialTheme.typography.bodyLarge,
)

// --- containers ------------------------------------------------------------------------------

/** `.card`: surface, hairline border, 24 dp corners. */
@Composable
fun VmCard(
    modifier: Modifier = Modifier,
    color: Color = Vm.colors.surface,
    border: Color? = Vm.colors.line,
    padding: Dp = 22.dp,
    spacing: Dp = 12.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = RoundedCornerShape(24.dp)
    Column(
        modifier.fillMaxWidth()
            .background(color, shape)
            .then(if (border != null) Modifier.border(1.dp, border, shape) else Modifier)
            .padding(padding),
        verticalArrangement = Arrangement.spacedBy(spacing),
        content = content,
    )
}

enum class Tone { Neutral, Accent, Good, Warn, Serious, Crit }

@Composable
private fun toneColors(tone: Tone): Pair<Color, Color> {
    val c = Vm.colors
    return when (tone) {
        Tone.Neutral -> c.neutralSoft to c.ink2
        Tone.Accent -> c.accentSoft to c.accent
        Tone.Good -> c.goodSoft to c.goodInk
        Tone.Warn -> c.warnSoft to c.warnInk
        Tone.Serious -> c.seriousSoft to c.seriousInk
        Tone.Crit -> c.critSoft to c.critInk
    }
}

/** `.callout`: a tinted note with an icon. */
@Composable
fun Callout(icon: ImageVector, tone: Tone? = null, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val (bg, fg) = if (tone == null) Vm.colors.sunken to Vm.colors.ink else toneColors(tone)
    Row(
        modifier.fillMaxWidth().background(bg, RoundedCornerShape(16.dp)).padding(horizontal = 18.dp, vertical = 16.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(icon, null, tint = fg, modifier = Modifier.size(28.dp))
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            androidx.compose.runtime.CompositionLocalProvider(
                androidx.compose.material3.LocalContentColor provides fg,
            ) { content() }
        }
    }
}

// --- buttons ---------------------------------------------------------------------------------

enum class BtnKind { Primary, Good, Danger, DangerSoft, Secondary, Ghost }

/** `.btn`: a pill. Main actions are `xl` (60 dp); secondary ones 56 dp. */
@Composable
fun VmButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    kind: BtnKind = BtnKind.Primary,
    icon: ImageVector? = null,
    enabled: Boolean = true,
    busy: Boolean = false,
    xl: Boolean = true,
) {
    val c = Vm.colors
    val (bg, fg) = when (kind) {
        BtnKind.Primary -> c.btn to c.onBtn
        BtnKind.Good -> c.good to Color.White
        BtnKind.Danger -> c.crit to Color.White
        BtnKind.DangerSoft -> c.critSoft to c.critInk
        BtnKind.Secondary -> c.surface to c.ink
        BtnKind.Ghost -> Color.Transparent to c.ink2
    }
    Button(
        onClick = onClick,
        enabled = enabled && !busy,
        modifier = modifier.fillMaxWidth().heightIn(min = if (xl) 60.dp else 56.dp),
        shape = CircleShape,
        border = if (kind == BtnKind.Secondary) BorderStroke(1.5.dp, c.lineStrong) else null,
        contentPadding = PaddingValues(horizontal = 24.dp, vertical = 10.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = bg, contentColor = fg,
            disabledContainerColor = bg.copy(alpha = if (bg == Color.Transparent) 0f else 0.55f),
            disabledContentColor = fg.copy(alpha = 0.7f),
        ),
        elevation = null,
    ) {
        if (busy) {
            CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 3.dp, color = fg)
            Spacer(Modifier.width(12.dp))
        } else if (icon != null) {
            Icon(icon, null, Modifier.size(24.dp))
            Spacer(Modifier.width(10.dp))
        }
        Text(text, style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
    }
}

// --- chips and dots --------------------------------------------------------------------------

/** `.chip`: colour + icon + word (colour never carries the meaning alone). */
@Composable
fun Chip(text: String, icon: ImageVector?, tone: Tone, large: Boolean = false) {
    val (bg, fg) = toneColors(tone)
    Row(
        Modifier.background(bg, CircleShape)
            .padding(start = if (large) 12.dp else 10.dp, end = if (large) 16.dp else 13.dp, top = if (large) 8.dp else 5.dp,
                bottom = if (large) 8.dp else 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = fg, modifier = Modifier.size(if (large) 20.dp else 17.dp))
            Spacer(Modifier.width(5.dp))
        }
        Text(text, color = fg, style = MaterialTheme.typography.labelMedium, maxLines = 1)
    }
}

/** A dose's state, as on every web screen (web/src/components/ui.tsx SLOT). */
@Composable
fun SlotChip(state: String, large: Boolean = false) {
    val s = LocalStrings.current
    val (tone, icon, label) = when (state) {
        "taken" -> Triple(Tone.Good, Icons.Outlined.Check, s.doseTaken)
        "partial" -> Triple(Tone.Warn, Icons.Outlined.WarningAmber, s.dosePartial)
        "missed" -> Triple(Tone.Crit, Icons.Outlined.Close, s.doseMissed)
        "later" -> Triple(Tone.Accent, Icons.Outlined.Schedule, s.doseLater)
        "unknown" -> Triple(Tone.Neutral, Icons.Outlined.HelpOutline, s.doseUnknown)
        "skipped" -> Triple(Tone.Neutral, Icons.Outlined.Shield, s.doseSkipped)
        "upcoming" -> Triple(Tone.Neutral, Icons.Outlined.Schedule, s.doseUpcoming)
        "due" -> Triple(Tone.Warn, Icons.Outlined.Schedule, s.doseDue)
        else -> Triple(Tone.Neutral, Icons.Outlined.HelpOutline, s.doseNoCheckin)
    }
    Chip(label, icon, tone, large)
}

/** The round marker for a whole day in the week strip (`.dot`). */
@Composable
fun DayDot(state: String, size: Dp = 40.dp, ring: Boolean = false) {
    val c = Vm.colors
    val (bg, fg, icon) = when (state) {
        "good" -> Triple(c.goodSoft, c.goodInk, Icons.Outlined.Check)
        "mixed" -> Triple(c.warnSoft, c.warnInk, Icons.Outlined.WarningAmber)
        "missed" -> Triple(c.critSoft, c.critInk, Icons.Outlined.Close)
        "unknown" -> Triple(c.neutralSoft, c.muted, Icons.Outlined.HelpOutline)
        else -> Triple(Color.Transparent, c.muted, null)
    }
    Box(
        Modifier.size(size + if (ring) 8.dp else 0.dp)
            .then(if (ring) Modifier.border(2.dp, c.accent, CircleShape).padding(4.dp) else Modifier)
            .background(bg, CircleShape)
            .then(if (icon == null) Modifier.border(1.5.dp, c.lineStrong, CircleShape) else Modifier),
        contentAlignment = Alignment.Center,
    ) {
        if (icon != null) Icon(icon, null, tint = fg, modifier = Modifier.size(size * 0.5f))
    }
}

/** `.avatar`: initials (or an icon) in a circle. */
@Composable
fun Avatar(text: String?, icon: ImageVector? = null, size: Dp = 64.dp, bg: Color = Vm.colors.neutralSoft, fg: Color = Vm.colors.ink2) {
    Box(Modifier.size(size).background(bg, CircleShape), contentAlignment = Alignment.Center) {
        if (icon != null) Icon(icon, null, tint = fg, modifier = Modifier.size(size * 0.48f))
        else Text(text ?: "", color = fg, style = MaterialTheme.typography.titleLarge)
    }
}

// --- states ----------------------------------------------------------------------------------

@Composable
fun LoadingState() {
    val s = LocalStrings.current
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp).semantics { liveRegion = LiveRegionMode.Polite },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        CircularProgressIndicator(color = Vm.colors.accent)
        Muted(s.loading, small = false)
    }
}

/** A plain-words problem, read out by TalkBack when it appears, with a retry. No internet gets its own icon. */
@Composable
fun ErrorState(message: String, onRetry: (() -> Unit)?, offline: Boolean = false) {
    val s = LocalStrings.current
    VmCard(Modifier.semantics { liveRegion = LiveRegionMode.Assertive }) {
        Row(verticalAlignment = Alignment.Top) {
            Icon(if (offline) Icons.Outlined.WifiOff else Icons.Outlined.ErrorOutline, null, tint = Vm.colors.critInk,
                modifier = Modifier.size(28.dp))
            Spacer(Modifier.width(12.dp))
            Text(message, color = Vm.colors.ink, style = MaterialTheme.typography.bodyLarge)
        }
        if (onRetry != null) VmButton(s.retry, onRetry, kind = BtnKind.Secondary, xl = false)
    }
}

@Composable
fun EmptyState(icon: ImageVector, text: String) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 28.dp, horizontal = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Icon(icon, null, tint = Vm.colors.muted, modifier = Modifier.size(40.dp))
        Text(text, color = Vm.colors.muted, style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center)
    }
}

/** What to tell the patient for a failed request. */
fun Strings.explain(e: Throwable, on401: String? = null, on400: String? = null): String = when {
    e is ApiException && e.code == 401 && on401 != null -> on401
    // Right password, but a login for the website (backend/routers/auth.py): say where to use it.
    e is ApiException && e.code == 403 && e.message == "family_login" -> familyLogin
    e is ApiException && e.code == 403 && e.message == "staff_login" -> staffLogin
    e is ApiException && e.code == 400 && on400 != null -> on400
    e is ApiException && e.code == 429 -> tooManyTries
    e is ApiException && e.code >= 500 -> serverError
    e is IOException -> netError
    else -> loadError
}

fun Throwable.isOffline() = this is IOException

// --- loading data ----------------------------------------------------------------------------

class Loaded<T>(val data: T?, val error: Throwable?, val retry: () -> Unit)

/**
 * Load `fetch()` while the screen is showing: on first show, every time it comes back to the front
 * (e.g. after a call) and every `refreshMs`. Keeps the last good data while a refresh fails.
 */
@Composable
fun <T> rememberLoaded(key: Any?, refreshMs: Long = 60_000, fetch: suspend () -> T): Loaded<T> {
    var data by remember(key) { mutableStateOf<T?>(null) }
    var error by remember(key) { mutableStateOf<Throwable?>(null) }
    var attempt by remember(key) { mutableIntStateOf(0) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(key, attempt) {
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            while (true) {
                try {
                    data = fetch()
                    error = null
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    error = e
                }
                delay(refreshMs)
            }
        }
    }
    return Loaded(data, error) { error = null; attempt++ }
}

/** The standard frame for a loaded screen: loading -> error (with retry) -> content (+ a note if a refresh failed). */
@Composable
fun <T> LoadedContent(loaded: Loaded<T>, content: @Composable (T) -> Unit) {
    val s = LocalStrings.current
    val data = loaded.data
    val error = loaded.error
    when {
        data != null -> {
            content(data)
            if (error != null) ErrorState(s.explain(error), loaded.retry, offline = error.isOffline())
        }
        error != null -> ErrorState(s.explain(error), loaded.retry, offline = error.isOffline())
        else -> LoadingState()
    }
}

/** A tab's scrolling page: the web's `.p-main` (16 dp sides, 16 dp between sections). */
@Composable
fun TabPage(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 28.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        content = content,
    )
}

/** An icon in a soft round badge (the iPhone/web list rows). */
@Composable
fun IconCircle(icon: ImageVector, size: Dp = 52.dp, bg: Color = Vm.colors.accentSoft, fg: Color = Vm.colors.accent) {
    Box(Modifier.size(size).background(bg, CircleShape), contentAlignment = Alignment.Center) {
        Icon(icon, null, tint = fg, modifier = Modifier.size(size * 0.5f))
    }
}

/** A card with a round icon, a title and a line under it; tappable when `onClick` is given. */
@Composable
fun IconCard(
    icon: ImageVector,
    title: String,
    body: String,
    tone: Tone? = null,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    val c = Vm.colors
    val (bg, fg) = when (tone) {
        Tone.Warn -> c.warnSoft to c.warnInk
        Tone.Accent -> c.accentSoft to c.accent
        else -> c.surface to c.accent
    }
    val shape = RoundedCornerShape(24.dp)
    Row(
        Modifier.fillMaxWidth().background(bg, shape)
            .then(if (tone == null) Modifier.border(1.dp, c.line, shape) else Modifier)
            .then(if (onClick != null) Modifier.clickable(role = androidx.compose.ui.semantics.Role.Button, onClick = onClick) else Modifier)
            .padding(20.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconCircle(icon, bg = if (tone == null) c.accentSoft else c.page.copy(alpha = if (c.dark) 0.6f else 0.7f), fg = fg)
        Spacer(Modifier.width(16.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = if (tone == Tone.Warn) c.warnInk else c.ink)
            Text(body, style = MaterialTheme.typography.bodyLarge, color = if (tone == Tone.Warn) c.warnInk else c.ink2)
        }
        if (trailing != null) {
            Spacer(Modifier.width(8.dp))
            trailing()
        }
    }
}

