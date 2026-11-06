import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, test } from "@jest/globals";
import ClaimsPage from "./ClaimsPage";
import {
  fetchClaim, fetchClaimFile,
  fetchClaims, fetchClaimRun, runClaims, searchClaim,
} from "../services/claimsService";

jest.mock("../services/claimsService", () => ({
  ...jest.requireActual("../services/claimsService"),
  fetchClaims: jest.fn(), fetchClaim: jest.fn(), fetchClaimFile: jest.fn(),
  fetchClaimRun: jest.fn(), runClaims: jest.fn(), searchClaim: jest.fn(),
}));
jest.mock("../Components/Sec/SourcePdfViewer", () => () => <div>PDF preview</div>);
jest.mock("react-markdown", () => ({ children }) => <div>{children}</div>);
jest.mock("remark-gfm", () => () => undefined);
jest.mock("@fluentui/react-icons", () => jest.requireActual("@fluentui/react-icons/lib-cjs/index.js"));
jest.mock("@fluentui/react-icons/lib/providers", () => jest.requireActual("@fluentui/react-icons/lib-cjs/providers.js"));
jest.mock("axios", () => ({ isAxiosError: () => false }));
jest.mock("react-toastify", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("../Components/Claims/ClaimsAgentChat", () => ({ initialClaim }) => <div>Local agent chat {initialClaim || "claim picker"}</div>);
jest.mock("reactflow", () => ({
  __esModule: true,
  default: ({ nodes, nodeTypes }) => <div data-testid="execution-graph">{nodes.map(node => {
    const Component = nodeTypes[node.type];
    return <Component key={node.id} data={node.data} type={node.type} />;
  })}</div>,
  ReactFlowProvider: ({ children }) => children,
  Handle: () => null, Controls: () => null, MiniMap: () => null, Background: () => null,
  BackgroundVariant: { Dots: "dots" }, Position: { Left: "left", Right: "right", Top: "top", Bottom: "bottom" },
  MarkerType: { ArrowClosed: "arrowclosed" },
}));

const chunk = {
  id: "chunk-1", claim_id: "claim-001", document_hash: "photo-1", chunk_id: 1,
  title: "Roof photo", header: "Visual observation", content: "Bent roof panels under a blue tarp.",
  source_type: "image", content_kind: "image_description", filename: "damage-01.jpg",
  source_path: "local", source_files: ["claim-001/damage-01.jpg"],
  parent_emails: [], figure_id: "", source_region: "", analyzer_id: "prebuilt-imageSearch",
  analyzer_api_version: "2025-11-01", vector_dimensions: 3072,
};
const detail = {
  claim_id: "claim-001", original_files: 1, chunks: [chunk], skipped: [],
  stale_chunks: 0, duplicate_occurrences: 0,
  stages: { files: true, extract: true, chunks: true, embed: true, index: false },
  files: [{
    id: "photo-1", filename: "damage-01.jpg", source_type: "image",
    source_files: chunk.source_files, parent_emails: [], bytes: 1024,
    analyzer_id: "prebuilt-imageSearch", extracted: true, chunks: 1,
    embedded: true, uploaded: false, text: "", attachment_only: false,
  }],
};
const overview = {
  claims: [{ claim_id: "claim-001", original_files: 1, evidence_files: 1, chunks: 1,
    stages: detail.stages, cover_id: "photo-1", stale_chunks: 0 }],
  index_name: "claims-evidence-v1", output_root: "local", job: null,
};

let host;
let root;
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

async function click(label) {
  const button = Array.from(document.querySelectorAll("button"))
    .find(item => item.textContent?.includes(label));
  if (!button) throw new Error(`Missing button: ${label}`);
  await act(async () => { button.click(); });
}

beforeEach(async () => {
  jest.clearAllMocks();
  jest.mocked(fetchClaims).mockResolvedValue(overview);
  jest.mocked(fetchClaimRun).mockResolvedValue(null);
  jest.mocked(fetchClaim).mockResolvedValue(detail);
  jest.mocked(fetchClaimFile).mockResolvedValue({
    file: detail.files[0], native_text: chunk.content, chunks: [chunk],
  });
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(<ClaimsPage />); });
});

afterEach(async () => {
  await act(async () => { root.unmount(); });
  jest.useRealTimers();
  host.remove();
});

test("opens a real-data-shaped folder, file preview and full chunk without processing", async () => {
  await click("Claim 001");
  await click("damage-01.jpg");
  expect(document.querySelector('img[alt="damage-01.jpg"]')).not.toBeNull();
  await click("Native extraction");
  expect(document.body.textContent).toContain(chunk.content);
  await click("Chunks");
  await click("Roof photo");
  expect(document.body.textContent).toContain("3072 vector dimensions");
  expect(document.body.textContent).toContain("Source trail");
  expect(runClaims).not.toHaveBeenCalled();
});

test("opening and dismissing the bulk-run confirmation never starts a paid run", async () => {
  await click("Process all folders");
  expect(document.body.textContent).toContain("New analysis and embeddings incur Azure usage");
  expect(document.querySelector('input[type="checkbox"]')?.checked).toBe(false);
  await click("Not now");
  expect(runClaims).not.toHaveBeenCalled();
});

test("agent chat is available from the main gallery and inherits a selected folder when opened there", async () => {
  await click("Chat with claims");
  expect(document.body.textContent).toContain("Local agent chat claim picker");
  const close = document.querySelector('button[aria-label="Close detail"]');
  await act(async () => { close.click(); });
  await click("Claim 001");
  await click("Chat with claims");
  expect(document.body.textContent).toContain("Local agent chat claim-001");
  expect(runClaims).not.toHaveBeenCalled();
});

test("each folder run starts with native image routing instead of retaining old scan overrides", async () => {
  await click("Claim 001");
  await click("Process this folder");
  const override = Array.from(document.querySelectorAll('input[type="checkbox"]')).at(-1);
  if (!override) throw new Error("Missing image scan override");
  await act(async () => { override.click(); });
  expect(document.body.textContent).toContain("(1 overrides)");
  await click("Not now");
  await click("Process this folder");
  expect(document.body.textContent).toContain("(0 overrides)");
  expect(Array.from(document.querySelectorAll('input[type="checkbox"]')).every(input => !input.checked)).toBe(true);
  expect(runClaims).not.toHaveBeenCalled();
});

test("the added execution popup unfolds files and chunks and preserves the tree on detail return", async () => {
  await click("Claim 001");
  await click("Execution tree");
  expect(document.body.textContent).toContain("COLLAPSED EXECUTION PATH");
  await click("Expand path");
  expect(document.body.textContent).toContain("PROCESSING APPROACH");
  await click("Image summary");
  expect(document.body.textContent).toContain(chunk.content);
  expect(document.body.textContent).toContain("Back to execution tree");
  await click("Back to execution tree");
  expect(document.body.textContent).toContain("PROCESSING APPROACH");
  await click("Unfold chunk branches");
  await click("Chunk 1: Roof photo");
  expect(document.body.textContent).toContain("Inside the chunk");
  expect(document.body.textContent).toContain(chunk.content);
  await click("Back to execution tree");
  expect(document.body.textContent).toContain("Chunk 1: Roof photo");
  await click("Recorded chronology");
  expect(document.body.textContent).toContain("Timestamps and durations were not recorded");
  expect(runClaims).not.toHaveBeenCalled();
});

test("a claim question uses the selected claim and opens source-linked semantic results", async () => {
  jest.mocked(searchClaim).mockResolvedValue([
    { ...chunk, semantic_score: 2.7, score: 0.03, caption: "Bent roof panels." },
  ]);
  await click("Claim 001");
  await click("Ask this claim");
  const form = document.querySelector("form");
  if (!form) throw new Error("Missing claim search form");
  await act(async () => { form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
  expect(searchClaim).toHaveBeenCalledWith("claim-001", "What are we still waiting on to move this claim forward?");
  expect(document.body.textContent).toContain("2.70 semantic");
  await click("Roof photo");
  expect(document.body.textContent).toContain(chunk.content);
});

test("an idle tab replaces a saved failure with a run started elsewhere and reconnects after a poll error", async () => {
  await act(async () => { root.unmount(); });
  jest.useFakeTimers();
  const failed = {
    id: "old-run", status: "failed", claim_ids: ["claim-001"], claim_id: "claim-001",
    stage: "extract", message: "Old Windows replacement error", index_data: true, events: [],
  };
  const running = {
    ...failed, id: "new-run", status: "running", claim_ids: ["claim-002"], claim_id: "claim-002",
    message: "Analyzing inspection.pdf",
  };
  jest.mocked(fetchClaims).mockResolvedValue({ ...overview, job: failed });
  root = createRoot(host);
  await act(async () => { root.render(<ClaimsPage />); });
  expect(document.querySelector(".ce-run-strip").textContent).toContain("Last run stopped");

  jest.mocked(fetchClaimRun).mockResolvedValue(running);
  jest.mocked(fetchClaims).mockResolvedValue({ ...overview, job: running });
  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(document.querySelector(".ce-run-strip").textContent).toContain("ProcessingClaim 002");
  expect(document.body.textContent).not.toContain("Old Windows replacement error");
  expect(runClaims).not.toHaveBeenCalled();

  jest.mocked(fetchClaimRun).mockRejectedValueOnce(new Error("Disconnected"));
  await act(async () => { jest.advanceTimersByTime(1200); });
  expect(document.body.textContent).toContain("Reconnecting automatically");
  await act(async () => { jest.advanceTimersByTime(5000); });
  expect(document.body.textContent).not.toContain("Progress connection lost:");
  expect(document.querySelector(".ce-run-strip").textContent).toContain("ProcessingClaim 002");
});
