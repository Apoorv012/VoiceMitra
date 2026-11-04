package com.voicemitra.patient.call

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import androidx.core.app.NotificationCompat
import androidx.core.app.Person
import androidx.core.content.getSystemService
import com.voicemitra.patient.App
import com.voicemitra.patient.R
import com.voicemitra.patient.ui.Strings

/**
 * The two call notifications. Ringing: a CallStyle notification with a full-screen intent (the call
 * screen over the lock screen), the phone's ringtone on loop and vibration, gone after [RING_MS].
 * Ongoing: the foreground-service notification while a call is connected.
 */
object Notifications {
    // Channel settings can't be changed once created: a new id is needed to change sound/importance.
    const val CHANNEL_RING = "ring_v1"
    const val CHANNEL_ONGOING = "ongoing_v1"
    const val ID_RING = 1
    const val ID_ONGOING = 2
    const val RING_MS = 60_000L

    private fun strings(): Strings = Strings.of(App.instance.settings.value.lang)

    fun createChannels(context: Context) {
        val nm = context.getSystemService<NotificationManager>() ?: return
        val s = strings()
        val ring = NotificationChannel(CHANNEL_RING, s.channelCalls, NotificationManager.IMPORTANCE_HIGH).apply {
            setSound(
                RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE),
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build(),
            )
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 1000, 1000)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
            setBypassDnd(false)
        }
        val ongoing = NotificationChannel(CHANNEL_ONGOING, s.channelOngoing, NotificationManager.IMPORTANCE_LOW).apply {
            setSound(null, null)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannels(listOf(ring, ongoing))
    }

    private fun caller(context: Context): Person =
        Person.Builder().setName("VoiceMitra").setImportant(true).build()

    fun showIncoming(context: Context, callId: String) {
        val s = strings()
        val full = PendingIntent.getActivity(
            context, 10, CallActivity.intent(context, CallActivity.ACTION_SHOW, callId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val answer = PendingIntent.getActivity(
            context, 11, CallActivity.intent(context, CallActivity.ACTION_ANSWER, callId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val decline = CallActionReceiver.pending(context, CallActionReceiver.ACTION_DECLINE, callId)
        val n = NotificationCompat.Builder(context, CHANNEL_RING)
            .setSmallIcon(R.drawable.ic_call)
            .setContentTitle(s.incomingTitle)
            .setContentText(s.incomingSub)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)
            .setAutoCancel(false)
            .setTimeoutAfter(RING_MS)
            .setFullScreenIntent(full, true)
            .setContentIntent(full)
            .setStyle(NotificationCompat.CallStyle.forIncomingCall(caller(context), decline, answer))
            .build()
        n.flags = n.flags or Notification.FLAG_INSISTENT  // ring until answered, declined or timed out
        context.getSystemService<NotificationManager>()?.notify(ID_RING, n)
    }

    fun cancelIncoming(context: Context) {
        context.getSystemService<NotificationManager>()?.cancel(ID_RING)
    }

    fun ongoing(context: Context): Notification {
        val s = strings()
        val open = PendingIntent.getActivity(
            context, 12, CallActivity.intent(context, CallActivity.ACTION_SHOW, null),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val hangUp = CallActionReceiver.pending(context, CallActionReceiver.ACTION_HANG_UP, null)
        return NotificationCompat.Builder(context, CHANNEL_ONGOING)
            .setSmallIcon(R.drawable.ic_call)
            .setContentTitle(s.ongoingTitle)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setOngoing(true)
            .setUsesChronometer(true)
            .setContentIntent(open)
            .setStyle(NotificationCompat.CallStyle.forOngoingCall(caller(context), hangUp))
            .build()
    }

    fun openAppIntent(context: Context): Intent =
        context.packageManager.getLaunchIntentForPackage(context.packageName) ?: Intent()
}
