import axios from "axios";
import type { CostBreakdown } from "./sovService";

const API_BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

export interface PrebuiltAnalyzer {
  id: string;
  name: string;
  description: string;
  source: "di" | "cu";
  category?: string;
}

export interface ApiVersionEntry {
  value: string;
  label: string;
}

export interface ApiVersions {
  di: ApiVersionEntry[];
  cu: ApiVersionEntry[];
}

export interface AnalyzerResult {
  analyzer_id: string;
  status: "succeeded" | "failed";
  result: Record<string, unknown> | null;
  error: string | null;
  api_version?: string;
  elapsed_ms?: number;
  cost?: CostBreakdown | null;
}

export interface CompareResponse {
  file_name: string;
  results: AnalyzerResult[];
  cost?: CostBreakdown;
}

export async function fetchPrebuiltAnalyzers(): Promise<PrebuiltAnalyzer[]> {
  const resp = await axios.get<PrebuiltAnalyzer[]>(
    `${API_BASE}/analyzer-compare/analyzers`
  );
  return resp.data;
}

export async function fetchApiVersions(): Promise<ApiVersions> {
  const resp = await axios.get<ApiVersions>(
    `${API_BASE}/analyzer-compare/api-versions`
  );
  return resp.data;
}

export async function compareAnalyzers(
  file: File,
  analyzerIds: string[],
  diApiVersion?: string,
  cuApiVersion?: string,
): Promise<CompareResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("analyzer_ids", analyzerIds.join(","));
  if (diApiVersion) form.append("di_api_version", diApiVersion);
  if (cuApiVersion) form.append("cu_api_version", cuApiVersion);

  const resp = await axios.post<CompareResponse>(
    `${API_BASE}/analyzer-compare/analyze`,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return resp.data;
}
