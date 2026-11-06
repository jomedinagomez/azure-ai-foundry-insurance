import axios from "axios";

const BASE = (process.env.REACT_APP_API_BASE_URL || "").replace(/\/$/, "");

export interface ClaimActivity {
  activity_id: string;
  title: string;
  status: "open" | "awaiting_external" | "completed";
  owner_team: string;
  priority: "normal" | "high";
  blocking: boolean;
  due_date: string;
  completed_at: string | null;
  source_refs: string[];
  overdue_as_of_snapshot: boolean;
  currently_blocking: boolean;
}

export interface ClaimPayment {
  payment_id: string;
  kind: "expense" | "indemnity";
  status: "posted" | "pending" | "voided";
  payee: string;
  amount: string;
  purpose: string;
  created_at: string;
  updated_at: string;
  posted_at: string | null;
}

export interface OperationalClaim {
  claim_id: string;
  claim_number: string;
  insured_name: string;
  line_of_business: string;
  reported_loss: string;
  loss_date: string;
  status: "open" | "closed";
  phase: string;
  assigned_adjuster: string;
  assigned_team: string;
  updated_at: string;
  coverage_decision: string;
  policy: {
    policy_number: string; effective_from: string; effective_to: string;
    currency: string; specimen_limit: string; specimen_deductible: string; source_ref: string;
  };
  financials: {
    currency: string; outstanding_indemnity_reserve: string; outstanding_expense_reserve: string;
    outstanding_reserve_total: string; paid_indemnity_total: string; paid_expense_total: string;
    paid_total: string; incurred_total: string; pending_payment_total: string; voided_request_total: string;
    approved_settlement_amount: string | null; payments: ClaimPayment[]; definitions: Record<string, string>;
  };
  activities: ClaimActivity[];
  log_notes: {
    note_id: string; recorded_at: string; author_role: string; category: string;
    text: string; activity_id: string | null; source_refs: string[];
  }[];
}

export interface OperationalSnapshot {
  metadata: {
    synthetic: true; source_system: string; implementation: string; schema_version: string;
    as_of: string; currency_values: string; caveat: string;
  };
  data: OperationalClaim;
}

export const structuredClaimUrl = (claimId: string) => `${BASE}/claims-operations/claims/${encodeURIComponent(claimId)}`;
export const fetchStructuredClaim = async (claimId: string) =>
  (await axios.get<OperationalSnapshot>(structuredClaimUrl(claimId))).data;

export function usd(value: string): string {
  const [whole, fraction = "00"] = value.split(".");
  return `USD ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;
}
