"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { SkillProposal, SkillTarget } from "@/lib/types";
import { useToast } from "@/components/Toast";

export default function SkillsPage() {
  const { addToast } = useToast();
  const [targets, setTargets] = useState<SkillTarget[]>([]);
  const [proposals, setProposals] = useState<SkillProposal[]>([]);
  const [selectedTargetId, setSelectedTargetId] = useState<string>("");
  const [selectedProposalId, setSelectedProposalId] = useState<string>("");
  const [path, setPath] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [selectedPatchIndex, setSelectedPatchIndex] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [targetData, proposalData] = await Promise.all([
        api.getSkillTargets(),
        api.getSkillProposals(),
      ]);
      setTargets(targetData.targets);
      setProposals(proposalData.proposals);
      if (!selectedTargetId && targetData.targets[0]) setSelectedTargetId(targetData.targets[0].target_id);
      if (!selectedProposalId && proposalData.proposals[0]) setSelectedProposalId(proposalData.proposals[0].proposal_id);
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Failed to load skills" });
    } finally {
      setLoading(false);
    }
  }, [addToast, selectedProposalId, selectedTargetId]);

  useEffect(() => {
    load();
  }, [load]);

  const selectedTarget = targets.find((target) => target.target_id === selectedTargetId) || targets[0] || null;
  const filteredProposals = useMemo(
    () => proposals.filter((proposal) => !selectedTarget || proposal.target_id === selectedTarget.target_id),
    [proposals, selectedTarget],
  );
  const selectedProposal =
    filteredProposals.find((proposal) => proposal.proposal_id === selectedProposalId) ||
    filteredProposals[0] ||
    null;
  const selectedPatch = selectedProposal?.patch_json.patches[selectedPatchIndex] || null;

  useEffect(() => {
    setSelectedPatchIndex(0);
  }, [selectedProposal?.proposal_id]);

  useEffect(() => {
    setEditText(selectedPatch?.after_text || "");
  }, [selectedPatch?.after_text, selectedPatchIndex, selectedProposal?.proposal_id]);

  const register = async () => {
    if (!path.trim()) return;
    setBusy("register");
    try {
      await api.addSkillTarget({
        path: path.trim(),
        name: name.trim() || undefined,
        description: description.trim() || undefined,
        update_mode: "review",
      });
      setPath("");
      setName("");
      setDescription("");
      addToast({ type: "success", message: "Skill registered" });
      await load();
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Could not register skill" });
    } finally {
      setBusy(null);
    }
  };

  const refreshTarget = async (target: SkillTarget) => {
    setBusy(`refresh:${target.target_id}`);
    try {
      await api.refreshSkillTarget(target.target_id);
      addToast({ type: "success", message: "Refresh completed" });
      await load();
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Refresh failed" });
    } finally {
      setBusy(null);
    }
  };

  const toggleAutoApply = async (target: SkillTarget) => {
    const enabled = target.update_mode !== "auto_apply";
    setBusy(`mode:${target.target_id}`);
    try {
      await api.updateSkillTargetMode(target.target_id, {
        update_mode: enabled ? "auto_apply" : "review",
        auto_apply_policy: { ...target.auto_apply_policy, enabled, max_risk: "low" },
      });
      addToast({ type: "success", message: enabled ? "Auto-apply enabled" : "Auto-apply disabled" });
      await load();
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Mode update failed" });
    } finally {
      setBusy(null);
    }
  };

  const applyProposal = async (proposal: SkillProposal) => {
    setBusy(`apply:${proposal.proposal_id}`);
    try {
      await api.applySkillProposal(proposal.proposal_id);
      addToast({ type: "success", message: "Proposal applied" });
      await load();
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Apply failed" });
    } finally {
      setBusy(null);
    }
  };

  const rejectProposal = async (proposal: SkillProposal) => {
    setBusy(`reject:${proposal.proposal_id}`);
    try {
      await api.rejectSkillProposal(proposal.proposal_id);
      addToast({ type: "success", message: "Proposal rejected" });
      await load();
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Reject failed" });
    } finally {
      setBusy(null);
    }
  };

  const saveEditedProposal = async (proposal: SkillProposal) => {
    if (!selectedPatch) return;
    setBusy(`edit:${proposal.proposal_id}`);
    try {
      await api.editSkillProposal(proposal.proposal_id, {
        ...proposal.patch_json,
        patches: proposal.patch_json.patches.map((patch, index) =>
          index === selectedPatchIndex ? { ...patch, after_text: editText } : patch,
        ),
      });
      addToast({ type: "success", message: "Proposal updated" });
      await load();
    } catch (err) {
      addToast({ type: "error", message: err instanceof Error ? err.message : "Edit failed" });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-[var(--text)]">Skills</h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--text-secondary)]">
            Registered instruction artifacts, evidence-backed updates, and review gates.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="min-h-11 rounded-md border border-[var(--border)] px-4 text-sm font-medium text-[var(--text)] hover:bg-white/[0.05]"
        >
          Refresh
        </button>
      </div>

      <section className="grid min-w-0 gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4 md:grid-cols-[minmax(0,1fr)_10rem]">
        <div className="grid gap-3 md:grid-cols-3">
          <input
            value={path}
            onChange={(event) => setPath(event.target.value)}
            placeholder="Path to SKILL.md, AGENTS.md, or skill folder"
            className="min-h-11 rounded-md border border-[var(--border)] bg-black/20 px-3 text-sm text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)] md:col-span-3"
          />
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Name"
            className="min-h-11 rounded-md border border-[var(--border)] bg-black/20 px-3 text-sm text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
          />
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Improvement intent"
            className="min-h-11 rounded-md border border-[var(--border)] bg-black/20 px-3 text-sm text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)] md:col-span-2"
          />
        </div>
        <button
          type="button"
          onClick={register}
          disabled={busy === "register" || !path.trim()}
          className="min-h-11 rounded-md bg-[var(--accent-blue)] px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          Register
        </button>
      </section>

      <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <section className="min-w-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-card)]">
          <div className="border-b border-[var(--border)] px-4 py-3">
            <h2 className="text-sm font-semibold text-[var(--text)]">Registered Skills</h2>
          </div>
          <div className="max-h-[34rem] overflow-y-auto p-2">
            {loading && <div className="p-3 text-sm text-[var(--text-muted)]">Loading…</div>}
            {!loading && targets.length === 0 && <div className="p-3 text-sm text-[var(--text-muted)]">No skills registered.</div>}
            {targets.map((target) => (
              <button
                key={target.target_id}
                type="button"
                onClick={() => setSelectedTargetId(target.target_id)}
                className={`mb-2 min-w-0 w-full rounded-md border p-3 text-left transition-colors ${
                  selectedTarget?.target_id === target.target_id
                    ? "border-[var(--accent-blue)] bg-blue-500/10"
                    : "border-[var(--border)] bg-white/[0.02] hover:bg-white/[0.05]"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-[var(--text)]">{target.name}</span>
                  <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
                    {target.update_mode}
                  </span>
                </div>
                <div className="mt-1 truncate text-xs text-[var(--text-muted)]">{target.path}</div>
                <div className="mt-2 flex flex-wrap gap-1.5 text-[10px] text-[var(--text-secondary)]">
                  <span className="rounded bg-white/[0.05] px-1.5 py-0.5">{target.target_type}</span>
                  <span className="rounded bg-white/[0.05] px-1.5 py-0.5">{target.file_count || 0} files</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="min-w-0 space-y-4">
          {selectedTarget && (
            <div className="min-w-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-[var(--text)]">{selectedTarget.name}</h2>
                  <p className="mt-1 break-all text-xs text-[var(--text-muted)]">{selectedTarget.path}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => refreshTarget(selectedTarget)}
                    disabled={busy === `refresh:${selectedTarget.target_id}`}
                    className="min-h-10 rounded-md border border-[var(--border)] px-3 text-xs font-medium text-[var(--text)] hover:bg-white/[0.05] disabled:opacity-50"
                  >
                    Scan
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleAutoApply(selectedTarget)}
                    disabled={busy === `mode:${selectedTarget.target_id}`}
                    className={`min-h-10 rounded-md px-3 text-xs font-semibold disabled:opacity-50 ${
                      selectedTarget.update_mode === "auto_apply"
                        ? "bg-emerald-400 text-slate-950"
                        : "border border-[var(--border)] text-[var(--text)] hover:bg-white/[0.05]"
                    }`}
                  >
                    Auto
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <Metric label="Type" value={selectedTarget.target_type} />
                <Metric label="Entry" value={selectedTarget.entry_file} />
                <Metric label="Pending" value={String(filteredProposals.filter((proposal) => proposal.status === "pending_review").length)} />
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <FileList title="Tracked Files" files={selectedTarget.files || []} />
                <ManifestPanel target={selectedTarget} />
              </div>
            </div>
          )}

            <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
            <ProposalList
              proposals={filteredProposals}
              selectedId={selectedProposal?.proposal_id || ""}
              onSelect={setSelectedProposalId}
            />
            <ProposalReview
              proposal={selectedProposal}
              editText={editText}
              onEditText={setEditText}
              selectedPatchIndex={selectedPatchIndex}
              onSelectPatch={setSelectedPatchIndex}
              onSave={saveEditedProposal}
              onApply={applyProposal}
              onReject={rejectProposal}
              busy={busy}
            />
          </div>
        </section>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-black/10 p-3">
      <div className="text-[10px] uppercase text-[var(--text-muted)]">{label}</div>
      <div className="mt-1 truncate text-sm font-medium text-[var(--text)]">{value}</div>
    </div>
  );
}

function FileList({ title, files }: { title: string; files: NonNullable<SkillTarget["files"]> }) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-black/10 p-3">
      <h3 className="text-xs font-semibold text-[var(--text)]">{title}</h3>
      <div className="mt-2 max-h-44 space-y-1 overflow-y-auto">
        {files.map((file) => (
          <div key={file.relative_path} className="flex items-center justify-between gap-2 text-xs">
            <span className="min-w-0 truncate text-[var(--text-secondary)]">{file.relative_path}</span>
            <span className="shrink-0 rounded bg-white/[0.05] px-1.5 py-0.5 text-[10px] text-[var(--text-muted)]">
              {file.file_role}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ManifestPanel({ target }: { target: SkillTarget }) {
  const manifest = target.manifest;
  return (
    <div className="rounded-md border border-[var(--border)] bg-black/10 p-3">
      <h3 className="text-xs font-semibold text-[var(--text)]">Update Surfaces</h3>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {(manifest?.allowed_update_surfaces || []).map((surface) => (
          <span key={surface} className="rounded bg-emerald-400/10 px-2 py-1 text-[10px] text-emerald-200">
            {surface}
          </span>
        ))}
        {(manifest?.high_risk_surfaces || []).map((surface) => (
          <span key={surface} className="rounded bg-amber-400/10 px-2 py-1 text-[10px] text-amber-200">
            {surface}
          </span>
        ))}
      </div>
    </div>
  );
}

function ProposalList({
  proposals,
  selectedId,
  onSelect,
}: {
  proposals: SkillProposal[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-card)]">
      <div className="border-b border-[var(--border)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--text)]">Updates</h2>
      </div>
      <div className="max-h-[30rem] overflow-y-auto p-2">
        {proposals.length === 0 && <div className="p-3 text-sm text-[var(--text-muted)]">No update proposals.</div>}
        {proposals.map((proposal) => (
          <button
            key={proposal.proposal_id}
            type="button"
            onClick={() => onSelect(proposal.proposal_id)}
            className={`mb-2 min-w-0 w-full rounded-md border p-3 text-left ${
              selectedId === proposal.proposal_id
                ? "border-[var(--accent-blue)] bg-blue-500/10"
                : "border-[var(--border)] bg-white/[0.02] hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="line-clamp-1 text-sm font-semibold text-[var(--text)]">{proposal.title}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] ${riskClass(proposal.risk_level)}`}>
                {proposal.risk_level}
              </span>
            </div>
            <div className="mt-1 line-clamp-2 text-xs text-[var(--text-secondary)]">{proposal.summary}</div>
            <div className="mt-2 text-[10px] text-[var(--text-muted)]">{proposal.status}</div>
          </button>
        ))}
      </div>
    </section>
  );
}

function ProposalReview({
  proposal,
  editText,
  onEditText,
  selectedPatchIndex,
  onSelectPatch,
  onSave,
  onApply,
  onReject,
  busy,
}: {
  proposal: SkillProposal | null;
  editText: string;
  onEditText: (value: string) => void;
  selectedPatchIndex: number;
  onSelectPatch: (index: number) => void;
  onSave: (proposal: SkillProposal) => void;
  onApply: (proposal: SkillProposal) => void;
  onReject: (proposal: SkillProposal) => void;
  busy: string | null;
}) {
  if (!proposal) {
    return (
      <section className="min-w-0 rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4 text-sm text-[var(--text-muted)]">
        Select an update proposal to review.
      </section>
    );
  }
  const patches = proposal.patch_json.patches;
  const patch = patches[selectedPatchIndex] || patches[0];
  return (
    <section className="min-w-0 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-card)]">
      <div className="border-b border-[var(--border)] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-[var(--text)]">{proposal.title}</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{proposal.summary}</p>
          </div>
          <span className={`rounded-full px-2.5 py-1 text-xs ${riskClass(proposal.risk_level)}`}>{proposal.risk_level}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {Array.from(new Set(patches.flatMap((item) => item.evidence_record_ids || []))).map((recordId) => (
            <span key={recordId} className="rounded bg-white/[0.05] px-2 py-1 text-[10px] text-[var(--text-secondary)]">
              {recordId}
            </span>
          ))}
        </div>
        {patches.length > 1 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {patches.map((item, index) => (
              <button
                key={`${item.relative_path}:${index}`}
                type="button"
                onClick={() => onSelectPatch(index)}
                className={`min-h-8 max-w-full rounded-md border px-2 text-xs ${
                  index === selectedPatchIndex
                    ? "border-[var(--accent-blue)] bg-blue-500/10 text-[var(--text)]"
                    : "border-[var(--border)] text-[var(--text-secondary)] hover:bg-white/[0.05]"
                }`}
              >
                <span className="block max-w-56 truncate">{item.relative_path}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {patch ? (
        <div className="grid gap-0 lg:grid-cols-2">
          <div className="border-b border-[var(--border)] p-4 lg:border-b-0 lg:border-r">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h3 className="text-xs font-semibold text-[var(--text)]">Editable Result</h3>
              <span className="text-[10px] text-[var(--text-muted)]">{patch.relative_path}</span>
            </div>
            <textarea
              value={editText}
              onChange={(event) => onEditText(event.target.value)}
              className="h-[26rem] w-full resize-y rounded-md border border-[var(--border)] bg-black/30 p-3 font-mono text-xs leading-5 text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-blue)]"
            />
          </div>
          <div className="p-4">
            <h3 className="mb-2 text-xs font-semibold text-[var(--text)]">Diff</h3>
            <pre className="h-[26rem] overflow-auto rounded-md border border-[var(--border)] bg-black/30 p-3 text-xs leading-5 text-[var(--text-secondary)]">
              {patch.diff_text || "No diff available until the proposal is regenerated."}
            </pre>
          </div>
        </div>
      ) : (
        <div className="p-4 text-sm text-[var(--text-muted)]">This proposal has no patch.</div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] p-4">
        <ValidationState proposal={proposal} />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onSave(proposal)}
            disabled={!patch || busy === `edit:${proposal.proposal_id}`}
            className="min-h-10 rounded-md border border-[var(--border)] px-3 text-xs font-medium text-[var(--text)] hover:bg-white/[0.05] disabled:opacity-50"
          >
            Save Edit
          </button>
          <button
            type="button"
            onClick={() => onReject(proposal)}
            disabled={busy === `reject:${proposal.proposal_id}`}
            className="min-h-10 rounded-md border border-red-400/30 px-3 text-xs font-medium text-red-200 hover:bg-red-400/10 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            type="button"
            onClick={() => onApply(proposal)}
            disabled={busy === `apply:${proposal.proposal_id}` || proposal.status === "applied"}
            className="min-h-10 rounded-md bg-emerald-400 px-3 text-xs font-semibold text-slate-950 disabled:opacity-50"
          >
            Apply
          </button>
        </div>
      </div>
    </section>
  );
}

function ValidationState({ proposal }: { proposal: SkillProposal }) {
  const ok = proposal.validation_json?.ok;
  const errors = proposal.validation_json?.errors || [];
  return (
    <div className="text-xs">
      <span className={ok ? "text-emerald-300" : "text-amber-200"}>
        {ok ? "Validation passed" : "Needs review"}
      </span>
      {errors.length > 0 && <span className="ml-2 text-[var(--text-muted)]">{errors[0]}</span>}
    </div>
  );
}

function riskClass(risk: string) {
  if (risk === "high") return "bg-red-400/10 text-red-200";
  if (risk === "medium") return "bg-amber-400/10 text-amber-200";
  return "bg-emerald-400/10 text-emerald-200";
}
