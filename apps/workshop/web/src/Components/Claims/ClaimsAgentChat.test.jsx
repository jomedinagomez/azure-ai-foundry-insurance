import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test } from "@jest/globals";
import ClaimsAgentChat from "./ClaimsAgentChat";
import {
  createAgentConversation, fetchAgentConversation, fetchClaimsAgentStatus,
  listAgentConversations, registerClaimsAgent, sendAgentMessage, verifyAgentTrace,
} from "../../services/claimsAgentService";

jest.mock("../../services/claimsAgentService", () => ({
  fetchClaimsAgentStatus: jest.fn(), listAgentConversations: jest.fn(),
  createAgentConversation: jest.fn(), fetchAgentConversation: jest.fn(),
  registerClaimsAgent: jest.fn(), sendAgentMessage: jest.fn(), verifyAgentTrace: jest.fn(),
}));
jest.mock("react-markdown", () => ({ children }) => <div>{children}</div>);
jest.mock("remark-gfm", () => () => undefined);
jest.mock("axios", () => ({ isAxiosError: () => false }));
jest.mock("@fluentui/react-icons", () => jest.requireActual("@fluentui/react-icons/lib-cjs/index.js"));
jest.mock("@fluentui/react-icons/lib/providers", () => jest.requireActual("@fluentui/react-icons/lib-cjs/providers.js"));

const registered = {
  name: "claims-local-assistant", version: "1", model: "gpt-5.2", registered: true,
  project_endpoint: "https://example.services.ai.azure.com/api/projects/claims", telemetry_configured: true,
};
const empty = {
  id: "c1", claim_id: "claim-001", title: "New conversation", agent_name: registered.name,
  agent_version: "1", created_at: "2026-11-06T08:00:00Z", updated_at: "2026-11-06T08:00:00Z", turns: [],
};
const turn = {
  id: "t1", question: "What is still outstanding?", answer: "The evidence is outstanding [D1] and the synthetic reserve is USD 25,000.00 [S1].",
  status: "complete", error: null, trace_id: "a".repeat(32), elapsed_ms: 1000,
  telemetry_status: "Telemetry flushed; cloud ingestion is not yet verified.",
  steps: [{ id: "s1", kind: "tool", name: "get_structured_claim", status: "complete", elapsed_ms: 200,
    started_at: "2026-11-06T08:00:00Z", arguments: {}, result: { synthetic: true, paid_total: "375.00" } }],
  citations: [
    { id: "D1", kind: "document", claim_id: "claim-001", title: "inspection.pdf · chunk 1", excerpt: "Missing diagnostic evidence.", source_files: ["claim-001/inspection.pdf"] },
    { id: "S1", kind: "structured", claim_id: "claim-001", title: "System records", excerpt: "USD 25,000.00 reserve", as_of: "2026-11-05T18:00:00Z" },
  ],
};
let host;
let root;
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

async function click(label) {
  const button = Array.from(document.querySelectorAll("button")).find(item => item.textContent?.includes(label));
  if (!button) throw new Error(`Missing button: ${label}`);
  await act(async () => { button.click(); });
}
async function typeQuestion(text) {
  const input = document.querySelector("textarea");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set.call(input, text);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

beforeEach(async () => {
  jest.clearAllMocks();
  jest.mocked(fetchClaimsAgentStatus).mockResolvedValue(registered);
  jest.mocked(listAgentConversations).mockResolvedValue([]);
  jest.mocked(createAgentConversation).mockResolvedValue(empty);
  jest.mocked(fetchAgentConversation).mockResolvedValue(empty);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(<ClaimsAgentChat claims={[{ claim_id: "claim-001" }, { claim_id: "claim-002" }]} />); });
});
afterEach(async () => {
  await act(async () => { root.unmount(); });
  host.remove();
});

test("main chat opens without remote registration or a model call and starts a claim-bound conversation explicitly", async () => {
  expect(registerClaimsAgent).not.toHaveBeenCalled();
  expect(sendAgentMessage).not.toHaveBeenCalled();
  expect(document.body.textContent).toContain("Runs locally");
  await click("New conversation");
  expect(createAgentConversation).toHaveBeenCalledWith("claim-001");
  expect(document.body.textContent).toContain("Ready for Claim 001");
});

test("a completed answer exposes real tool trace, source details and explicit cloud verification", async () => {
  jest.mocked(sendAgentMessage).mockResolvedValue({ ...empty, turns: [turn] });
  jest.mocked(verifyAgentTrace).mockResolvedValue({ verified: true, span_count: 4, message: "Cloud spans observed", query: "Exact KQL", spans: [] });
  await click("New conversation");
  await typeQuestion(turn.question);
  await click("Send");
  expect(sendAgentMessage).toHaveBeenCalledWith("c1", turn.question);
  expect(document.body.textContent).toContain(turn.answer);
  expect(document.body.textContent).toContain("get_structured_claim");
  expect(document.body.textContent).toContain("cloud ingestion is not yet verified");
  await click("Verify cloud trace");
  expect(verifyAgentTrace).toHaveBeenCalledWith("c1", "t1");
  expect(document.body.textContent).toContain("4 cloud spans observed");
  await click("[D1]");
  expect(document.body.textContent).toContain("Missing diagnostic evidence.");
});

test("a failed invocation remains an error with no assistant answer", async () => {
  jest.mocked(sendAgentMessage).mockResolvedValue({ ...empty, turns: [
    { ...turn, status: "failed", answer: null, error: "Search permission denied", citations: [] },
  ] });
  await click("New conversation");
  await typeQuestion("What is outstanding?");
  await click("Send");
  expect(document.body.textContent).toContain("This turn did not complete");
  expect(document.body.textContent).toContain("Search permission denied");
  expect(document.body.textContent).not.toContain("The evidence is outstanding [D1]");
});

test("changing claim scopes clears the active conversation rather than reusing its evidence", async () => {
  await click("New conversation");
  const picker = document.querySelector('select[aria-label="Chat claim scope"]');
  await act(async () => { picker.value = "claim-002"; picker.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(listAgentConversations).toHaveBeenCalledWith("claim-002");
  expect(document.body.textContent).not.toContain("Ready for Claim 001");
  expect(document.querySelector('button[type="submit"]').disabled).toBe(true);
});

test("registration is an explicit action and does not masquerade as hosted execution", async () => {
  await act(async () => { root.unmount(); });
  jest.mocked(fetchClaimsAgentStatus).mockResolvedValue({ ...registered, version: null, registered: false });
  jest.mocked(registerClaimsAgent).mockResolvedValue(registered);
  root = createRoot(host);
  await act(async () => { root.render(<ClaimsAgentChat claims={[{ claim_id: "claim-001" }]} />); });
  expect(document.body.textContent).toContain("metadata-only external-agent version");
  expect(createAgentConversation).not.toHaveBeenCalled();
  await click("Register agent");
  expect(registerClaimsAgent).toHaveBeenCalledTimes(1);
  expect(document.body.textContent).toContain("Registered for tracing");
});
