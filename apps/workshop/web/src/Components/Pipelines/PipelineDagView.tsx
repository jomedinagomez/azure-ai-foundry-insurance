import React, { useMemo } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MarkerType,
  Node,
  NodeTypes,
  ReactFlowProvider,
} from "reactflow";
import "reactflow/dist/style.css";

import { Pipeline, StepEvent } from "../../services/pipelinesService";
import StepNode, { StepNodeData } from "./StepNode";

const NODE_TYPES: NodeTypes = { step: StepNode };

const NODE_X = 280;     // horizontal spacing between nodes
const NODE_X_FIRST = 0;
const NODE_Y = 100;     // top inset

function paramsSummary(kind: string, params: Record<string, unknown>): string | undefined {
  if (!params || Object.keys(params).length === 0) return undefined;
  if (kind === "cu_analyze") return `${params.analyzer_id ?? "?"}`;
  if (kind === "pdf_to_tiff") return `${params.dpi ?? 300} dpi`;
  if (kind === "xlsx_preflight") {
    const bits: string[] = [];
    if (params.autofit) bits.push("autofit");
    if (params.print_gridlines) bits.push("gridlines");
    return bits.join(" · ") || undefined;
  }
  return undefined;
}

export interface PipelineDagViewProps {
  pipeline: Pipeline | null;
  inputLabel?: string;       // file name shown on the input node
  events?: Record<string, StepEvent>;  // keyed by step.id
}

export default function PipelineDagView({ pipeline, inputLabel, events }: PipelineDagViewProps) {
  const { nodes, edges } = useMemo<{ nodes: Node<StepNodeData>[]; edges: Edge[] }>(() => {
    if (!pipeline) return { nodes: [], edges: [] };

    const nodes: Node<StepNodeData>[] = [];
    const edges: Edge[] = [];

    // Input node
    nodes.push({
      id: "__input",
      type: "step",
      position: { x: NODE_X_FIRST, y: NODE_Y },
      data: {
        label: inputLabel ?? "Input file",
        kind: "xlsx_preflight",     // unused for input nodes (icon swapped via isInput)
        paramsSummary: pipeline.input_extensions.join(", "),
        isInput: true,
      },
      draggable: false,
    });

    let prevId = "__input";
    pipeline.steps.forEach((step, i) => {
      const id = step.id;
      const isTerminal = i === pipeline.steps.length - 1;
      const ev = events?.[id];
      nodes.push({
        id,
        type: "step",
        position: { x: NODE_X_FIRST + NODE_X * (i + 1), y: NODE_Y },
        data: {
          label: step.label || step.kind,
          kind: step.kind,
          paramsSummary: paramsSummary(step.kind, step.params),
          status: ev?.status,
          elapsedSec: ev?.elapsed_sec ?? null,
          meta: ev?.meta,
          isTerminal,
        },
        draggable: false,
      });
      edges.push({
        id: `${prevId}->${id}`,
        source: prevId,
        target: id,
        animated: ev?.status === "running",
        markerEnd: { type: MarkerType.ArrowClosed },
      });
      prevId = id;
    });

    return { nodes, edges };
  }, [pipeline, inputLabel, events]);

  if (!pipeline) {
    return (
      <div style={{ padding: 16, opacity: 0.6 }}>Select a pipeline to view its DAG.</div>
    );
  }

  return (
    <ReactFlowProvider>
      <div style={{ width: "100%", height: "100%", minHeight: 280 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={NODE_TYPES}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
