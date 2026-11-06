import axios from "axios";

const BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");
export const stages = ["files", "extract", "chunks", "embed", "index"] as const;
export type Stage = typeof stages[number];
export type StageState = Record<Stage, boolean>;

export interface ClaimSummary {
  claim_id: string;
  original_files: number;
  evidence_files: number;
  chunks: number;
  stages: StageState;
  cover_id: string | null;
  stale_chunks: number;
}

export interface EvidenceFile {
  id: string;
  filename: string;
  source_type: "document" | "image" | "email";
  source_files: string[];
  parent_emails: string[];
  bytes: number;
  analyzer_id: string;
  extracted: boolean;
  chunks: number;
  embedded: boolean;
  uploaded: boolean;
  text: string;
  attachment_only: boolean;
}

export interface EvidenceChunk {
  id: string;
  claim_id: string;
  document_hash: string;
  chunk_id: number;
  title: string;
  header: string;
  content: string;
  source_type: string;
  content_kind: string;
  filename: string;
  source_path: string;
  source_files: string[];
  parent_emails: string[];
  figure_id: string;
  source_region: string;
  analyzer_id: string;
  analyzer_api_version: string;
  vector_dimensions?: number;
  score?: number;
  semantic_score?: number;
  caption?: string;
}

export interface ClaimDetail {
  claim_id: string;
  original_files: number;
  files: EvidenceFile[];
  chunks: EvidenceChunk[];
  stages: StageState;
  skipped: { source: string; reason: string }[];
  stale_chunks: number;
  duplicate_occurrences: number;
}

export interface FileDetail {
  file: EvidenceFile;
  native_text: string;
  chunks: EvidenceChunk[];
}

export interface ClaimRun {
  id: string;
  status: "running" | "complete" | "failed";
  claim_ids: string[];
  claim_id: string;
  stage: Stage;
  message: string;
  index_data: boolean;
  events: { claim_id: string; stage: Stage; message: string; evidence_id: string; done: boolean }[];
}

export interface ClaimsOverview {
  claims: ClaimSummary[];
  index_name: string;
  output_root: string;
  job: ClaimRun | null;
}

export const fetchClaims = async () => (await axios.get<ClaimsOverview>(`${BASE}/claims`)).data;
export const fetchClaim = async (id: string) => (await axios.get<ClaimDetail>(`${BASE}/claims/${encodeURIComponent(id)}`)).data;
export const fetchClaimFile = async (id: string, file: string) =>
  (await axios.get<FileDetail>(`${BASE}/claims/${encodeURIComponent(id)}/files/${encodeURIComponent(file)}`)).data;
export const claimFileUrl = (id: string, file: string) =>
  `${BASE}/claims/${encodeURIComponent(id)}/files/${encodeURIComponent(file)}/raw`;
export const fetchClaimRun = async () => (await axios.get<ClaimRun | null>(`${BASE}/claims/run`)).data;
export const runClaims = async (ids: string[], indexData: boolean, documentImages: string[]) =>
  (await axios.post<ClaimRun>(`${BASE}/claims/run`, {
    claim_ids: ids, index_data: indexData, document_image_names: documentImages,
  })).data;
export const searchClaim = async (id: string, question: string) =>
  (await axios.post<EvidenceChunk[]>(`${BASE}/claims/${encodeURIComponent(id)}/search`, { question })).data;

export function claimsError(error: unknown): string {
  if (axios.isAxiosError<{ detail?: string }>(error)) {
    const detail = error.response?.data?.detail;
    return typeof detail === "string" ? detail : error.message;
  }
  return error instanceof Error ? error.message : String(error);
}
