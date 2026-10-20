// The messages the backend pushes over its WebSockets (backend/routers/live.py, escalations.py). These
// are not part of the OpenAPI schema, so their shapes are written down here once instead of being
// guessed at each use.

export type EscalationState = { status: string; doctor_name?: string | null };

export type ChatMessage = { index: number; role: string; text: string };

export type LogEntry = {
  type: string;
  channel?: string | null;
  content?: string | null;
};

export type VoiceJoin = { url: string; token: string };

/** /ws/patients/{id}/chat */
export type PatientEvent =
  | { type: "voice_call"; call_id: string; url: string; token: string }
  | { type: "log_entry"; call_id: string; entry: LogEntry }
  | { type: "voice_call_ended" }
  | {
      type: "snapshot";
      call_id: string | null;
      active: boolean;
      messages: ChatMessage[];
      escalation: EscalationState | null;
      voice?: { call_id: string } & VoiceJoin;
      log?: LogEntry[];
    }
  | { type: "call_started"; call_id: string }
  | ({ type: "message"; call_id: string } & ChatMessage)
  | ({ type: "escalation"; call_id?: string } & EscalationState)
  | { type: "call_ended"; call_id: string };

/** /ws/doctors/{id} */
export type RingEvent = { escalation_id: string; patient_id: string; patient_name: string };
export type DoctorEvent =
  | { type: "snapshot"; ringing: RingEvent[] }
  | ({ type: "incoming_call" } & RingEvent)
  | { type: "call_taken"; escalation_id: string }
  | { type: "call_ended"; escalation_id: string };

/** /ws/escalations/{id} */
export type EscalationEvent =
  | {
      type: "snapshot";
      status: string;
      summary: string | null;
      messages: ChatMessage[];
      voice_join: VoiceJoin | null;
      brief_join: VoiceJoin | null;
    }
  | ({ type: "message" } & ChatMessage)
  | ({ type: "brief_join" } & VoiceJoin)
  | ({ type: "voice_join" } & VoiceJoin)
  | { type: "status"; status: string; summary?: string | null }
  | { type: "gone" };

/** /ws/operator -- any event means "the roster may have changed". */
export type OperatorEvent = { type: string; patient_id?: string };
