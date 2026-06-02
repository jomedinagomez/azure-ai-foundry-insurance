import axios from "axios";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { apiUrl, formatCost as formatCostShared, CostBreakdown } from "./sovService";

export { apiUrl };
export type { CostBreakdown };
export const formatCost = formatCostShared;

const API_BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

export interface SecSample {
  file_name: string;
  file_type: "pdf";
  size_kb: number;
  has_cached_result: boolean;
  has_ground_truth: boolean;
}

export type StatementType =
  | "BalanceSheet"
  | "IncomeStatement"
  | "ComprehensiveIncome"
  | "Equity"
  | "CashFlow"
  | "Other";

export interface SecLineItem {
  line_item: string;
  level: number;
  is_section_header: boolean;
  is_subtotal: boolean;
  values: string[];
  value_confidences?: (number | null)[] | null;
  confidence?: number | null;
}

export interface SecStatement {
  statement_type: StatementType;
  table_title: string;
  company_name: string;
  unit: string;
  period_headers: string[];
  period_groups: string[];
  rows: SecLineItem[];
  source_category?: string | null;
  page_start?: number | null;
  page_end?: number | null;
}

export interface SecExtractionMeta {
  source_file: string;
  classifier_id?: string | null;
  analyzer_id?: string | null;
  elapsed_sec?: number | null;
  retries?: number;
  segment_categories?: Record<string, number>;
  missing_statements?: string[];
  from_cache?: boolean;
  run_id?: string | null;
  artifacts?: Record<string, string>;
  cost?: CostBreakdown | Record<string, never>;
  [key: string]: unknown;
}

export interface SecExtractionResult {
  file_name: string;
  meta: SecExtractionMeta;
  statements: SecStatement[];
  raw?: Record<string, unknown>;
}

export interface SecStepEvent {
  step_id: string;
  status: "running" | "done" | "error" | "pending";
  [key: string]: unknown;
}

export interface SecValidationStatementSummary {
  statement_type: StatementType;
  expected_rows: number;
  actual_rows: number;
  matched_rows: number;
  missing_rows: string[];
  extra_rows: string[];
}

export interface SecValidationResult {
  file_name: string;
  has_ground_truth: boolean;
  statements: SecValidationStatementSummary[];
  overall_match_rate: number;
}

export async function fetchSecSamples(): Promise<SecSample[]> {
  const { data } = await axios.get<SecSample[]>(`${API_BASE}/sec/samples`);
  return data;
}

export interface RunCallbacks {
  onStep?: (evt: SecStepEvent) => void;
  onComplete?: (result: SecExtractionResult) => void;
  onError?: (err: string) => void;
  signal?: AbortSignal;
}

export async function runSecExtractionStream(
  sampleName: string,
  opts: { useCache?: boolean; saveAsCanonical?: boolean } & RunCallbacks
): Promise<void> {
  const { onStep, onComplete, onError, signal } = opts;
  const body = JSON.stringify({
    sample_name: sampleName,
    use_cache: opts.useCache ?? true,
    save_as_canonical: opts.saveAsCanonical ?? false,
  });

  await fetchEventSource(`${API_BASE}/sec/extract/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    signal,
    openWhenHidden: true,
    onmessage(ev) {
      if (!ev.event) return;
      if (ev.event === "step") {
        try {
          onStep?.(JSON.parse(ev.data));
        } catch {
          /* ignore */
        }
      } else if (ev.event === "complete") {
        try {
          const env = JSON.parse(ev.data);
          onComplete?.(env.result as SecExtractionResult);
        } catch (e) {
          onError?.(String(e));
        }
      } else if (ev.event === "error") {
        try {
          const e = JSON.parse(ev.data);
          onError?.(e.error || "unknown error");
        } catch {
          onError?.(ev.data || "stream error");
        }
      }
    },
    onerror(err) {
      onError?.(String(err));
      throw err; // stop retry loop
    },
  });
}

export async function runSecExtraction(
  sampleName: string,
  opts: { useCache?: boolean; saveAsCanonical?: boolean } = {}
): Promise<SecExtractionResult> {
  const { data } = await axios.post<SecExtractionResult>(`${API_BASE}/sec/extract`, {
    sample_name: sampleName,
    use_cache: opts.useCache ?? true,
    save_as_canonical: opts.saveAsCanonical ?? false,
  });
  return data;
}

export async function runSecValidation(
  result: SecExtractionResult
): Promise<SecValidationResult> {
  const { data } = await axios.post<SecValidationResult>(`${API_BASE}/sec/validate`, {
    result,
  });
  return data;
}

export interface SaveExpectedResponse {
  written: string;
  bytes: number;
}

export async function saveSecExpected(
  result: SecExtractionResult
): Promise<SaveExpectedResponse> {
  const { data } = await axios.post<SaveExpectedResponse>(
    `${API_BASE}/sec/save-expected`,
    { result }
  );
  return data;
}

export function secSampleFileUrl(fileName: string): string {
  return `${API_BASE}/sec/samples/${encodeURIComponent(fileName)}/raw`;
}
