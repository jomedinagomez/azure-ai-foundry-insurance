import { Edge, MarkerType, Node, Position } from "reactflow";
import { ClaimDetail, ClaimRun, EvidenceFile, Stage } from "../../services/claimsService";

export type TreeStatus = "saved" | "recorded" | "cached" | "pending" | "running" | "failed";
export type FileView = "original" | "extraction" | "chunks" | "sources";
export type TreeAction =
  | { kind: "file"; fileId: string; view: FileView }
  | { kind: "chunk"; chunkId: string }
  | { kind: "inspect"; fileId: string; stage: Stage }
  | { kind: "expand-file"; fileId: string }
  | { kind: "expand-chunks"; fileId: string };

export interface TreeNodeData {
  label: string;
  eyebrow: string;
  description: string;
  status: TreeStatus;
  fileId?: string;
  action?: TreeAction;
  secondary?: { label: string; action: TreeAction };
  onAction?: (action: TreeAction) => void;
}

export interface TreeOptions {
  expandedFiles: string[];
  expandedChunks: string[];
  focusId: string;
}

export const statusLabels: Record<TreeStatus, string> = {
  saved: "Saved artifact", recorded: "Recorded", cached: "Cached",
  pending: "Waiting", running: "Running", failed: "Failed",
};

export function retainedEvents(detail: ClaimDetail, job: ClaimRun | null, fileId?: string) {
  return (job?.events || []).map((event, index) => ({ ...event, sequence: index + 1 }))
    .filter(event => event.claim_id === detail.claim_id
      && (!fileId || event.evidence_id === fileId || !event.evidence_id));
}

export function fileStageStatus(detail: ClaimDetail, file: EvidenceFile, stage: Stage, job: ClaimRun | null): TreeStatus {
  const saved = stage === "files" || (stage === "extract" ? file.extracted
    : stage === "chunks" ? file.chunks > 0 : stage === "embed" ? file.embedded : file.uploaded);
  const events = retainedEvents(detail, job, file.id).filter(event => event.stage === stage);
  const latest = events[events.length - 1];
  const lastRunEvent = job?.events[job.events.length - 1];
  const currentFile = lastRunEvent?.claim_id === detail.claim_id && lastRunEvent.evidence_id === file.id;
  const folderStep = lastRunEvent?.claim_id === detail.claim_id && !lastRunEvent.evidence_id
    && (stage === "chunks" || stage === "index");
  if (job?.claim_id === detail.claim_id && job.stage === stage && latest && !latest.done) {
    if (job.status === "running" && (currentFile || folderStep)) return "running";
    if (job.status === "failed" && currentFile) return "failed";
  }
  if (latest?.done) {
    if (stage === "extract" && events.some(event => event.evidence_id === file.id && event.message.startsWith("Reading saved result"))) return "cached";
    return "recorded";
  }
  return saved ? "saved" : "pending";
}

export function buildExecutionTree(detail: ClaimDetail, job: ClaimRun | null, options: TreeOptions) {
  const nodes: Node<TreeNodeData>[] = [];
  const edges: Edge[] = [];
  const warnings: string[] = [];
  const byId = new Map(detail.files.map(file => [file.id, file]));
  const included = new Set<string>();
  const children = (id: string) => detail.files.filter(file => file.parent_emails.includes(id));

  if (options.focusId) {
    if (!byId.has(options.focusId)) warnings.push("The focused file no longer exists in this folder. Select All files.");
    const visit = (id: string, direction: "parents" | "children", seen = new Set<string>()) => {
      if (seen.has(id)) return;
      seen.add(id);
      const file = byId.get(id);
      if (!file) return;
      included.add(id);
      for (const related of direction === "parents" ? file.parent_emails : children(id).map(item => item.id)) {
        visit(related, direction, seen);
      }
    };
    visit(options.focusId, "parents");
    visit(options.focusId, "children");
  } else {
    detail.files.forEach(file => included.add(file.id));
  }

  const depths = new Map<string, number>();
  const depth = (file: EvidenceFile, trail = new Set<string>()): number => {
    const known = depths.get(file.id);
    if (known !== undefined) return known;
    if (trail.has(file.id)) {
      warnings.push(`Circular email relationship at ${file.filename}; inspect its source trail.`);
      return 0;
    }
    const parents = file.parent_emails.map(id => byId.get(id)).filter((item): item is EvidenceFile => Boolean(item));
    if (parents.length !== file.parent_emails.length) warnings.push(`Some parent email links for ${file.filename} are unavailable.`);
    const nextTrail = new Set([...trail, file.id]);
    const value = !file.attachment_only || !parents.length ? 0 : Math.max(...parents.map(parent => depth(parent, nextTrail))) + 1;
    depths.set(file.id, value);
    return value;
  };
  const files = detail.files.filter(file => included.has(file.id));
  files.forEach(file => depth(file));
  const maxDepth = Math.max(0, ...files.map(file => depths.get(file.id) || 0));
  const sorted = [...files].sort((a, b) => Number(b.source_type === "email") - Number(a.source_type === "email")
    || a.filename.localeCompare(b.filename));
  const ordered: EvidenceFile[] = [];
  const seen = new Set<string>();
  const append = (file: EvidenceFile) => {
    if (seen.has(file.id)) return;
    seen.add(file.id);
    ordered.push(file);
    children(file.id).filter(child => included.has(child.id) && child.attachment_only)
      .sort((a, b) => a.filename.localeCompare(b.filename)).forEach(append);
  };
  sorted.filter(file => !file.attachment_only || !file.parent_emails.some(id => included.has(id))).forEach(append);
  sorted.forEach(append);

  const spacing = 274;
  const approachX = spacing * (maxDepth + 2);
  const nativeX = approachX + spacing;
  const chunksX = nativeX + spacing;
  const showIndividualChunks = ordered.some(file => options.expandedFiles.includes(file.id)
    && options.expandedChunks.includes(file.id) && detail.chunks.some(chunk => chunk.document_hash === file.id));
  const vectorX = chunksX + spacing * (showIndividualChunks ? 2 : 1);
  const searchX = vectorX + spacing;
  let cursor = 110;

  const add = (id: string, x: number, y: number, data: TreeNodeData, type = "evidence") => {
    nodes.push({ id, type, position: { x, y }, data, draggable: false,
      sourcePosition: Position.Right, targetPosition: Position.Left });
  };
  const connect = (source: string, target: string, label?: string, related = false) => {
    edges.push({ id: `${source}->${target}`, source, target, type: "smoothstep",
      sourceHandle: related ? "related-out" : "out", targetHandle: related ? "related-in" : "in",
      label, animated: nodes.find(node => node.id === target)?.data.status === "running",
      style: { stroke: related ? "var(--colorPalettePurpleBorder2)" : "var(--colorNeutralStroke1)",
        strokeDasharray: related ? "5 5" : undefined },
      labelStyle: { fill: "var(--colorNeutralForeground2)", fontSize: 10 },
      labelBgStyle: { fill: "var(--colorNeutralBackground1)" },
      markerEnd: { type: MarkerType.ArrowClosed, color: "var(--colorNeutralStroke1)" } });
  };

  for (const file of ordered) {
    const rowStart = cursor;
    const chunks = detail.chunks.filter(chunk => chunk.document_hash === file.id);
    const expanded = options.expandedFiles.includes(file.id);
    const expandedChunks = expanded && options.expandedChunks.includes(file.id) && chunks.length > 0;
    const height = expandedChunks ? Math.max(190, chunks.length * 130) : 190;
    const y = rowStart + (height - 150) / 2;
    const fileNode = `file:${file.id}`;
    add(fileNode, spacing * ((depths.get(file.id) || 0) + 1), y, {
      label: file.filename, eyebrow: file.source_type === "email" ? "EMAIL" : file.attachment_only ? "ATTACHMENT" : "ORIGINAL FILE",
      description: `${file.source_files.length} source link${file.source_files.length === 1 ? "" : "s"} · ${chunks.length} saved chunks`,
      fileId: file.id, status: "saved", action: { kind: "file", fileId: file.id, view: "original" },
      secondary: { label: expanded ? "Collapse path" : "Expand path", action: { kind: "expand-file", fileId: file.id } },
    });

    if (!expanded) {
      add(`summary:${file.id}`, approachX, y, {
        label: "Follow this file", eyebrow: "COLLAPSED EXECUTION PATH",
        description: `${file.analyzer_id} → native output → chunks → vectors → Search`,
        status: file.embedded ? "saved" : "pending", fileId: file.id,
        action: { kind: "expand-file", fileId: file.id },
      });
      connect(fileNode, `summary:${file.id}`);
      cursor += height;
      continue;
    }
    add(`approach:${file.id}`, approachX, y, {
      label: file.analyzer_id, eyebrow: "PROCESSING APPROACH",
      description: file.source_type === "email" ? "Parse message text and recurse through attachments locally."
        : file.analyzer_id === "prebuilt-imageSearch" ? "Native image observations. No inferred cause or coverage decision."
          : "Native OCR, document Markdown, tables and embedded figures.",
      status: fileStageStatus(detail, file, "extract", job), fileId: file.id,
      action: { kind: "inspect", fileId: file.id, stage: "extract" },
    });
    connect(fileNode, `approach:${file.id}`);
    add(`native:${file.id}`, nativeX, y, {
      label: file.source_type === "email" ? "Parsed email text" : file.analyzer_id === "prebuilt-imageSearch" ? "Image summary" : "Markdown + figures",
      eyebrow: "NATIVE OUTPUT", description: file.extracted ? "Open the saved extraction without another Azure call." : "Output is not yet saved for this route.",
      status: fileStageStatus(detail, file, "extract", job), fileId: file.id,
      action: { kind: "file", fileId: file.id, view: "extraction" },
    });
    connect(`approach:${file.id}`, `native:${file.id}`);
    add(`chunks:${file.id}`, chunksX, y, {
      label: `${chunks.length} evidence chunks`, eyebrow: "SOURCE-LINKED SECTIONS",
      description: "Document sections, visual observations and figure descriptions retain their own source trail.",
      status: fileStageStatus(detail, file, "chunks", job), fileId: file.id,
      action: { kind: "file", fileId: file.id, view: "chunks" },
      secondary: chunks.length ? { label: expandedChunks ? "Fold chunk branches" : "Unfold chunk branches",
        action: { kind: "expand-chunks", fileId: file.id } } : undefined,
    });
    connect(`native:${file.id}`, `chunks:${file.id}`);
    const dimensions = [...new Set(chunks.map(chunk => chunk.vector_dimensions).filter(value => value !== undefined))];
    add(`embed:${file.id}`, vectorX, y, {
      label: "Contextual vectors", eyebrow: "EMBEDDINGS",
      description: dimensions.length ? `${dimensions.join(" / ")} dimensions · vector values stay on the server`
        : "One embedding per chunk, using title, section, evidence kind and content.",
      status: fileStageStatus(detail, file, "embed", job), fileId: file.id,
      action: { kind: "inspect", fileId: file.id, stage: "embed" },
    });
    if (expandedChunks) {
      chunks.forEach((chunk, index) => {
        const id = `chunk:${chunk.id}`;
        add(id, chunksX + spacing, rowStart + index * 130, {
          label: `Chunk ${chunk.chunk_id}: ${chunk.title}`, eyebrow: chunk.content_kind.replace(/_/g, " ").toUpperCase(),
          description: chunk.content.slice(0, 130), status: "saved", fileId: file.id,
          action: { kind: "chunk", chunkId: chunk.id },
        }, "chunk");
        connect(`chunks:${file.id}`, id);
        connect(id, `embed:${file.id}`);
      });
    } else {
      connect(`chunks:${file.id}`, `embed:${file.id}`);
    }
    add(`index:${file.id}`, searchX, y, {
      label: file.uploaded ? "Upload receipt saved" : "Evidence index", eyebrow: "AZURE AI SEARCH",
      description: "Claim-filtered keyword + vector retrieval with semantic reranking. A receipt is not a live health check.",
      status: fileStageStatus(detail, file, "index", job), fileId: file.id,
      action: { kind: "inspect", fileId: file.id, stage: "index" },
    });
    connect(`embed:${file.id}`, `index:${file.id}`);
    cursor += height;
  }

  const rootStatus = job?.claim_id === detail.claim_id && job.status !== "complete"
    ? job.status : "saved";
  add("claim-root", 0, 110, {
    label: detail.claim_id, eyebrow: "CLAIM FOLDER",
    description: `${detail.original_files} originals · ${detail.files.length} unique evidence files`,
    status: rootStatus,
  });
  for (const file of ordered) {
    const parents = file.parent_emails.filter(id => included.has(id));
    if (!file.attachment_only || !parents.length) connect("claim-root", `file:${file.id}`);
    for (const parent of parents) {
      const related = (depths.get(file.id) || 0) <= (depths.get(parent) || 0);
      connect(`file:${parent}`, `file:${file.id}`, related ? "also attached · same bytes" : "attachment", related);
    }
  }
  const header = (id: string, x: number, label: string) => add(id, x, 20, {
    label, eyebrow: "", description: "", status: "saved",
  }, "heading");
  header("heading:folder", 0, "FOLDER");
  for (let level = 0; level <= maxDepth; level++) header(`heading:files:${level}`, spacing * (level + 1), level ? `ATTACHMENTS · LEVEL ${level}` : "ORIGINAL EVIDENCE");
  const anyExpanded = ordered.some(file => options.expandedFiles.includes(file.id));
  header("heading:approach", approachX, anyExpanded ? "APPROACH" : "EXPAND A FILE TO FOLLOW ITS OUTPUTS");
  if (anyExpanded) {
    header("heading:native", nativeX, "NATIVE OUTPUT");
    header("heading:chunks", chunksX, "EVIDENCE CHUNKS");
    if (showIndividualChunks) header("heading:individual", chunksX + spacing, "INDIVIDUAL CHUNKS");
    header("heading:vectors", vectorX, "EMBEDDINGS");
    header("heading:index", searchX, "SEARCH");
  }
  return { nodes, edges, warnings: [...new Set(warnings)] };
}
