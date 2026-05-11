import React from "react";
import {
  Body1Strong,
  Caption1,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import {
  CheckmarkCircleFilled,
  DismissCircleFilled,
  ArrowSyncRegular,
  CircleRegular,
  DocumentRegular,
  DocumentTableRegular,
  DocumentPdfRegular,
  ImageRegular,
  ImageMultipleRegular,
  WrenchRegular,
  BrainCircuitRegular,
} from "@fluentui/react-icons";
import { Handle, Position, NodeProps } from "reactflow";

import { StepKind, StepEvent } from "../../services/pipelinesService";

export interface StepNodeData {
  label: string;
  kind: StepKind;
  paramsSummary?: string;
  status?: StepEvent["status"];
  elapsedSec?: number | null;
  meta?: Record<string, unknown>;
  isInput?: boolean;
  isTerminal?: boolean;
}

const KIND_ICON: Record<StepKind | "input", React.ReactElement> = {
  xlsx_preflight: <DocumentTableRegular />,
  libreoffice_to_pdf: <DocumentPdfRegular />,
  pdf_to_tiff: <ImageRegular />,
  extract_embedded_images: <ImageMultipleRegular />,
  cu_analyze: <BrainCircuitRegular />,
  input: <DocumentRegular />,
};

function statusIcon(s?: StepEvent["status"]) {
  if (s === "running")
    return (
      <ArrowSyncRegular
        style={{ animation: "spin 1.2s linear infinite" }}
      />
    );
  if (s === "done") return <CheckmarkCircleFilled />;
  if (s === "error") return <DismissCircleFilled />;
  return <CircleRegular style={{ opacity: 0.45 }} />;
}

function statusColor(s?: StepEvent["status"]): string {
  if (s === "running") return tokens.colorPaletteBlueForeground2;
  if (s === "done") return tokens.colorPaletteGreenForeground1;
  if (s === "error") return tokens.colorPaletteRedForeground1;
  return tokens.colorNeutralForeground3;
}

const useStyles = makeStyles({
  node: {
    display: "flex",
    flexDirection: "column",
    rowGap: "4px",
    minWidth: "190px",
    maxWidth: "240px",
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.padding("10px", "12px"),
    ...shorthands.borderRadius("8px"),
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke2),
    boxShadow: tokens.shadow4,
  },
  nodeRunning: {
    ...shorthands.border("1px", "solid", tokens.colorBrandStroke1),
    boxShadow: `0 0 0 3px ${tokens.colorBrandBackground2Hover}`,
  },
  nodeDone: {
    ...shorthands.border("1px", "solid", tokens.colorPaletteGreenBorder1),
  },
  nodeError: {
    ...shorthands.border("1px", "solid", tokens.colorPaletteRedBorder1),
  },
  header: {
    display: "flex",
    alignItems: "center",
    columnGap: "8px",
  },
  iconBox: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "28px",
    height: "28px",
    ...shorthands.borderRadius("6px"),
    backgroundColor: tokens.colorNeutralBackground3,
    flexShrink: 0,
  },
  title: {
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    columnGap: "6px",
    marginTop: "4px",
  },
});

export default function StepNode({ data }: NodeProps<StepNodeData>) {
  const styles = useStyles();
  const isInput = !!data.isInput;
  const isTerminal = !!data.isTerminal;
  const showLeft = !isInput;
  const showRight = !isTerminal;

  let extraCls: string | undefined;
  if (data.status === "running") extraCls = styles.nodeRunning;
  else if (data.status === "done") extraCls = styles.nodeDone;
  else if (data.status === "error") extraCls = styles.nodeError;

  const icon = KIND_ICON[isInput ? "input" : data.kind] ?? <WrenchRegular />;

  return (
    <div className={`${styles.node} ${extraCls ?? ""}`}>
      {showLeft && (
        <Handle type="target" position={Position.Left} style={{ background: tokens.colorBrandBackground }} />
      )}
      <div className={styles.header}>
        <div className={styles.iconBox}>{icon}</div>
        <div className={styles.title}>
          <Body1Strong>{data.label}</Body1Strong>
        </div>
      </div>
      {data.paramsSummary && (
        <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
          {data.paramsSummary}
        </Caption1>
      )}
      <div className={styles.statusRow}>
        <span style={{ color: statusColor(data.status), display: "inline-flex" }}>
          {statusIcon(data.status)}
        </span>
        <Caption1 style={{ color: statusColor(data.status) }}>
          {data.status === "running"
            ? "running…"
            : data.status === "done"
            ? `done · ${data.elapsedSec ?? "?"}s`
            : data.status === "error"
            ? "error"
            : isInput
            ? "input"
            : "pending"}
        </Caption1>
      </div>
      {showRight && (
        <Handle type="source" position={Position.Right} style={{ background: tokens.colorBrandBackground }} />
      )}
    </div>
  );
}
