// Friendly names for the generated API types (api-schema.d.ts, produced by `npm run gen:api` from the
// backend's OpenAPI spec). Change a response model in backend/views.py, re-run
// `python -m backend.dump_openapi` and `npm run gen:api`, and the compiler shows what to update.
import type { components } from "./api-schema";

type S = components["schemas"];

export type People = S["People"];
export type Person = S["Person"];
export type PatientHome = S["PatientHome"];
export type PatientMedicines = S["PatientMedicines"];
export type PatientHistory = S["PatientHistory"];
export type DoctorOverview = S["DoctorOverview"];
export type PatientClinical = S["PatientClinical"];
export type EscalationView = S["EscalationView"];
export type CallTranscript = S["CallTranscript"];
export type OperatorRoster = S["OperatorRoster"];
export type SlotView = S["SlotView"];
export type DayView = S["DayView"];
export type CheckinView = S["CheckinView"];
export type MedicineView = S["MedicineView"];
export type LogView = S["LogView"];
export type EscalationRow = S["EscalationRow"];
export type PatientRow = S["PatientRow"];
export type AdherenceView = S["AdherenceView"];
export type AttentionView = S["AttentionView"];
export type TranscriptEntry = S["TranscriptEntry"];
export type AlertView = S["AlertView"];

export type SlotState =
  | "taken" | "partial" | "missed" | "later" | "unknown" | "skipped" | "upcoming" | "due" | "no_checkin";
export type DayState = "good" | "mixed" | "missed" | "unknown" | "upcoming" | "none";
export type AttentionLevel = "critical" | "warning" | "ok";
