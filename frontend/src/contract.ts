// Mirrors backend/contracts.py (frozen, ADR-002). Keep these shapes in sync
// by hand: scripts/export_contract.py still reads the superseded backend/models.py
// and has not been updated for the pivot (see WP4's final report).
// Changing a shape here without a matching contracts.py change breaks the API.

// ---------------------------------------------------------------------------
// API (jury contract unchanged; extras optional) — contracts.py bottom section
// ---------------------------------------------------------------------------

// Upload containers POST /api/v1/analyze accepts; mirrors backend/media.py VIDEO_SUFFIXES.
export const VIDEO_SUFFIXES = ['.mov', '.mp4', '.mkv'];

export type Coverage = {
  step_s: number;
  planned: number;
  done: number;
  failed: number;
  deadline_hit: boolean;
  mode: 'full' | 'coarse' | 'partial';
};

export type EvidenceFrame = {
  timestamp_sec: number;
  /** base64-encoded JPEG bytes only. */
  image_base64: string;
};

export type CitationStatus = 'verified' | 'pending' | 'invalid';

export type Violation = {
  // jury-required fields (task.md §10) -- never rename, never add a required one
  type: string;
  timecode_sec: number;
  description: string;
  evidence_frames: EvidenceFrame[]; // 1..3
  // optional extras, used by the UI only (contracts.py: all optional, default null)
  rule_id?: string | null;
  source?: string | null;
  source_url?: string | null;
  /** Verbatim norm text for the UI norm block. */
  source_quote?: string | null;
  strength?: string | null;
  citation_status?: CitationStatus | string | null;
  jurisdiction?: string | null;
  document_title?: string | null;
  issuing_authority?: string | null;
  act_number?: string | null;
  adopted_on?: string | null;
  detection_confidence?: number | null;
  business_status?: 'confirmed' | 'candidate' | null;
  implementation_status?: 'implemented' | 'unimplemented' | null;
};

export type DoneJob = {
  job_id: string;
  status: 'done';
  verdict: 'violation' | 'no_violation';
  violations: Violation[];
  warnings: string[];
  coverage?: Coverage | null;
};

export type ProcessingJob = {
  job_id: string;
  status: 'processing';
};

export type FailedJob = {
  job_id: string;
  status: 'failed';
  error: string;
};

export type AcceptedJob = {
  job_id: string;
};

export type JobResult = DoneJob | ProcessingJob | FailedJob;
/** Alias kept for the existing UI code (= contracts.py's JobResult). */
export type Job = JobResult;
