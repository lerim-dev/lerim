"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { formatRecordKind, formatRecordRole, formatScopeLabel, humanizeToken } from "@/lib/labels";
import type { ContextRecord, FeedbackSignal, RecordFeedbackEntry, RecordFeedbackResult } from "@/lib/types";

interface RecordEditorProps {
  record: ContextRecord;
  /** Called after a feedback signal is recorded, so a parent list/banner can refetch. */
  onFeedbackSubmitted?: (result: RecordFeedbackResult) => void;
}

interface FeedbackAction {
  signal: FeedbackSignal;
  label: string;
  hint: string;
  tone: "positive" | "negative";
}

const FEEDBACK_ACTIONS: FeedbackAction[] = [
  { signal: "used", label: "Used", hint: "Retrieved and used as-is (+0.05 confidence)", tone: "positive" },
  { signal: "correct", label: "Correct", hint: "Verified correct (+0.15 confidence)", tone: "positive" },
  { signal: "confirm", label: "Confirm", hint: "Independently re-confirmed (+0.15 confidence)", tone: "positive" },
  { signal: "wrong", label: "Wrong", hint: "Verified wrong (-0.25 confidence)", tone: "negative" },
];

export default function RecordEditor({ record, onFeedbackSubmitted }: RecordEditorProps) {
  const { addToast } = useToast();
  const rolePayload = parseRolePayload(record.role_payload);
  const evidenceRefs = parseReferenceList(record.evidence_refs);
  const sourceEventRefs = parseReferenceList(record.source_event_refs);

  const [confidence, setConfidence] = useState(record.confidence);
  const [entries, setEntries] = useState<RecordFeedbackEntry[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(true);
  const [entriesError, setEntriesError] = useState<string | null>(null);
  const [busySignal, setBusySignal] = useState<FeedbackSignal | null>(null);

  /* Resync the displayed confidence whenever the parent hands us a fresh record
     (e.g. after it refetches following a feedback submission). */
  useEffect(() => {
    setConfidence(record.confidence);
  }, [record.record_id, record.confidence]);

  /* Load feedback history for the selected record; degrade to an inline error
     rather than throwing, since this is supplementary to the record itself. */
  useEffect(() => {
    let cancelled = false;
    setEntriesLoading(true);
    setEntriesError(null);
    api
      .getRecordFeedback(record.record_id)
      .then((rows) => {
        if (!cancelled) setEntries(rows);
      })
      .catch((err) => {
        if (!cancelled) setEntriesError(err instanceof Error ? err.message : "Failed to load feedback history");
      })
      .finally(() => {
        if (!cancelled) setEntriesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [record.record_id]);

  const submitFeedback = async (signal: FeedbackSignal) => {
    setBusySignal(signal);
    try {
      const result = await api.recordFeedback(record.record_id, signal);
      setConfidence(result.confidence);
      setEntries((current) => [
        ...current,
        {
          feedback_id: `pending-${Date.now()}`,
          record_id: record.record_id,
          signal: result.signal,
          note: null,
          source_session_id: null,
          created_at: new Date().toISOString(),
        },
      ]);
      addToast({ type: "success", message: `Feedback recorded: ${formatFeedbackSignal(signal)}` });
      onFeedbackSubmitted?.(result);
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Feedback failed" });
    } finally {
      setBusySignal(null);
    }
  };

  const hasStaticProvenance = Boolean(record.source_session_id || evidenceRefs.length > 0 || sourceEventRefs.length > 0);
  const showProvenanceEmptyState = !hasStaticProvenance && !entriesLoading && !entriesError && entries.length === 0;

  return (
    <div className="flex h-full flex-col rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)]">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
        <h2 id="record-editor-title" className="text-sm font-semibold text-[var(--text)]">
          Record
        </h2>
        <span className="rounded bg-white/[0.06] px-2 py-0.5 text-[11px] font-medium text-[var(--text-muted)]">
          Read-only
        </span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <Field label="Title" value={record.title || "Untitled"} />

        <div className="flex flex-wrap items-center gap-3">
          <Pill label="Type" value={formatRecordKind(record.record_kind)} />
          {record.record_role && record.record_role !== "general" && (
            <Pill label="Role" value={formatRecordRole(record.record_role)} />
          )}
          {record.project && <Pill label="Project" value={formatScopeLabel(record.project)} />}
          <Pill label="Status" value={record.status || "unknown"} />
        </div>

        <div>
          <p className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">Record ID</p>
          <p className="break-all font-mono text-xs text-[var(--text-muted)]">{record.record_id}</p>
        </div>

        {(record.source_session_id || record.source) && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">Source</p>
            <p className="break-all font-mono text-xs text-[var(--text-muted)]">
              {record.source_session_id || record.source}
            </p>
          </div>
        )}

        <div>
          <p className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">Body</p>
          <div className="min-h-32 whitespace-pre-wrap rounded-md border border-[var(--border)] bg-[var(--bg-card)] px-3 py-2 text-sm leading-relaxed text-[var(--text)]">
            {record.body || "No body stored for this record."}
          </div>
        </div>

        {rolePayload.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">Role Payload</p>
            <div className="space-y-2 rounded-md border border-[var(--border)] bg-[var(--bg-card)] px-3 py-2">
              {rolePayload.map(([key, value]) => (
                <div key={key} className="grid gap-1 text-sm sm:grid-cols-[130px_minmax(0,1fr)]">
                  <span className="text-xs font-medium text-[var(--text-muted)]">{humanizeToken(key)}</span>
                  <span className="whitespace-pre-wrap break-words text-[var(--text)]">{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Created" value={record.created_at || "unknown"} />
          <Field label="Updated" value={record.updated_at || "unknown"} />
        </div>

        {/* ---- Feedback confidence + verify controls ---- */}
        <div className="rounded-md border border-[var(--border)] bg-[var(--bg-card)] px-3 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium text-[var(--text-secondary)]">Feedback confidence</p>
            <ConfidenceMeter confidence={confidence} />
          </div>
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
            Earned from recorded feedback signals below. Distinct from any relationship confidence shown in the graph
            explorer.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {FEEDBACK_ACTIONS.map((action) => (
              <button
                key={action.signal}
                type="button"
                title={action.hint}
                onClick={() => submitFeedback(action.signal)}
                disabled={busySignal !== null}
                className={`min-h-9 rounded-md border px-3 text-xs font-medium outline-none transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)] ${
                  action.tone === "negative"
                    ? "border-red-400/30 text-red-200 hover:bg-red-400/10"
                    : "border-[var(--border)] text-[var(--text)] hover:bg-white/[0.05]"
                }`}
              >
                {busySignal === action.signal ? "Saving…" : action.label}
              </button>
            ))}
          </div>
        </div>

        {/* ---- Provenance / proof-of-value ---- */}
        <div className="rounded-md border border-[var(--border)] bg-[var(--bg-card)] px-3 py-3">
          <p className="text-xs font-medium text-[var(--text-secondary)]">Provenance</p>
          {showProvenanceEmptyState ? (
            <p className="mt-2 text-xs text-[var(--text-muted)]">
              No source session, evidence, or feedback recorded for this record yet.
            </p>
          ) : (
            <div className="mt-2 space-y-3">
              <ProvenanceRow label="Source session" value={record.source_session_id} />
              <ProvenanceList label="Evidence references" items={evidenceRefs} />
              <ProvenanceList label="Source event references" items={sourceEventRefs} />

              <div>
                <p className="mb-1 text-[11px] font-medium text-[var(--text-muted)]">Feedback history</p>
                {entriesLoading && <p className="text-xs text-[var(--text-muted)]">Loading…</p>}
                {!entriesLoading && entriesError && (
                  <p className="text-xs text-[var(--text-muted)]">Feedback history unavailable: {entriesError}</p>
                )}
                {!entriesLoading && !entriesError && entries.length === 0 && (
                  <p className="text-xs text-[var(--text-muted)]">No feedback recorded yet.</p>
                )}
                {!entriesLoading && !entriesError && entries.length > 0 && (
                  <ul className="space-y-1.5">
                    {[...entries].reverse().map((entry) => (
                      <li
                        key={entry.feedback_id}
                        className="flex flex-wrap items-center gap-2 rounded border border-[var(--border)] bg-black/10 px-2 py-1 text-[11px]"
                      >
                        <span className="rounded bg-white/[0.06] px-1.5 py-0.5 font-medium text-[var(--text)]">
                          {formatFeedbackSignal(entry.signal)}
                        </span>
                        <span className="text-[var(--text-muted)]">{formatFeedbackTime(entry.created_at)}</span>
                        {entry.source_session_id && (
                          <span className="break-all font-mono text-[var(--text-muted)]">{entry.source_session_id}</span>
                        )}
                        {entry.note && <span className="w-full text-[var(--text-secondary)]">{entry.note}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ProvenanceRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium text-[var(--text-muted)]">{label}</p>
      <p className="break-all font-mono text-xs text-[var(--text-secondary)]">{value}</p>
    </div>
  );
}

function ProvenanceList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="mb-1 text-[11px] font-medium text-[var(--text-muted)]">{label}</p>
      <ul className="space-y-1">
        {items.map((item, index) => (
          <li
            key={`${index}:${item.slice(0, 24)}`}
            className="whitespace-pre-wrap break-words text-xs text-[var(--text-secondary)]"
          >
            &ldquo;{item}&rdquo;
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConfidenceMeter({ confidence }: { confidence: number | null }) {
  if (confidence == null) {
    return <span className="text-xs text-[var(--text-muted)]">{"—"}</span>;
  }
  const pct = Math.round(Math.max(0, Math.min(1, confidence)) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-[var(--accent-teal)]" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-[var(--text)]">{pct}%</span>
    </div>
  );
}

function parseRolePayload(payload?: string | null): Array<[string, string]> {
  const text = payload?.trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return [["payload", text]];
    return Object.entries(parsed).map(([key, value]) => [key, renderPayloadValue(value)]);
  } catch {
    return [["payload", text]];
  }
}

function renderPayloadValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(renderPayloadValue).join("\n");
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value ?? "");
}

/** Parse a compact-JSON reference list (`evidence_refs`/`source_event_refs`); tolerate plain text. */
function parseReferenceList(value?: string | null): string[] {
  const text = value?.trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text) as unknown;
    if (Array.isArray(parsed)) {
      return parsed.map((item) => String(item).trim()).filter(Boolean);
    }
    return [String(parsed)];
  } catch {
    return [text];
  }
}

function formatFeedbackSignal(signal: string): string {
  const labels: Record<string, string> = {
    used: "Used",
    correct: "Correct",
    wrong: "Wrong",
    confirm: "Confirmed",
  };
  return labels[signal] || humanizeToken(signal);
}

function formatFeedbackTime(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso || "unknown";
  return parsed.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className="rounded-md border border-[var(--border)] bg-[var(--bg-card)] px-3 py-2 text-sm text-[var(--text)]">
        {value}
      </p>
    </div>
  );
}

function Pill({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <span className="inline-block rounded bg-white/[0.06] px-2 py-1 text-xs text-[var(--text-muted)]">
        {value}
      </span>
    </div>
  );
}
