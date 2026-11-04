package com.voicemitra.patient.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// The web app's palette (web/src/app/globals.css): green brand, near-black ink, warm off-white page.
private val Light = lightColorScheme(
    primary = Color(0xFF12261A), onPrimary = Color.White,
    secondary = Color(0xFF4D7A37), onSecondary = Color.White,
    secondaryContainer = Color(0xFFE2EBD6), onSecondaryContainer = Color(0xFF1F3A12),
    background = Color(0xFFE9ECE7), onBackground = Color(0xFF10200F),
    surface = Color(0xFFFBFBF9), onSurface = Color(0xFF10200F),
    surfaceVariant = Color(0xFFF0F2EC), onSurfaceVariant = Color(0xFF435041),
    outline = Color(0xFFC9CFC1),
    error = Color(0xFFA02626), onError = Color.White,
    errorContainer = Color(0xFFFBE8E8), onErrorContainer = Color(0xFFA02626),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF8FBC72), onPrimary = Color(0xFF0C1A0A),
    secondary = Color(0xFF8FBC72), onSecondary = Color(0xFF0C1A0A),
    secondaryContainer = Color(0xFF1F2E19), onSecondaryContainer = Color(0xFFD9E8CC),
    background = Color(0xFF0C110C), onBackground = Color(0xFFEEF2EA),
    surface = Color(0xFF151B14), onSurface = Color(0xFFEEF2EA),
    surfaceVariant = Color(0xFF1C231B), onSurfaceVariant = Color(0xFFC5CDBF),
    outline = Color(0xFF3A4439),
    error = Color(0xFFFF8A80), onError = Color(0xFF3A0000),
    errorContainer = Color(0xFF3A1414), onErrorContainer = Color(0xFFFFB4AB),
)

/** Status colours: always shown with a word too, never colour alone. */
object StatusColors {
    val good = Color(0xFF1F6A43)
    val goodSoft = Color(0xFFE4F3EA)
    val warn = Color(0xFF7A4D00)
    val warnSoft = Color(0xFFFBF1DC)
    val crit = Color(0xFFA02626)
    val critSoft = Color(0xFFFBE8E8)
    val answer = Color(0xFF2E7D32)
    val hangUp = Color(0xFFC62828)
}

// Bigger than Material's defaults (elderly readers). All in sp, so the phone's own font-size setting
// still scales them.
private val Big = Typography(
    displaySmall = TextStyle(fontSize = 40.sp, lineHeight = 48.sp, fontWeight = FontWeight.Bold),
    headlineMedium = TextStyle(fontSize = 30.sp, lineHeight = 38.sp, fontWeight = FontWeight.Bold),
    headlineSmall = TextStyle(fontSize = 26.sp, lineHeight = 34.sp, fontWeight = FontWeight.SemiBold),
    titleLarge = TextStyle(fontSize = 24.sp, lineHeight = 32.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 21.sp, lineHeight = 28.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 20.sp, lineHeight = 28.sp),
    bodyMedium = TextStyle(fontSize = 18.sp, lineHeight = 26.sp),
    bodySmall = TextStyle(fontSize = 16.sp, lineHeight = 22.sp),
    labelLarge = TextStyle(fontSize = 21.sp, lineHeight = 26.sp, fontWeight = FontWeight.SemiBold),
    labelMedium = TextStyle(fontSize = 17.sp, lineHeight = 22.sp, fontWeight = FontWeight.Medium),
)

val LocalStrings = staticCompositionLocalOf { Strings.EN }

@Composable
fun VoiceMitraTheme(strings: Strings, content: @Composable () -> Unit) {
    val scheme: ColorScheme = if (isSystemInDarkTheme()) Dark else Light
    MaterialTheme(colorScheme = scheme, typography = Big) {
        CompositionLocalProvider(LocalStrings provides strings, content = content)
    }
}
