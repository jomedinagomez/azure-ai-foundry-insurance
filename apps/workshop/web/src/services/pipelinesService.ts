import axios from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";

const API_BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

export type StepKind =
  | "xlsx_preflight"
  | "libreoffice_to_pdf"
  | "pdf_to_tiff"
  | "extract_embedded_images"
  | "cu_analyze";

export interface PipelineStep {
  id: string;
  kind: StepKind;
  label?: string | null;
  params: Record<string, unknown>;
}

export interface Pipeline {
  id: string;
  name: string;
  description: string;
  input_extensions: string[];
  is_default: boolean;
  steps: PipelineStep[];
}

export interface StepEvent {
  pipeline_id: string;
  step_index: number;
  step_id: string;
  step_kind: StepKind;
  status: "pending" | "running" | "done" | "error";
  elapsed_sec?: number | null;
  meta?: Record<string, unknown>;
  error?: string | null;
}

export interface PipelineRunResult {
  payload: Record<string, unknown>;
  timings: Record<string, number>;
  artifacts: Record<string, string>;
}

// ── Library CRUD ───────────────────────────────────────────────────────────
export async function fetchPipelines(): Promise<Pipeline[]> {
  const r = await axios.get<Pipeline[]>(`${API_BASE}/pipelines`);
  return r.data;
}

export async function fetchPipeline(id: string): Promise<Pipeline> {
  const r = await axios.get<Pipeline>(`${API_BASE}/pipelines/${encodeURIComponent(id)}`);
  return r.data;
}

export async function fetchDefaultPipeline(extension: string): Promise<Pipeline> {
  const r = await axios.get<Pipeline>(
    `${API_BASE}/pipelines/default`,
    { params: { extension } }
  );
  return r.data;
}

export async function savePipeline(pipeline: Pipeline): Promise<Pipeline> {
  const r = await axios.put<Pipeline>(
    `${API_BASE}/pipelines/${encodeURIComponent(pipeline.id)}`,
    pipeline
  );
  return r.data;
}

// ── Run (sync) ─────────────────────────────────────────────────────────────
export async function runPipeline(
  pipelineId: string,
  sampleName: string,
  saveAsCanonical: boolean = false
): Promise<PipelineRunResult> {
  const r = await axios.post<PipelineRunResult>(
    `${API_BASE}/pipelines/${encodeURIComponent(pipelineId)}/run`,
    { sample_name: sampleName, save_as_canonical: saveAsCanonical }
  );
  return r.data;
}

// ── Run (streaming via SSE) ────────────────────────────────────────────────
export interface RunStreamCallbacks {
  onStep?: (e: StepEvent) => void;
  onComplete?: (r: PipelineRunResult) => void;
  onError?: (msg: string) => void;
}

export async function runPipelineStream(
  pipelineId: string,
  sampleName: string,
  cb: RunStreamCallbacks,
  saveAsCanonical: boolean = false,
  signal?: AbortSignal
): Promise<void> {
  await fetchEventSource(
    `${API_BASE}/pipelines/${encodeURIComponent(pipelineId)}/run/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ sample_name: sampleName, save_as_canonical: saveAsCanonical }),
      signal,
      onmessage(ev) {
        try {
          const data = JSON.parse(ev.data);
          if (ev.event === "step") cb.onStep?.(data as StepEvent);
          else if (ev.event === "complete") cb.onComplete?.(data as PipelineRunResult);
          else if (ev.event === "error") cb.onError?.((data as { error: string }).error);
        } catch (e: any) {
          cb.onError?.(`bad event payload: ${e?.message ?? e}`);
        }
      },
      onerror(err) {
        cb.onError?.(err?.message ?? String(err));
        throw err; // stop retries
      },
      openWhenHidden: true,
    }
  );
}
