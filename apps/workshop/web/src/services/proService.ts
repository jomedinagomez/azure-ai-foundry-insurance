import axios from "axios";

const API_BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

export function proApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (!path.startsWith("/")) path = "/" + path;
  return `${API_BASE}${path}`;
}

export type Scenario = "claims" | "fraud";
export type Severity = "low" | "medium" | "high";
export type RiskBand = "low" | "medium" | "high";

export interface ProSampleFile {
  name: string;
  kind: string;
  media_type: string;
  tampered?: boolean;
}

export interface ProSampleManifest {
  id: string;
  title: string;
  scenario: Scenario;
  loss_type: string;
  description: string;
  claimant?: string | null;
  policy_number?: string | null;
  vin?: string | null;
  vehicle?: string | null;
  files: ProSampleFile[];
  expected_signals: Array<{ rule_id: string; severity: Severity; evidence?: string }>;
  expected_risk_score_range?: [number, number] | null;
}

export interface FraudSignal {
  rule_id: string;
  severity: Severity;
  title: string;
  evidence: string;
  source_documents: string[];
  weight: number;
}

export interface ProMeta {
  sample_id?: string | null;
  scenario: Scenario;
  analyzer_id: string;
  api_version: string;
  elapsed_sec?: number | null;
  input_files: string[];
}

export interface ProClaimsFields {
  claimant_name?: string | null;
  policy_number?: string | null;
  vin?: string | null;
  date_of_loss?: string | null;
  loss_location?: string | null;
  incident_narrative?: string | null;
  estimated_total?: number | null;
  damage_visible_in_photo?: string | null;
  coverage_applies?: string | null;
  police_report_present?: string | null;
  document_set_completeness?: string | null;
  claims_handler_verdict?: string | null;
}

export interface ProFraudFields {
  vin_consistency?: string | null;
  vin_consistency_evidence?: string | null;
  policy_number_consistency?: string | null;
  claimant_name_consistency?: string | null;
  totals_vs_sub_limit?: string | null;
  totals_evidence?: string | null;
  estimate_date_vs_date_of_loss?: string | null;
  date_evidence?: string | null;
  narrative_image_consistency?: string | null;
  narrative_image_evidence?: string | null;
  overall_fraud_indication?: string | null;
  rationale?: string | null;
}

export interface ProClaimsResult {
  meta: ProMeta;
  fields: ProClaimsFields;
  raw: Record<string, unknown>;
}

export interface ProFraudResult {
  meta: ProMeta;
  fields: ProFraudFields;
  cu_signals: FraudSignal[];
  rule_signals: FraudSignal[];
  risk_score: number;
  risk_band: RiskBand;
  raw: Record<string, unknown>;
}

export interface ProHealthcheck {
  endpoint_configured: boolean;
  api_version: string;
  analyzers: Record<string, boolean>;
  samples_available: string[];
  pro_mode_supported?: boolean | null;
  error?: string | null;
}

export async function getHealth(): Promise<ProHealthcheck> {
  const r = await axios.get<ProHealthcheck>(proApiUrl("/pro/healthcheck"));
  return r.data;
}

export async function listSamples(): Promise<ProSampleManifest[]> {
  const r = await axios.get<ProSampleManifest[]>(proApiUrl("/pro/samples"));
  return r.data;
}

export function sampleFileUrl(sampleId: string, fileName: string): string {
  return proApiUrl(`/pro/samples/${encodeURIComponent(sampleId)}/files/${encodeURIComponent(fileName)}`);
}

export async function analyzeSample(
  sampleId: string,
  scenario: Scenario,
): Promise<ProClaimsResult | ProFraudResult> {
  const r = await axios.post(
    proApiUrl(`/pro/samples/${encodeURIComponent(sampleId)}/analyze`),
    null,
    { params: { scenario }, timeout: 300_000 },
  );
  return r.data;
}

export async function analyzeUpload(
  files: File[],
  scenario: Scenario,
): Promise<ProClaimsResult | ProFraudResult> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  const path = scenario === "claims" ? "/pro/claims/analyze" : "/pro/fraud/analyze";
  const r = await axios.post(proApiUrl(path), fd, { timeout: 300_000 });
  return r.data;
}

export async function deployAnalyzers(overwrite = false): Promise<Record<string, unknown>> {
  const r = await axios.post(proApiUrl("/pro/deploy"), null, { params: { overwrite } });
  return r.data;
}
