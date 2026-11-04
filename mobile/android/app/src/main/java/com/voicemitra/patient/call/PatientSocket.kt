package com.voicemitra.patient.call

import android.util.Log
import com.voicemitra.patient.App
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * The patient's live-event socket (mobile/API.md "Live events"), held while the app is on screen or a
 * call is on. It rings from `voice_call` (the same path as a push, so a ring is never shown twice),
 * stops ringing on `voice_call_ended`, and feeds the call's transcript from `log_entry`.
 */
class PatientSocket(private val app: App) {
    private var socket: WebSocket? = null
    private var patientId: String? = null
    private var retry: Job? = null
    private var wanted = false
    private var backoffMs = 1_000L
    private val json = Json { ignoreUnknownKeys = true }

    /** Main thread only. */
    fun start(patientId: String) {
        if (wanted && this.patientId == patientId && socket != null) return
        stop()
        wanted = true
        this.patientId = patientId
        open()
    }

    /** Main thread only. */
    fun stop() {
        wanted = false
        retry?.cancel()
        socket?.close(1000, null)
        socket = null
    }

    private fun open() {
        val id = patientId ?: return
        val request = Request.Builder().url(app.api.socketUrl(id)).build()
        socket = app.api.http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                backoffMs = 1_000L
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                val event = try {
                    json.parseToJsonElement(text).jsonObject
                } catch (_: Exception) {
                    return
                }
                app.scope.launch { handle(event) }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = reconnect(webSocket)

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.i("PatientSocket", "socket dropped: ${t.message}")
                reconnect(webSocket)
            }
        })
    }

    private fun reconnect(dead: WebSocket) {
        app.scope.launch {
            if (!wanted || socket !== dead) return@launch
            socket = null
            retry = app.scope.launch {
                delay(backoffMs)
                backoffMs = (backoffMs * 2).coerceAtMost(30_000L)
                if (wanted && socket == null) open()
            }
        }
    }

    private fun handle(e: JsonObject) {
        val calls = app.calls
        fun str(o: JsonObject?, k: String) = o?.get(k)?.jsonPrimitive?.contentOrNull
        when (str(e, "type")) {
            // A call already waiting when the app opened: ring for it (unless it was declined).
            "snapshot" -> str(e["voice"] as? JsonObject, "call_id")?.let { calls.onRing(it) }
            "voice_call" -> str(e, "call_id")?.let { calls.onRing(it) }
            "voice_call_ended" -> calls.onRemoteEnded(str(e, "call_id"))
            "log_entry" -> {
                val entry = e["entry"] as? JsonObject
                // channel null = the patient's own conversation with the agent
                if (entry != null && entry["channel"]?.jsonPrimitive?.contentOrNull == null) {
                    calls.onLogEntry(str(e, "call_id"), str(entry, "type") ?: "", str(entry, "content"))
                }
            }
        }
    }
}
