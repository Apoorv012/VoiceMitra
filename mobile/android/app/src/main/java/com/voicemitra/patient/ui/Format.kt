package com.voicemitra.patient.ui

import androidx.compose.runtime.staticCompositionLocalOf
import com.voicemitra.patient.data.Lang
import java.time.Duration
import java.time.LocalDate
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.time.format.TextStyle
import java.util.Locale

// Dates and times arrive as ISO strings; "today" and dose times are the server's, in the patient's
// `timezone` (as on the web: web/src/lib/format.ts). Everything is shown in that zone, not the phone's.

/** The current moment. Screenshots fix it, so pictures don't change with the clock. */
val LocalNow = staticCompositionLocalOf<() -> ZonedDateTime> { { ZonedDateTime.now() } }

fun zoneOf(tz: String): ZoneId = try {
    ZoneId.of(tz)
} catch (_: Exception) {
    ZoneId.of("Asia/Kolkata")
}

private fun locale(lang: Lang) = if (lang == Lang.HI) Locale.forLanguageTag("hi-IN") else Locale.forLanguageTag("en-IN")

private fun parse(iso: String, tz: String): ZonedDateTime? = try {
    OffsetDateTime.parse(iso).atZoneSameInstant(zoneOf(tz))
} catch (_: Exception) {
    null
}

/** "9:00 PM" (digits and AM/PM as on the web, in both languages). */
fun timeOf(iso: String, tz: String): String =
    parse(iso, tz)?.format(DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH))?.uppercase() ?: ""

/** Kept for older call sites: the same as [timeOf]. */
@Suppress("UNUSED_PARAMETER")
fun clock(iso: String, zone: String, lang: Lang): String = timeOf(iso, zone)

/** "21:00" -> "9:00 PM" (a stored dose time, no date or zone). */
fun clockLabel(hhmm: String): String = try {
    LocalTime.parse(hhmm.take(5)).format(DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)).uppercase()
} catch (_: Exception) {
    hhmm
}

/** "Today", "Yesterday", or "Tue, 14 Oct". */
fun dayLabel(iso: String, tz: String, s: Strings, now: ZonedDateTime): String {
    val d = parse(iso, tz) ?: return ""
    val today = now.withZoneSameInstant(zoneOf(tz)).toLocalDate()
    return when (d.toLocalDate()) {
        today -> s.today
        today.minusDays(1) -> s.yesterday
        else -> d.format(DateTimeFormatter.ofPattern("EEE, d MMM", locale(s.lang)))
    }
}

/** "Today, 9:41 AM" */
fun whenLabel(iso: String, tz: String, s: Strings, now: ZonedDateTime) = "${dayLabel(iso, tz, s, now)}, ${timeOf(iso, tz)}"

/** "Wednesday, 5 November" for today. */
fun fullDateToday(tz: String, lang: Lang, now: ZonedDateTime): String =
    now.withZoneSameInstant(zoneOf(tz)).format(DateTimeFormatter.ofPattern("EEEE, d MMMM", locale(lang)))

/** "14 Oct" for a plain "YYYY-MM-DD" date. */
fun dayOfDate(date: String, lang: Lang): String = try {
    LocalDate.parse(date).format(DateTimeFormatter.ofPattern("d MMM", locale(lang)))
} catch (_: Exception) {
    date
}

/** Short weekday of a plain date: "Tue" / "मंगल". */
fun weekdayOf(date: String, lang: Lang): String = try {
    LocalDate.parse(date).dayOfWeek.getDisplayName(TextStyle.SHORT, locale(lang))
} catch (_: Exception) {
    ""
}

fun isToday(date: String, tz: String, now: ZonedDateTime): Boolean =
    date == now.withZoneSameInstant(zoneOf(tz)).toLocalDate().toString()

/** "in 35 min", "in 2 h", "now" */
fun inWords(iso: String, s: Strings, now: ZonedDateTime): String {
    val at = parse(iso, "UTC") ?: return ""
    val seconds = Duration.between(now.toInstant(), at.toInstant()).seconds
    return when {
        seconds <= 60 -> s.now
        seconds < 3600 -> s.fill(s.inMin, "n" to seconds / 60)
        else -> s.fill(s.inHours, "n" to Math.round(seconds / 3600.0))
    }
}

/** Good morning / afternoon / evening (late night counts as the evening that never ended). */
fun greetingOf(tz: String, s: Strings, now: ZonedDateTime): String {
    val hour = now.withZoneSameInstant(zoneOf(tz)).hour
    return when (hour) {
        in 4..11 -> s.goodMorning
        in 12..16 -> s.goodAfternoon
        else -> s.goodEvening
    }
}

fun initials(name: String): String =
    name.replace(".", " ").split(Regex("\\s+")).filter { it.isNotBlank() && !it.lowercase().matches(Regex("dr|mr|mrs|ms")) }
        .take(2).joinToString("") { it.first().uppercase() }.ifEmpty { "?" }
