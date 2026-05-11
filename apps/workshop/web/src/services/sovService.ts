import axios from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import type { StepEvent } from "./pipelinesService";

const API_BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

/** Resolve a server-relative path (e.g. an artifact URL) to an absolute one
 * the browser can fetch. Useful for `<a href>` and `<img src>` attributes. */
export function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (!path.startsWith("/")) path = "/" + path;
  return `${API_BASE}${path}`;
}

export interface SovSample {
  file_name: string;
  file_type: "xlsx" | "pdf";
  size_kb: number;
  has_cached_result: boolean;
  has_ground_truth: boolean;
}

export type Pattern = "A" | "B" | "C";

export interface SovExtractionMeta {
  source_file: string;
  approach?: string | null;
  analyzer_id?: string | null;
  pattern: Pattern;
  elapsed_sec?: number | null;
  image_calls?: number | null;
  added_from_images?: number | null;
  field_complements?: number | null;
  elapsed_main_sec?: number | null;
  elapsed_images_sec?: number | null;
  elapsed_total_sec?: number | null;
  from_cache: boolean;
  pipeline_id?: string | null;
  pipeline_name?: string | null;
  // The schema accepts unknown extras (pipeline_timings, pipeline_artifacts, etc.).
  [key: string]: unknown;
}

export interface SovAccountSummary {
  insured_name?: string | null;
  dba?: string | null;
  mailing_address?: string | null;
  effective_date?: string | null;
  expiration_date?: string | null;
  primary_operations?: string | null;
  naics?: string | null;
  currency?: string | null;
  valuation_date?: string | null;
  total_insured_value?: number | null;
  location_count?: number | null;
  broker_name?: string | null;
  broker_contact?: string | null;
  broker_email?: string | null;
  broker_phone?: string | null;
  prepared_by?: string | null;
  prepared_date?: string | null;
}

export interface SovLocation {
  location_number?: number | string | null;
  building_number?: number | string | null;
  street?: string | null;
  city?: string | null;
  state?: string | null;
  zip?: string | null;
  construction_type?: string | null;
  occupancy?: string | null;
  operations_description?: string | null;
  year_built?: number | null;
  stories?: number | null;
  square_footage?: number | null;
  unit_count?: number | null;
  building_value?: number | null;
  bpp_value?: number | null;
  bi_ee_value?: number | null;
  sprinklered?: string | boolean | null;
  protection_class?: number | string | null;
  roof_year?: number | null;
  flood_zone?: string | null;
  distance_to_coast_mi?: number | null;
  notes?: string | null;
  source?: string | null;
}

export interface SovExtractionResult {
  file_name: string;
  meta: SovExtractionMeta;
  account: SovAccountSummary;
  account_confidence: Record<string, number | null>;
  locations: SovLocation[];
  locations_confidence: Record<string, number | null>[];
  location_count_actual: number;
  raw: Record<string, unknown>;
}

export interface SovValidationDiff {
  scope: "account" | "location";
  location_key: number | string | null;
  field: string;
  actual: unknown;
  expected: unknown;
  in_source: boolean;
  match: boolean;
}

export interface SovValidationResult {
  summary: {
    file_name: string;
    location_count_actual: number;
    location_count_expected: number;
    account_mismatches_in_source: number;
    location_mismatches_in_source: number;
  };
  account: SovValidationDiff[];
  locations: SovValidationDiff[];
  has_ground_truth: boolean;
}

export async function fetchSovSamples(): Promise<SovSample[]> {
  const r = await axios.get<SovSample[]>(`${API_BASE}/sov/samples`);
  return r.data;
}

export async function fetchCachedExtraction(name: string): Promise<SovExtractionResult> {
  const r = await axios.get<SovExtractionResult>(
    `${API_BASE}/sov/samples/${encodeURIComponent(name)}/cached`
  );
  return r.data;
}

export async function runExtraction(
  sampleName: string,
  forceRefresh = false,
  pattern?: Pattern | null
): Promise<SovExtractionResult> {
  const r = await axios.post<SovExtractionResult>(`${API_BASE}/sov/extract`, {
    sample_name: sampleName,
    force_refresh: forceRefresh,
    pattern: pattern ?? null,
  });
  return r.data;
}

/**
 * Run a pipeline against a known sample and return the same projected
 * SovExtractionResult shape that runExtraction returns. `pipelineId=null`
 * picks the extension default on the server.
 */
export async function runPipelineExtraction(
  sampleName: string,
  pipelineId: string | null,
  saveAsCanonical = false
): Promise<SovExtractionResult> {
  const r = await axios.post<SovExtractionResult>(`${API_BASE}/sov/extract/pipeline`, {
    sample_name: sampleName,
    pipeline_id: pipelineId,
    save_as_canonical: saveAsCanonical,
  });
  return r.data;
}

// ── Streaming pipeline run (SSE) projected to SovExtractionResult ──────────
// Reuses the generic StepEvent shape from pipelinesService so the existing
// RunDialog can stay generic over the stream-fn.

export interface SovPipelineRunEnvelope {
  /** Already-projected SOV result, ready to drop into setResult(). */
  result: SovExtractionResult;
  /** Per-step elapsed seconds (kept so the dialog can show total time). */
  timings: Record<string, number>;
  artifacts: Record<string, string>;
}

export interface SovPipelineStreamCallbacks {
  onStep?: (e: StepEvent) => void;
  onComplete?: (envelope: SovPipelineRunEnvelope) => void;
  onError?: (msg: string) => void;
}

/**
 * Same SSE protocol as `runPipelineStream` but the `complete` event payload
 * is `{ result: SovExtractionResult, timings, artifacts }` instead of the
 * raw CU `PipelineRunResult`. Server route: `POST /sov/extract/pipeline/stream`.
 */
export async function runSovPipelineStream(
  pipelineId: string,
  sampleName: string,
  cb: SovPipelineStreamCallbacks,
  saveAsCanonical = false,
  signal?: AbortSignal
): Promise<void> {
  await fetchEventSource(`${API_BASE}/sov/extract/pipeline/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      sample_name: sampleName,
      pipeline_id: pipelineId,
      save_as_canonical: saveAsCanonical,
    }),
    signal,
    onmessage(ev) {
      try {
        const data = JSON.parse(ev.data);
        if (ev.event === "step") cb.onStep?.(data as StepEvent);
        else if (ev.event === "complete") cb.onComplete?.(data as SovPipelineRunEnvelope);
        else if (ev.event === "error") cb.onError?.((data as { error: string }).error);
      } catch (e: any) {
        cb.onError?.(`bad event payload: ${e?.message ?? e}`);
      }
    },
    onerror(err) {
      cb.onError?.(err?.message ?? String(err));
      throw err;
    },
    openWhenHidden: true,
  });
}

export async function uploadAndExtract(file: File): Promise<SovExtractionResult> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await axios.post<SovExtractionResult>(
    `${API_BASE}/sov/extract/upload`,
    fd,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return r.data;
}

export async function saveResultToCache(
  sampleName: string,
  payload: Record<string, unknown>
): Promise<void> {
  await axios.post(`${API_BASE}/sov/save-cache`, {
    sample_name: sampleName,
    payload,
  });
}

export async function runValidation(
  sampleName: string,
  forceRefresh = false
): Promise<SovValidationResult> {
  const r = await axios.post<SovValidationResult>(`${API_BASE}/sov/validate`, {
    sample_name: sampleName,
    force_refresh: forceRefresh,
  });
  return r.data;
}

// ── Analyzer templates ──────────────────────────────────────────────────────
export interface SovAnalyzer {
  id: string;
  template_file: string;
  method: "extract" | "generate";
  use_case: string;
  exists: boolean;
  size_bytes: number;
}

export async function fetchAnalyzers(): Promise<SovAnalyzer[]> {
  const r = await axios.get<SovAnalyzer[]>(`${API_BASE}/sov/analyzers`);
  return r.data;
}

export async function fetchAnalyzerTemplate(templateFile: string): Promise<Record<string, unknown>> {
  const r = await axios.get<Record<string, unknown>>(
    `${API_BASE}/sov/analyzers/${encodeURIComponent(templateFile)}`
  );
  return r.data;
}

export async function saveAnalyzerTemplate(
  templateFile: string,
  body: Record<string, unknown>
): Promise<void> {
  await axios.put(`${API_BASE}/sov/analyzers/${encodeURIComponent(templateFile)}`, body);
}

export async function pushAnalyzerToFoundry(
  templateFile: string,
  analyzerId: string
): Promise<{ analyzer_id: string; template_file: string; previous_deleted: boolean; elapsed_sec: number }> {
  const r = await axios.post(
    `${API_BASE}/sov/analyzers/${encodeURIComponent(templateFile)}/push`,
    null,
    { params: { analyzer_id: analyzerId } }
  );
  return r.data;
}

// ── Pattern config ──────────────────────────────────────────────────────────
export interface PatternBinding {
  analyzer_id: string;
  template_file: string;
}

export type PatternConfig = Record<"A" | "B" | "C", PatternBinding>;

export async function fetchPatternConfig(): Promise<PatternConfig> {
  const r = await axios.get<PatternConfig>(`${API_BASE}/sov/patterns`);
  return r.data;
}

export async function updatePattern(
  pattern: "A" | "B" | "C",
  binding: PatternBinding
): Promise<PatternConfig> {
  const r = await axios.put<PatternConfig>(
    `${API_BASE}/sov/patterns/${pattern}`,
    binding
  );
  return r.data;
}
