import axios from "axios";

const BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");
const AGENT = `${BASE}/claims-agent`;

export interface ClaimsAgentStatus {
  name: string;
  version: string | null;
  model: string;
  project_endpoint: string;
  project_portal_url?: string;
  runtime: string;
  registered: boolean;
  telemetry_configured: boolean;
  message: string;
}

export interface AgentCitation {
  id: string;
  kind: "document" | "structured";
  title: string;
  claim_id: string;
  excerpt: string;
  document_hash?: string;
  source_files?: string[];
  as_of?: string;
}

export interface AgentStep {
  id: string;
  kind: "model" | "tool";
  name: string;
  status: "complete" | "failed";
  started_at: string;
  elapsed_ms: number;
  arguments?: Record<string, unknown>;
  result?: unknown;
  error?: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
}

export interface AgentTurn {
  id: string;
  question: string;
  answer: string | null;
  status: "running" | "complete" | "failed";
  error: string | null;
  created_at: string;
  trace_id: string | null;
  steps: AgentStep[];
  citations: AgentCitation[];
  telemetry_status: string;
  elapsed_ms: number | null;
}

export interface AgentConversation {
  id: string;
  claim_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  agent_name: string;
  agent_version: string;
  turns: AgentTurn[];
}

export const fetchClaimsAgentStatus = async () => (await axios.get<ClaimsAgentStatus>(`${AGENT}/status`)).data;
export const registerClaimsAgent = async () => (await axios.post<ClaimsAgentStatus>(`${AGENT}/register`)).data;
export const listAgentConversations = async (claimId: string) =>
  (await axios.get<AgentConversation[]>(`${AGENT}/conversations`, { params: { claim_id: claimId } })).data;
export const createAgentConversation = async (claimId: string) =>
  (await axios.post<AgentConversation>(`${AGENT}/conversations`, { claim_id: claimId })).data;
export const fetchAgentConversation = async (id: string) =>
  (await axios.get<AgentConversation>(`${AGENT}/conversations/${encodeURIComponent(id)}`)).data;
export const sendAgentMessage = async (id: string, question: string) =>
  (await axios.post<AgentConversation>(`${AGENT}/conversations/${encodeURIComponent(id)}/messages`, { question }, { timeout: 240000 })).data;

export interface CloudTraceEvidence {
  trace_id: string;
  verified: boolean;
  span_count: number;
  query: string;
  spans: Record<string, unknown>[];
  message: string;
}
export const verifyAgentTrace = async (conversationId: string, turnId: string) =>
  (await axios.get<CloudTraceEvidence>(`${AGENT}/conversations/${encodeURIComponent(conversationId)}/turns/${encodeURIComponent(turnId)}/cloud-trace`)).data;
