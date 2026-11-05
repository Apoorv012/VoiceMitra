package com.voicemitra.patient.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.voicemitra.patient.R

/**
 * The web app's design tokens (web/src/app/globals.css), so the phone app, the web app and the iPhone app
 * look like one product. Status colours (good / warn / serious / crit) are for state only and always travel
 * with an icon and a word.
 */
@Immutable
data class VmColors(
    val page: Color, val surface: Color, val sunken: Color,
    val ink: Color, val ink2: Color, val muted: Color,
    val line: Color, val lineStrong: Color,
    val accent: Color, val accentSoft: Color, val sage: Color,
    val btn: Color, val onBtn: Color,
    val good: Color, val goodInk: Color, val goodSoft: Color,
    val warn: Color, val warnInk: Color, val warnSoft: Color,
    val serious: Color, val seriousInk: Color, val seriousSoft: Color,
    val crit: Color, val critInk: Color, val critSoft: Color,
    val neutralSoft: Color,
    val dark: Boolean,
)

val LightColors = VmColors(
    page = Color(0xFFE9ECE7), surface = Color(0xFFFBFBF9), sunken = Color(0xFFF0F2EC),
    ink = Color(0xFF10200F), ink2 = Color(0xFF435041), muted = Color(0xFF6B7668),
    line = Color(0xFFE0E4DA), lineStrong = Color(0xFFC9CFC1),
    accent = Color(0xFF4D7A37), accentSoft = Color(0xFFE2EBD6), sage = Color(0xFFD9E3CB),
    btn = Color(0xFF12261A), onBtn = Color.White,
    good = Color(0xFF3F9163), goodInk = Color(0xFF1F6A43), goodSoft = Color(0xFFE4F3EA),
    warn = Color(0xFFD9961A), warnInk = Color(0xFF7A4D00), warnSoft = Color(0xFFFBF1DC),
    serious = Color(0xFFD9703F), seriousInk = Color(0xFF9B3A14), seriousSoft = Color(0xFFFBE9E0),
    crit = Color(0xFFC53A3A), critInk = Color(0xFFA02626), critSoft = Color(0xFFFBE8E8),
    neutralSoft = Color(0xFFEAEDE4),
    dark = false,
)

val DarkColors = VmColors(
    page = Color(0xFF0C110C), surface = Color(0xFF151B14), sunken = Color(0xFF1C231B),
    ink = Color(0xFFEEF2EA), ink2 = Color(0xFFC5CDBF), muted = Color(0xFF98A393),
    line = Color(0xFF262E25), lineStrong = Color(0xFF3A4439),
    accent = Color(0xFF8FBC72), accentSoft = Color(0xFF1F2E19), sage = Color(0xFF22301D),
    btn = Color(0xFF8FBC72), onBtn = Color(0xFF0C1A0A),
    good = Color(0xFF4CB37C), goodInk = Color(0xFF6FD09A), goodSoft = Color(0xFF14301F),
    warn = Color(0xFFE0A83A), warnInk = Color(0xFFF0B84A), warnSoft = Color(0xFF3A2D0B),
    serious = Color(0xFFE38A5E), seriousInk = Color(0xFFF4A384), seriousSoft = Color(0xFF3B2118),
    crit = Color(0xFFE06666), critInk = Color(0xFFF08A8A), critSoft = Color(0xFF3D1A1A),
    neutralSoft = Color(0xFF232A22),
    dark = true,
)

/** Plus Jakarta Sans, as on the web. Hindi falls back to the phone's own Noto Sans Devanagari (the web's Hindi font). */
@OptIn(ExperimentalTextApi::class)
private fun jakarta(weight: Int) = Font(
    R.font.plus_jakarta_sans, FontWeight(weight),
    variationSettings = FontVariation.Settings(FontVariation.weight(weight)),
)

val Jakarta = FontFamily(jakarta(400), jakarta(500), jakarta(600), jakarta(700), jakarta(800))

// The web patient app's scale (17 px body, 32 px h1, 18 px h2), one step larger for older eyes. All sp, so the
// phone's own font-size setting scales it further.
private fun style(size: Int, line: Int, weight: FontWeight = FontWeight.Normal, spacing: Double = 0.0) = TextStyle(
    fontFamily = Jakarta, fontSize = size.sp, lineHeight = line.sp, fontWeight = weight, letterSpacing = spacing.sp,
)

val VmType = Typography(
    displaySmall = style(36, 42, FontWeight.SemiBold, -0.6),     // h1 on a page
    headlineMedium = style(30, 36, FontWeight.SemiBold, -0.5),
    headlineSmall = style(24, 30, FontWeight.Bold),
    titleLarge = style(22, 28, FontWeight.SemiBold, -0.2),       // card h2
    titleMedium = style(19, 26, FontWeight.SemiBold),             // strong row text
    bodyLarge = style(19, 28),                                    // body
    bodyMedium = style(17, 25),                                   // .small
    bodySmall = style(15, 21),                                    // .tiny
    labelLarge = style(19, 24, FontWeight.SemiBold),              // buttons
    labelMedium = style(16, 20, FontWeight.SemiBold),             // chips, tabs
    labelSmall = style(13, 16, FontWeight.SemiBold, 0.9),         // .eyebrow (upper case)
)

val LocalStrings = staticCompositionLocalOf { Strings.EN }
val LocalVm = staticCompositionLocalOf { LightColors }

/** `Vm.colors` from anywhere in a composable. */
object Vm {
    val colors: VmColors
        @Composable @ReadOnlyComposable get() = LocalVm.current
}

@Composable
fun VoiceMitraTheme(strings: Strings, dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val c = if (dark) DarkColors else LightColors
    // Material components (text fields, dialogs, switches) take the same tokens.
    val scheme = (if (dark) darkColorScheme() else lightColorScheme()).copy(
        primary = c.btn, onPrimary = c.onBtn,
        secondary = c.accent, onSecondary = if (dark) c.onBtn else Color.White,
        secondaryContainer = c.accentSoft, onSecondaryContainer = c.ink,
        background = c.page, onBackground = c.ink,
        surface = c.surface, onSurface = c.ink, surfaceContainerHigh = c.surface, surfaceContainer = c.surface,
        surfaceVariant = c.sunken, onSurfaceVariant = c.ink2,
        outline = c.lineStrong, outlineVariant = c.line,
        error = c.critInk, onError = Color.White, errorContainer = c.critSoft, onErrorContainer = c.critInk,
    )
    MaterialTheme(colorScheme = scheme, typography = VmType) {
        CompositionLocalProvider(LocalStrings provides strings, LocalVm provides c, content = content)
    }
}
