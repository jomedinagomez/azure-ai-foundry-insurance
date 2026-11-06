import { expect, test } from "@jest/globals";
import { buildExecutionTree, fileStageStatus, retainedEvents } from "./executionTreeModel";

const evidence = (id, filename, source_type, extra = {}) => ({
  id, filename, source_type, source_files: [`claim-001/${filename}`], parent_emails: [],
  bytes: 100, analyzer_id: source_type === "email" ? "local-msg" : source_type === "image" ? "prebuilt-imageSearch" : "prebuilt-documentSearch",
  extracted: false, chunks: 0, embedded: false, uploaded: false, text: "", attachment_only: false, ...extra,
});
const mail = evidence("mail", "notification.msg", "email", { extracted: true });
const photo = evidence("photo", "damage.jpg", "image", {
  parent_emails: ["mail"], source_files: ["claim-001/damage.jpg", "claim-001/notification.msg::damage.jpg"],
  extracted: true, chunks: 2, embedded: true,
});
const attachment = evidence("attachment", "authority.pdf", "document", {
  parent_emails: ["mail"], attachment_only: true, source_files: ["claim-001/notification.msg::authority.pdf"],
});
const nested = evidence("nested", "forwarded.msg", "email", {
  parent_emails: ["mail"], attachment_only: true, source_files: ["claim-001/notification.msg::forwarded.msg"],
});
const inner = evidence("inner", "inside.png", "image", {
  parent_emails: ["nested"], attachment_only: true,
  source_files: ["claim-001/notification.msg::forwarded.msg::inside.png"],
});
const chunks = [1, 2].map(number => ({
  id: `chunk-${number}`, claim_id: "claim-001", document_hash: "photo", chunk_id: number,
  title: "Damage photo", content: `Observation ${number}`, header: "Visual observation",
  content_kind: "image_description", vector_dimensions: 3072,
}));
const detail = {
  claim_id: "claim-001", original_files: 2, files: [mail, photo, attachment, nested, inner], chunks,
  stages: { files: true, extract: false, chunks: false, embed: false, index: false },
  skipped: [], stale_chunks: 0, duplicate_occurrences: 1,
};
const options = { expandedFiles: [], expandedChunks: [], focusId: "" };
const event = (stage, id, done = false, message = "Observed event") => ({
  claim_id: "claim-001", stage, evidence_id: id, done, message,
});
const run = (events, status = "running", stage = "extract") => ({
  id: "run", claim_id: "claim-001", claim_ids: ["claim-001"], status, stage,
  message: "Current run", index_data: true, events,
});

test("connects original files, attachment-only evidence and nested messages without duplicating copies", () => {
  const graph = buildExecutionTree(detail, null, options);
  expect(graph.nodes.filter(node => node.id.startsWith("file:"))).toHaveLength(5);
  expect(graph.edges.find(edge => edge.source === "claim-root" && edge.target === "file:photo")).toBeDefined();
  expect(graph.edges.find(edge => edge.source === "file:mail" && edge.target === "file:photo").label).toContain("same bytes");
  expect(graph.edges.find(edge => edge.source === "file:nested" && edge.target === "file:inner").label).toBe("attachment");
  const x = id => graph.nodes.find(node => node.id === id).position.x;
  expect(x("file:inner")).toBeGreaterThan(x("file:nested"));
  expect(x("file:nested")).toBeGreaterThan(x("file:mail"));
  expect(graph.warnings).toEqual([]);
});

test("expands each processing approach and actual chunk branches without copying vector values", () => {
  const before = JSON.stringify(detail);
  const graph = buildExecutionTree(detail, null, { ...options, expandedFiles: ["photo"], expandedChunks: ["photo"] });
  expect(graph.nodes.find(node => node.id === "approach:photo").data.label).toBe("prebuilt-imageSearch");
  expect(graph.nodes.find(node => node.id === "native:photo").data.label).toBe("Image summary");
  expect(graph.nodes.filter(node => node.type === "chunk")).toHaveLength(2);
  expect(graph.nodes.find(node => node.id === "chunk:chunk-1").data.action).toEqual({ kind: "chunk", chunkId: "chunk-1" });
  expect(graph.nodes.find(node => node.id === "embed:photo").data.description).toContain("3072 dimensions");
  expect(JSON.stringify(graph)).not.toContain("content_vector");
  expect(JSON.stringify(detail)).toBe(before);
});

test("file focus keeps provenance ancestors while hiding unrelated sibling evidence", () => {
  const graph = buildExecutionTree(detail, null, { ...options, focusId: "inner" });
  const fileIds = graph.nodes.filter(node => node.id.startsWith("file:")).map(node => node.id);
  expect(fileIds).toEqual(expect.arrayContaining(["file:mail", "file:nested", "file:inner"]));
  expect(fileIds).not.toContain("file:photo");
  expect(fileIds).not.toContain("file:attachment");
});

test("distinguishes saved output from an observed cache hit, running file and failed file", () => {
  expect(fileStageStatus(detail, photo, "extract", null)).toBe("saved");
  expect(fileStageStatus(detail, photo, "extract", run([event("extract", "photo")]))).toBe("running");
  expect(fileStageStatus(detail, photo, "extract", run([event("extract", "photo")], "failed"))).toBe("failed");
  const cached = run([
    event("extract", "photo", false, "Reading saved result: damage.jpg"),
    event("extract", "photo", true, "Extracted damage.jpg"),
  ], "complete");
  expect(fileStageStatus(detail, photo, "extract", cached)).toBe("cached");
  expect(fileStageStatus(detail, photo, "embed", cached)).toBe("saved");
});

test("does not attribute a folder-wide failure to every file or invent timestamps", () => {
  const job = run([event("chunks", "", false, "Preparing folder chunks")], "failed", "chunks");
  expect(fileStageStatus(detail, photo, "chunks", job)).toBe("saved");
  const graph = buildExecutionTree(detail, job, { ...options, expandedFiles: ["photo"] });
  expect(graph.nodes.find(node => node.id === "claim-root").data.status).toBe("failed");
  expect(graph.nodes.find(node => node.id === "chunks:photo").data.status).not.toBe("failed");
  expect(retainedEvents(detail, job, "photo")).toEqual([{ ...job.events[0], sequence: 1 }]);
  expect(JSON.stringify(graph)).not.toContain("duration");
  expect(JSON.stringify(graph)).not.toContain("timestamp");
});

test("only shows this folder's retained events, preserving their recorded sequence", () => {
  const job = run([
    { ...event("files", ""), claim_id: "claim-002" },
    event("extract", "photo", true),
    event("extract", "attachment"),
    event("chunks", "", true),
  ]);
  expect(retainedEvents(detail, job, "photo").map(item => item.sequence)).toEqual([2, 4]);
});

test("reports missing provenance and expired focus selections explicitly", () => {
  const unknown = evidence("orphan", "unknown.pdf", "document", { attachment_only: true, parent_emails: ["missing"] });
  expect(buildExecutionTree({ ...detail, files: [unknown], chunks: [] }, null, options).warnings.join(" ")).toContain("unavailable");
  expect(buildExecutionTree(detail, null, { ...options, focusId: "removed" }).warnings.join(" ")).toContain("no longer exists");
});
