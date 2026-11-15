package com.voicemitra.patient.caregiver

import android.util.Log
import com.voicemitra.patient.data.Api
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * The caregiver socket (`/ws/caregivers/{id}`, mobile/API.md "Caregivers in the apps"), open while it is
 * collected (the caregiver home, while on screen). Emits once per message -- `snapshot`, `alert`,
 * `alerts_seen`, `call_started`, `call_ended` all just mean "refetch the home" -- and once more whenever the
 * socket closes, so a refused socket (1008: the phone was signed out, e.g. the family contact was removed;
 * 4404: the caregiver is gone) turns into a refetch, whose 401/404 signs the phone out. Reconnects with
 * backoff (1 s doubling to 30 s) while still collected. The `X-Device-Token` is added by [Api.http].
 */
fun caregiverEvents(api: Api, caregiverId: String): Flow<Unit> = channelFlow {
    var backoffMs = 1_000L
    while (true) {
        val closed = CompletableDeferred<Unit>()
        val socket = api.http.newWebSocket(
            Request.Builder().url(api.caregiverSocketUrl(caregiverId)).build(),
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    backoffMs = 1_000L
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    trySend(Unit)
                }

                override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                    if (code == 1008 || code == 4404) Log.i("CaregiverEvents", "socket refused ($code): checking sign-in")
                    webSocket.close(1000, null)
                    closed.complete(Unit)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    closed.complete(Unit)
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    Log.i("CaregiverEvents", "socket dropped: ${t.message}")
                    closed.complete(Unit)
                }
            },
        )
        try {
            closed.await()
        } finally {
            socket.cancel()
        }
        trySend(Unit)  // refetch: picks up anything missed, and notices a sign-out
        delay(backoffMs)
        backoffMs = (backoffMs * 2).coerceAtMost(30_000L)
    }
}
