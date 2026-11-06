import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test } from "@jest/globals";
import ClaimOperationsPanel from "./ClaimOperationsPanel";
import { fetchStructuredClaim, usd } from "../../services/claimOperationsService";

jest.mock("../../services/claimOperationsService", () => ({
  ...jest.requireActual("../../services/claimOperationsService"), fetchStructuredClaim: jest.fn(),
}));
jest.mock("axios", () => ({ isAxiosError: () => false }));
jest.mock("@fluentui/react-icons", () => jest.requireActual("@fluentui/react-icons/lib-cjs/index.js"));
jest.mock("@fluentui/react-icons/lib/providers", () => jest.requireActual("@fluentui/react-icons/lib-cjs/providers.js"));

const response = {
  metadata: { synthetic: true, source_system: "simulated_databricks_genie",
    implementation: "local_read_only_api", as_of: "2026-11-05T18:00:00Z",
    caveat: "Synthetic operational snapshot, not a real Databricks/Genie response or a coverage decision." },
  data: {
    claim_id: "claim-001", claim_number: "AV-26-004181", insured_name: "Cedar Quay Warehousing LLC",
    line_of_business: "commercial_property", loss_date: "2026-09-12", status: "open",
    phase: "evidence_collection", assigned_adjuster: "Alex Rowan", assigned_team: "Commercial Property East",
    coverage_decision: "under_review",
    policy: { policy_number: "AV-CP-260101", effective_from: "2026-01-01", effective_to: "2026-12-31",
      specimen_limit: "500000.00", specimen_deductible: "2500.00", source_ref: "claim-001/policy.pdf" },
    financials: {
      outstanding_reserve_total: "25000.00", paid_total: "375.00", paid_indemnity_total: "0.00",
      paid_expense_total: "375.00", pending_payment_total: "1200.00", voided_request_total: "0.00",
      incurred_total: "25375.00", approved_settlement_amount: null, definitions: { paid_total: "Posted payments only." },
      payments: [{ payment_id: "PAY-001-02", kind: "indemnity", status: "pending", amount: "1200.00",
        payee: "Cedar Quay Warehousing LLC", purpose: "Mitigation invoice review pending", posted_at: null }],
    },
    activities: [{ activity_id: "ACT-001-01", title: "Obtain corroboration for the incident time",
      status: "awaiting_external", owner_team: "Commercial Property East", priority: "high",
      due_date: "2026-11-04", completed_at: null, currently_blocking: true,
      overdue_as_of_snapshot: true, source_refs: ["claim-001/incident-report-scan.pdf"] }],
    log_notes: [{ note_id: "NOTE-001-03", recorded_at: "2026-11-05T16:30:00Z",
      author_role: "Claims financial analyst", category: "financial",
      text: "The mitigation request has not posted. No settlement amount is approved.",
      activity_id: "ACT-001-01", source_refs: [] }],
  },
};

let host;
let root;
let openEvidence;
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

async function click(label) {
  const button = Array.from(document.querySelectorAll("button")).find(item => item.textContent?.includes(label));
  if (!button) throw new Error(`Missing button: ${label}`);
  await act(async () => { button.click(); });
}

beforeEach(async () => {
  jest.clearAllMocks();
  jest.mocked(fetchStructuredClaim).mockResolvedValue(response);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  openEvidence = jest.fn();
  await act(async () => { root.render(<ClaimOperationsPanel claimId="claim-001" onOpenEvidence={openEvidence} />); });
});

afterEach(async () => {
  await act(async () => { root.unmount(); });
  host.remove();
});

test("shows explicit simulation provenance, exact financial values and snapshot-based blockers", () => {
  expect(fetchStructuredClaim).toHaveBeenCalledWith("claim-001");
  expect(document.body.textContent).toContain("Simulated Genie");
  expect(document.body.textContent).toContain("not the document Search index");
  expect(document.body.textContent).toContain("USD 25,000.00");
  expect(document.body.textContent).toContain("USD 375.00");
  expect(document.body.textContent).toContain("Overdue at snapshot");
  expect(document.body.textContent).toContain("none recorded (not zero)");
});

test("keeps a pending request distinct from posted paid totals", async () => {
  await click("Financial ledger");
  expect(document.body.textContent).toContain("Pending requests: USD 1,200.00");
  expect(document.body.textContent).toContain("Paid expenses: USD 375.00");
  expect(document.body.textContent).toContain("Not posted");
  expect(document.body.textContent).toContain("pending");
});

test("opens evidence references and renders complete dated log notes", async () => {
  await click("incident-report-scan.pdf");
  expect(openEvidence).toHaveBeenCalledWith("claim-001/incident-report-scan.pdf");
  await click("Log notes");
  expect(document.body.textContent).toContain("NOTE-001-03");
  expect(document.body.textContent).toContain(response.data.log_notes[0].text);
  expect(document.body.textContent).toContain("ACT-001-01");
});

test("shows API failures explicitly and retries the local data read", async () => {
  jest.mocked(fetchStructuredClaim).mockRejectedValueOnce(new Error("Dataset unavailable"));
  await click("Refresh records");
  expect(document.querySelector('[role="alert"]').textContent).toContain("Dataset unavailable");
  expect(document.body.textContent).not.toContain("USD 0.00");
  await click("Retry");
  expect(document.body.textContent).toContain(response.data.claim_number);
});

test("currency display preserves exact decimal strings", () => {
  expect(usd("0.10")).toBe("USD 0.10");
  expect(usd("1000000.00")).toBe("USD 1,000,000.00");
});
