import axios from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";

const API_BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

export type Challenge = "printed" | "handwritten";
export type VariantName = "zero_shot" | "labeled";

export interface LabeledAnalyzerStatus {
  api_version: string;
  model: string;
  embedding_model: string;
  training_files: string[];
  holdout_files: string[];
  labeled_data: {
    ready: boolean;
    training_documents: number;
    sidecars_present: number;
    sidecars_expected: number;
    error?: string | null;
  };
  cached_report: boolean;
  live_endpoint_configured: boolean;
  live_evaluation_enabled: boolean;
  storage_configured: boolean;
  analyzer_ids: Record<VariantName, string>;
}

export interface LabeledAnalyzerSample {
  file_name: string;
  size_kb: number;
  challenge: Challenge;
  has_ground_truth: boolean;
  has_zero_shot_cache: boolean;
  has_labeled_cache: boolean;
}

export interface FieldScore {
  field_name: string;
  expected: unknown;
  actual: unknown;
  confidence: number | null;
  correct: boolean;
  missing: boolean;
  source?: string | null;
  spans: Array<{ offset: number; length: number }>;
}

export interface ThresholdMetric {
  accepted: number;
  false_accepts: number;
  coverage: number;
  precision: number | null;
}

export interface DocumentScore {
  fields: FieldScore[];
  total_fields: number;
  correct_fields: number;
  missing_fields: number;
  accuracy: number;
  missing_rate: number;
  thresholds: Record<string, ThresholdMetric>;
}

export interface ProjectedResult {
  analyzer_id: string;
  api_version: string;
  fields: Record<
    string,
    {
      value: unknown;
      confidence: number | null;
      source?: string | null;
      spans: Array<{ offset: number; length: number }>;
    }
  >;
  cost: Record<string, unknown>;
}

export interface EvaluationRun {
  repeat: number;
  result: ProjectedResult;
  score: DocumentScore;
}

export interface AggregateScore {
  total_fields: number;
  correct_fields: number;
  missing_fields: number;
  accuracy: number;
  missing_rate: number;
  mean_confidence_correct: number | null;
  mean_confidence_incorrect: number | null;
  thresholds: Record<string, ThresholdMetric>;
  field_accuracy: Record<string, number>;
}

export interface VariantEvaluation {
  analyzer_id: string;
  documents: Record<string, { challenge: Challenge; runs: EvaluationRun[] }>;
  aggregate: AggregateScore;
}

export interface LabeledEvaluationReport {
  generated_at: string;
  api_version: string;
  model: string;
  embedding_model: string;
  training_files: string[];
  holdout_files: string[];
  repeats: number;
  variants: Record<VariantName, VariantEvaluation>;
  summary: {
    zero_shot_accuracy: number;
    labeled_accuracy: number;
    accuracy_delta_points: number;
    zero_shot_false_accepts_at_090: number;
    labeled_false_accepts_at_090: number;
  };
}

export interface LabeledStepEvent {
  step_id: string;
  status: "running" | "done" | "error";
  variant?: VariantName;
  file_name?: string;
  repeat?: number;
  from_cache?: boolean;
}

export async function fetchLabeledAnalyzerStatus(): Promise<LabeledAnalyzerStatus> {
  const { data } = await axios.get<LabeledAnalyzerStatus>(`${API_BASE}/labeled-analyzer/status`);
  return data;
}

export async function fetchLabeledAnalyzerSamples(): Promise<LabeledAnalyzerSample[]> {
  const { data } = await axios.get<LabeledAnalyzerSample[]>(`${API_BASE}/labeled-analyzer/samples`);
  return data;
}

export async function fetchLabeledEvaluationReport(): Promise<LabeledEvaluationReport | null> {
  try {
    const { data } = await axios.get<LabeledEvaluationReport>(`${API_BASE}/labeled-analyzer/report`);
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) return null;
    throw error;
  }
}

export function labeledAnalyzerSampleUrl(fileName: string): string {
  return `${API_BASE}/labeled-analyzer/samples/${encodeURIComponent(fileName)}/raw`;
}

export async function runLabeledEvaluationStream(
  options: {
    forceLive: boolean;
    repeats: number;
    sampleNames?: string[];
    signal?: AbortSignal;
  },
  callbacks: {
    onStep?: (event: LabeledStepEvent) => void;
    onComplete?: (report: LabeledEvaluationReport) => void;
    onError?: (message: string) => void;
  }
): Promise<void> {
  await fetchEventSource(`${API_BASE}/labeled-analyzer/evaluate/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      force_live: options.forceLive,
      repeats: options.repeats,
      sample_names: options.sampleNames,
    }),
    signal: options.signal,
    openWhenHidden: true,
    onmessage(event) {
      if (!event.event) return;
      try {
        const data = JSON.parse(event.data);
        if (event.event === "step") callbacks.onStep?.(data as LabeledStepEvent);
        else if (event.event === "complete") {
          callbacks.onComplete?.(data as LabeledEvaluationReport);
        } else if (event.event === "error") {
          callbacks.onError?.(data.error || "Evaluation failed.");
        }
      } catch (error) {
        callbacks.onError?.(String(error));
      }
    },
    onerror(error) {
      callbacks.onError?.(String(error));
      throw error;
    },
  });
}

export type LabelingDocumentRole = "training" | "evaluation";

export interface LabelingWorkspaceStatus {
  api_version: string;
  content_understanding_configured: boolean;
  host_storage_configured: boolean;
  storage_mode: "host-managed-temporary";
}

export interface LabelingAnalyzerState {
  status: "not_created" | "ready";
  analyzer_id: string;
  last_action?: "created" | "reused";
  training_documents?: number;
  staging?: string;
  updated_at?: string;
}

export interface LabelingProjectSummary {
  project_id: string;
  name: string;
  preset: "property-claim-form";
  base_analyzer_id: string;
  trained_analyzer_id: string;
  analyzers: Record<"base" | "trained", LabelingAnalyzerState>;
  document_count: number;
  training_count: number;
  evaluation_count: number;
  reviewed_count: number;
  updated_at: string;
}

export interface LabelingDocumentSummary {
  document_id: string;
  file_name: string;
  role: LabelingDocumentRole;
  status: "uploaded" | "ready_for_labeling" | "auto_labeled" | "draft" | "reviewed";
  reviewed: boolean;
  labeled_fields: number;
  grounded_fields: number;
  total_fields: number;
}

export interface LabelFieldDefinition {
  type: "string" | "date" | "time" | "number" | "integer" | "boolean";
  method: "extract";
  description: string;
}

export interface EditableLabel {
  type: LabelFieldDefinition["type"];
  value: string | number | boolean | null;
  auto_value: string | number | boolean | null;
  confidence: number | null;
  source: string | null;
  spans: Array<{ offset: number; length: number }>;
  kind: "confirmed" | "corrected";
}

export interface LabelingProject extends Omit<LabelingProjectSummary, "document_count" | "training_count" | "evaluation_count" | "reviewed_count"> {
  schema_version: number;
  field_schema: {
    name: string;
    description: string;
    fields: Record<string, LabelFieldDefinition>;
  };
  documents: LabelingDocumentSummary[];
  summary: LabelingProjectSummary;
  evaluation?: LabelingEvaluationReport | null;
  last_evaluation?: LabelingEvaluationReport["summary"] & { generated_at: string };
}

export interface LabelingDocument extends Omit<LabelingDocumentSummary, "labeled_fields" | "grounded_fields" | "total_fields"> {
  labels: Record<string, EditableLabel>;
  markdown: string;
  auto_label_analyzer_id?: string;
  created_at: string;
  updated_at: string;
}

export interface LabelingScoreValue {
  actual: unknown;
  confidence: number | null;
  correct: boolean;
  source?: string | null;
}

export interface LabelingEvaluationReport {
  generated_at: string;
  project_id: string;
  training_documents: number;
  evaluation_documents: number;
  zero_shot_analyzer_id: string;
  labeled_analyzer_id: string;
  summary: {
    zero_shot_accuracy: number;
    labeled_accuracy: number;
    accuracy_delta_points: number;
  };
  documents: Record<
    string,
    {
      file_name: string;
      fields: Array<{
        field_name: string;
        expected: unknown;
        zero_shot: LabelingScoreValue;
        labeled: LabelingScoreValue;
      }>;
    }
  >;
}

export async function fetchLabelingWorkspaceStatus(): Promise<LabelingWorkspaceStatus> {
  const { data } = await axios.get<LabelingWorkspaceStatus>(`${API_BASE}/labeled-analyzer/workspace/status`);
  return data;
}

export async function fetchLabelingProjects(): Promise<LabelingProjectSummary[]> {
  const { data } = await axios.get<LabelingProjectSummary[]>(`${API_BASE}/labeled-analyzer/projects`);
  return data;
}

export async function createLabelingProject(
  name: string,
  analyzerId: string
): Promise<LabelingProjectSummary> {
  const { data } = await axios.post<LabelingProjectSummary>(`${API_BASE}/labeled-analyzer/projects`, {
    name,
    analyzer_id: analyzerId,
  });
  return data;
}

export async function fetchLabelingProject(projectId: string): Promise<LabelingProject> {
  const { data } = await axios.get<LabelingProject>(`${API_BASE}/labeled-analyzer/projects/${projectId}`);
  return data;
}

export async function uploadLabelingDocuments(
  projectId: string,
  files: File[],
  role: LabelingDocumentRole
): Promise<LabelingDocumentSummary[]> {
  const form = new FormData();
  form.append("role", role);
  files.forEach((file) => form.append("files", file));
  const { data } = await axios.post<LabelingDocumentSummary[]>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/documents`,
    form
  );
  return data;
}

export async function fetchLabelingDocument(
  projectId: string,
  documentId: string
): Promise<LabelingDocument> {
  const { data } = await axios.get<LabelingDocument>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/documents/${documentId}`
  );
  return data;
}

export function labelingDocumentUrl(projectId: string, documentId: string): string {
  return `${API_BASE}/labeled-analyzer/projects/${projectId}/documents/${documentId}/file`;
}

export async function prepareLabelingDocument(
  projectId: string,
  documentId: string
): Promise<LabelingDocument> {
  const { data } = await axios.post<LabelingDocument>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/documents/${documentId}/prepare`
  );
  return data;
}

export async function autoLabelDocument(
  projectId: string,
  documentId: string,
  analyzerId?: string
): Promise<LabelingDocument> {
  const { data } = await axios.post<LabelingDocument>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/documents/${documentId}/autolabel`,
    { analyzer_id: analyzerId || null }
  );
  return data;
}

export async function saveLabelingDocument(
  projectId: string,
  documentId: string,
  labels: Record<string, Pick<EditableLabel, "value" | "source" | "spans">>,
  reviewed: boolean
): Promise<LabelingDocument> {
  const { data } = await axios.put<LabelingDocument>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/documents/${documentId}/labels`,
    { labels, reviewed }
  );
  return data;
}

export async function createBaseAnalyzer(projectId: string): Promise<LabelingAnalyzerState> {
  const { data } = await axios.post<LabelingAnalyzerState>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/analyzers/base`
  );
  return data;
}

export async function buildLearnedAnalyzer(projectId: string): Promise<LabelingAnalyzerState> {
  const { data } = await axios.post<LabelingAnalyzerState>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/analyzers/trained`
  );
  return data;
}

export async function scoreLabelingProject(projectId: string): Promise<LabelingEvaluationReport> {
  const { data } = await axios.post<LabelingEvaluationReport>(
    `${API_BASE}/labeled-analyzer/projects/${projectId}/score`
  );
  return data;
}

export async function exportLabelingProject(projectId: string): Promise<void> {
  const response = await axios.get<Blob>(`${API_BASE}/labeled-analyzer/projects/${projectId}/export`, {
    responseType: "blob",
  });
  const disposition = response.headers["content-disposition"] || "";
  const fileName = disposition.match(/filename="?([^";]+)"?/)?.[1] || `${projectId}-labeled-data.zip`;
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}