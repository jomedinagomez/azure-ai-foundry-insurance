import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button } from "@fluentui/react-components";
import {
  ArrowExpandRegular, ChevronRightRegular, ClockRegular,
  DismissRegular, FolderRegular, FlowRegular,
} from "@fluentui/react-icons";
import ReactFlow, {
  Background, BackgroundVariant, Controls, Handle, MiniMap,
  NodeProps, NodeTypes, Position, ReactFlowInstance, ReactFlowProvider, Viewport,
} from "reactflow";
import "reactflow/dist/style.css";
import { ClaimDetail, ClaimRun, EvidenceChunk } from "../../services/claimsService";
import {
  buildExecutionTree, fileStageStatus, FileView, retainedEvents,
  statusLabels, TreeAction, TreeNodeData, TreeOptions,
} from "./executionTreeModel";
import "../../Styles/ClaimsExecutionTree.css";

export interface ExecutionTreeView extends TreeOptions {
  viewport?: Viewport;
}

interface Props {
  detail: ClaimDetail;
  job: ClaimRun | null;
  view: ExecutionTreeView;
  onChange: React.Dispatch<React.SetStateAction<ExecutionTreeView>>;
  onOpenFile: (fileId: string, view: FileView) => void;
  onOpenChunk: (chunk: EvidenceChunk) => void;
}

function EvidenceNode({ data, type }: NodeProps<TreeNodeData>) {
  return <div className={`cet-node cet-status-${data.status} ${type === "chunk" ? "cet-chunk-node" : ""}`}>
    <Handle type="target" position={Position.Left} id="in" isConnectable={false} />
    <Handle type="target" position={Position.Top} id="related-in" isConnectable={false} />
    <div className="cet-node-top"><span>{data.eyebrow}</span><span className="cet-status-dot" title={statusLabels[data.status]} /></div>
    {data.action ? <button className="cet-node-main nodrag" onClick={() => data.action && data.onAction?.(data.action)}
      aria-label={`${data.label} — ${data.eyebrow.toLowerCase()}`}>
      <strong>{data.label}</strong><span>{data.description}</span>
    </button> : <div className="cet-node-main"><strong><FolderRegular /> {data.label}</strong><span>{data.description}</span></div>}
    <div className="cet-node-footer"><span>{statusLabels[data.status]}</span>
      {data.secondary && <button className="cet-node-toggle nodrag" onClick={() => data.secondary && data.onAction?.(data.secondary.action)}>
        {data.secondary.label}<ChevronRightRegular /></button>}</div>
    <Handle type="source" position={Position.Right} id="out" isConnectable={false} />
    <Handle type="source" position={Position.Bottom} id="related-out" isConnectable={false} />
  </div>;
}

function HeadingNode({ data }: NodeProps<TreeNodeData>) {
  return <div className="cet-column-heading">{data.label}</div>;
}

const NODE_TYPES: NodeTypes = { evidence: EvidenceNode, chunk: EvidenceNode, heading: HeadingNode };

export default function ClaimsExecutionTree({ detail, job, view, onChange, onOpenFile, onOpenChunk }: Props) {
  const [instance, setInstance] = useState<ReactFlowInstance<TreeNodeData> | null>(null);
  const [inspection, setInspection] = useState<{ fileId?: string; stage?: string } | null>(null);
  const graph = useMemo(() => buildExecutionTree(detail, job, {
    expandedFiles: view.expandedFiles, expandedChunks: view.expandedChunks, focusId: view.focusId,
  }), [detail, job, view.expandedFiles, view.expandedChunks, view.focusId]);
  const act = useCallback((action: TreeAction) => {
    if (action.kind === "file") onOpenFile(action.fileId, action.view);
    if (action.kind === "chunk") {
      const chunk = detail.chunks.find(item => item.id === action.chunkId);
      if (chunk) onOpenChunk(chunk);
    }
    if (action.kind === "inspect") setInspection({ fileId: action.fileId, stage: action.stage });
    if (action.kind === "expand-file" || action.kind === "expand-chunks") {
      const field = action.kind === "expand-file" ? "expandedFiles" : "expandedChunks";
      onChange(previous => ({ ...previous, [field]: previous[field].includes(action.fileId)
        ? previous[field].filter(id => id !== action.fileId) : [...previous[field], action.fileId] }));
    }
  }, [detail.chunks, onChange, onOpenChunk, onOpenFile]);
  const nodes = useMemo(() => graph.nodes.map(node => ({ ...node, data: { ...node.data, onAction: act } })), [graph.nodes, act]);
  const selectedFile = detail.files.find(file => file.id === inspection?.fileId);
  const events = inspection ? retainedEvents(detail, job, inspection.fileId) : [];
  const runRelevant = retainedEvents(detail, job).length > 0;

  useEffect(() => {
    if (!instance || !view.focusId || view.viewport) return;
    const frame = requestAnimationFrame(() => { void instance.fitView({ padding: 0.12, maxZoom: 0.9 }); });
    return () => cancelAnimationFrame(frame);
  }, [instance, view.focusId, view.viewport]);

  const focus = (fileId: string) => {
    onChange(previous => ({ ...previous, focusId: fileId, viewport: previous.focusId === fileId ? previous.viewport : undefined,
      expandedFiles: fileId && !previous.expandedFiles.includes(fileId) ? [...previous.expandedFiles, fileId] : previous.expandedFiles }));
  };
  const fileOrder = detail.files.map(file => file.id);

  return <div className="cet-workspace">
    <div className="cet-toolbar">
      <label className="cet-focus-label">Focus on a file
        <select value={view.focusId} onChange={event => focus(event.target.value)} aria-label="Focus execution tree on a file">
          <option value="">All files in this folder</option>
          {detail.files.map(file => <option key={file.id} value={file.id}>{file.filename}</option>)}
        </select>
      </label>
      <Button size="small" icon={<FlowRegular />} onClick={() => onChange(previous => ({ ...previous, expandedFiles: fileOrder }))}>Expand all paths</Button>
      <Button size="small" appearance="subtle" onClick={() => onChange(previous => ({ ...previous, expandedFiles: [], expandedChunks: [] }))}>Collapse paths</Button>
      <Button size="small" appearance="subtle" icon={<ArrowExpandRegular />} onClick={() => void instance?.fitView({ padding: 0.12, maxZoom: 1 })}>Fit tree</Button>
      <Button size="small" appearance="subtle" icon={<ClockRegular />} onClick={() => setInspection({})}>Recorded chronology</Button>
    </div>
    <div className="cet-legend" aria-label="Execution states">
      {(["saved", "recorded", "cached", "running", "pending", "failed"] as const).map(status =>
        <span key={status} className={`cet-status-${status}`}><i className="cet-status-dot" />{statusLabels[status]}</span>)}
      <span className="cet-legend-note">Solid lines: processing path · dashed lines: shared attachment copies</span>
    </div>
    {graph.warnings.map(warning => <div key={warning} className="ce-error" role="alert">{warning}</div>)}
    <div className={`cet-canvas-row ${inspection ? "cet-with-inspector" : ""}`}>
      <div className="cet-canvas" aria-label="Horizontal claim execution tree">
        <ReactFlowProvider>
          <ReactFlow
            nodes={nodes} edges={graph.edges} nodeTypes={NODE_TYPES}
            onInit={setInstance}
            defaultViewport={view.viewport || { x: 28, y: 0, zoom: 0.75 }}
            onMoveEnd={(_, viewport) => onChange(previous => ({ ...previous, viewport }))}
            nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
            nodesFocusable={false} edgesFocusable={false}
            minZoom={0.12} maxZoom={1.6} panOnScroll zoomOnDoubleClick={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="var(--colorNeutralStroke2)" />
            <Controls showInteractive={false} />
            <MiniMap pannable zoomable nodeColor={node => node.data.status === "running" ? "var(--colorBrandBackground)" : "var(--colorBrandBackground2)"}
              nodeStrokeColor="var(--colorNeutralStroke1)" maskColor="var(--colorNeutralBackgroundAlpha)" />
          </ReactFlow>
        </ReactFlowProvider>
      </div>
      {inspection && <aside className="cet-inspector" aria-label="Recorded execution details">
        <div className="cet-inspector-heading"><div><div className="ce-eyebrow">EXECUTION DETAILS</div><h3>{selectedFile?.filename || detail.claim_id}</h3></div>
          <Button size="small" appearance="subtle" aria-label="Close chronology panel" icon={<DismissRegular />} onClick={() => setInspection(null)} /></div>
        {selectedFile && <>
          <p className="cet-inspector-note">{selectedFile.analyzer_id} · {selectedFile.chunks} saved chunks</p>
          <p className="cet-inspector-note">The approach comes from prepared records or the available saved/default route. It is not proof that a currently running override used that analyzer.</p>
          <div className="cet-file-states">{(["files", "extract", "chunks", "embed", "index"] as const).map(stage =>
            <Badge key={stage} appearance="tint">{stage}: {statusLabels[fileStageStatus(detail, selectedFile, stage, job)]}</Badge>)}</div>
          <Button size="small" onClick={() => onOpenFile(selectedFile.id, "sources")}>Open source trail</Button>
          <Button size="small" appearance="subtle" onClick={() => focus(selectedFile.id)}>Focus on this file</Button>
        </>}
        <h4>Retained event order</h4>
        <p className="cet-inspector-note">Only recorded events are listed, in their saved order. Numbers refer to the retained log window (up to 200 events). Timestamps and durations were not recorded.</p>
        {events.length ? <ol className="cet-events">{events.map(event =>
          <li key={event.sequence}><span className="cet-event-number">#{event.sequence}</span><div>
            <div className="cet-event-context">{event.stage} · {event.evidence_id ? "this file" : "folder step"}</div><p>{event.message}</p>
          </div></li>)}</ol> : <p className="cet-inspector-note">No retained execution events are available for this {selectedFile ? "file" : "folder"}. Saved outputs are still visible; no execution times are inferred.</p>}
        {runRelevant && job?.status === "failed" && job.claim_id === detail.claim_id &&
          <div className="ce-error" role="alert"><strong>Folder run stopped</strong><p>{job.message}</p><small>The log may not identify which file caused a folder-wide failure.</small></div>}
      </aside>}
    </div>
    <p className="cet-footer">Read left to right. Drag or scroll to pan; use the controls to zoom. Expand file paths, then unfold individual chunk branches.
      Saved artifacts are not a replay of a run or a live Search health check. Opening this view makes no paid calls.</p>
  </div>;
}
