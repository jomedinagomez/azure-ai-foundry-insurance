import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import {
  Badge,
  Button,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Tab,
  TabList,
  Text,
  Tooltip,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  ArrowUploadRegular,
  ChevronDownRegular,
  ChevronRightRegular,
  DocumentRegular,
  PlayRegular,
  DismissRegular,
  CheckmarkCircleRegular,
  ErrorCircleRegular,
  ClockRegular,
} from "@fluentui/react-icons";
import {
  compareAnalyzers,
  fetchPrebuiltAnalyzers,
  fetchApiVersions,
  AnalyzerResult,
  ApiVersions,
  CompareResponse,
  PrebuiltAnalyzer,
} from "../services/analyzerService";

// ───────────────────────────────────────────────────────────────────────────────
// Constants
// ───────────────────────────────────────────────────────────────────────────────
const DI_BORDER = tokens.colorBrandStroke1;
const CU_COLOR  = "#7B2FAE";
const CU_BORDER = "#7B2FAE";
const CU_BG     = "#F3EAFF";

const DEFAULT_API_VERSIONS: ApiVersions = {
  di: [
    { value: "2024-11-30",         label: "2024-11-30 — GA v4.0" },
    { value: "2024-07-31-preview", label: "2024-07-31-preview — v4.0 Preview" },
    { value: "2023-07-31",         label: "2023-07-31 — GA v3.1" },
  ],
  cu: [
    { value: "2025-11-01",         label: "2025-11-01 — GA" },
    { value: "2024-12-01-preview", label: "2024-12-01-preview — Preview" },
  ],
};

// ───────────────────────────────────────────────────────────────────────────────
// Styles
// ───────────────────────────────────────────────────────────────────────────────
const useStyles = makeStyles({
  // Root 3-panel layout
  page: {
    display: "flex",
    flexDirection: "row",
    width: "100%",
    height: "100%",
    overflow: "hidden",
    backgroundColor: tokens.colorNeutralBackground3,
  },

  // ── Left configuration panel ──
  leftPanel: {
    width: "340px",
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    overflowY: "auto",
  },
  panelTitle: {
    padding: "13px 16px 11px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexShrink: 0,
  },
  leftSection: {
    padding: "12px 16px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  serviceConfigCard: {
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    overflow: "hidden",
  },
  serviceCardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "7px 12px",
    backgroundColor: tokens.colorNeutralBackground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  serviceCardBody: {
    padding: "10px 12px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  fieldLabel: {
    fontSize: tokens.fontSizeBase100,
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground3,
    letterSpacing: "0.05em",
    textTransform: "uppercase" as const,
    marginBottom: "2px",
  },

  // Upload area
  dropzone: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "5px",
    padding: "16px",
    border: `2px dashed ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    cursor: "pointer",
    transition: "border-color 0.15s, background-color 0.15s",
    backgroundColor: tokens.colorNeutralBackground2,
    textAlign: "center" as const,
    "&:hover": {
      border: `2px dashed ${tokens.colorBrandStroke1}`,
      backgroundColor: tokens.colorNeutralBackground2Hover,
    },
  },
  dropzoneActive: {
    border: `2px dashed ${tokens.colorBrandStroke1}`,
    backgroundColor: tokens.colorBrandBackground2,
  },
  fileChip: {
    display: "flex",
    alignItems: "center",
    gap: "7px",
    padding: "6px 10px",
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },

  // Run button section
  runSection: {
    padding: "14px 16px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },

  // ── Result panels ──
  resultPanel: {
    flex: "1 1 0",
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    backgroundColor: tokens.colorNeutralBackground1,
  },
  resultPanelHeader: {
    padding: "9px 16px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    display: "flex",
    alignItems: "center",
    gap: "10px",
    flexShrink: 0,
    flexWrap: "wrap" as const,
    backgroundColor: tokens.colorNeutralBackground1,
    minHeight: "52px",
  },
  resultPanelHeaderLeft: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flex: "1 1 auto",
    minWidth: 0,
  },
  resultPanelHeaderRight: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexWrap: "wrap" as const,
  },
  tabsBar: {
    padding: "0 16px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  tabContent: {
    flex: "1 1 auto",
    overflowY: "auto",
    padding: "14px 16px",
  },

  // Empty / loading state
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    gap: "10px",
    color: tokens.colorNeutralForeground3,
    textAlign: "center" as const,
  },

  // ── Extracted fields table ──
  fieldsTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: tokens.fontSizeBase200,
  },
  fieldsRow: {
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  fieldKey: {
    padding: "5px 10px 5px 0",
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground2,
    verticalAlign: "top",
    whiteSpace: "nowrap",
    maxWidth: "180px",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  fieldVal: {
    padding: "5px 0",
    color: "#C0651A",
    wordBreak: "break-word",
  },
  fieldConf: {
    padding: "5px 0 5px 8px",
    fontSize: tokens.fontSizeBase100,
    whiteSpace: "nowrap",
    verticalAlign: "top",
    textAlign: "right" as const,
  },

  // ── JSON Tree ──
  treeRoot: {
    fontFamily: "Consolas, 'Courier New', monospace",
    fontSize: tokens.fontSizeBase200,
    lineHeight: "1.65",
  },
  treeItem: {
    paddingLeft: "14px",
    borderLeft: `1px solid ${tokens.colorNeutralStroke3}`,
    marginLeft: "2px",
  },
  treeKey: {
    color: tokens.colorNeutralForeground1,
    fontWeight: tokens.fontWeightSemibold,
    userSelect: "text" as const,
  },
  treeColon: {
    color: tokens.colorNeutralForeground3,
    marginRight: "4px",
    marginLeft: "1px",
  },
  treeStringVal:  { color: "#C67C28" },
  treeNumberVal:  { color: "#2471A3" },
  treeBoolVal:    { color: "#7D3C98" },
  treeNullVal:    { color: "#C0392B", fontStyle: "italic" },
  treeObjectLabel:{ color: tokens.colorNeutralForeground3, fontStyle: "italic" },
  treeExpandBtn: {
    display: "inline-flex",
    alignItems: "center",
    color: tokens.colorNeutralForeground3,
    marginRight: "2px",
    cursor: "pointer",
    flexShrink: 0,
  },

  // ── Markdown output ──
  markdownBody: {
    fontFamily: tokens.fontFamilyBase,
    fontSize: tokens.fontSizeBase300,
    lineHeight: "1.7",
    color: tokens.colorNeutralForeground1,
    "& h1": { fontSize: tokens.fontSizeBase600, fontWeight: tokens.fontWeightSemibold, margin: "16px 0 6px" },
    "& h2": { fontSize: tokens.fontSizeBase500, fontWeight: tokens.fontWeightSemibold, margin: "14px 0 5px" },
    "& h3": { fontSize: tokens.fontSizeBase400, fontWeight: tokens.fontWeightSemibold, margin: "12px 0 4px" },
    "& h4": { fontSize: tokens.fontSizeBase300, fontWeight: tokens.fontWeightSemibold, margin: "10px 0 4px" },
    "& p":  { margin: "0 0 10px" },
    "& ul, & ol": { paddingLeft: "24px", margin: "0 0 10px" },
    "& li":         { marginBottom: "4px" },
    "& code": {
      fontFamily: "Consolas, 'Courier New', monospace",
      fontSize: tokens.fontSizeBase100,
      backgroundColor: tokens.colorNeutralBackground2,
      padding: "1px 5px",
      borderRadius: tokens.borderRadiusSmall,
    },
    "& pre": {
      backgroundColor: tokens.colorNeutralBackground2,
      borderRadius: tokens.borderRadiusMedium,
      padding: "10px 14px",
      overflowX: "auto",
      fontSize: tokens.fontSizeBase100,
      fontFamily: "Consolas, 'Courier New', monospace",
      margin: "0 0 10px",
    },
    "& pre code": {
      backgroundColor: "transparent",
      padding: 0,
    },
    "& blockquote": {
      borderLeft: `3px solid ${tokens.colorNeutralStroke1}`,
      paddingLeft: "12px",
      color: tokens.colorNeutralForeground3,
      margin: "0 0 10px",
    },
    "& table": {
      width: "100%",
      borderCollapse: "collapse",
      marginBottom: "12px",
      fontSize: tokens.fontSizeBase200,
    },
    "& th": {
      padding: "6px 10px",
      borderBottom: `2px solid ${tokens.colorNeutralStroke1}`,
      fontWeight: tokens.fontWeightSemibold,
      textAlign: "left" as const,
      backgroundColor: tokens.colorNeutralBackground2,
    },
    "& td": {
      padding: "5px 10px",
      borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    },
    "& hr": { border: "none", borderTop: `1px solid ${tokens.colorNeutralStroke2}`, margin: "16px 0" },
    "& img": { maxWidth: "100%" },
    "& a":  { color: tokens.colorBrandForeground1 },
  },

  // Error box
  errorBox: {
    backgroundColor: tokens.colorStatusDangerBackground1,
    color: tokens.colorStatusDangerForeground1,
    borderRadius: tokens.borderRadiusMedium,
    padding: "10px 14px",
    fontSize: tokens.fontSizeBase200,
  },

  // Raw JSON
  rawJson: {
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: tokens.borderRadiusMedium,
    padding: "12px 14px",
    fontSize: tokens.fontSizeBase100,
    fontFamily: "Consolas, 'Courier New', monospace",
    overflowX: "auto",
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
    color: tokens.colorNeutralForeground1,
    margin: 0,
    lineHeight: "1.55",
  },

  // Summary badges row
  metaRow: {
    display: "flex",
    gap: "6px",
    flexWrap: "wrap" as const,
    marginBottom: "12px",
  },

  // ── DI structured tables ──
  diTable: {
    borderCollapse: "collapse",
    fontSize: tokens.fontSizeBase200,
    minWidth: "300px",
    width: "100%",
  },
  diTh: {
    padding: "6px 10px",
    fontWeight: tokens.fontWeightSemibold,
    backgroundColor: tokens.colorNeutralBackground2,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    textAlign: "left" as const,
    verticalAlign: "top",
    whiteSpace: "pre-wrap" as const,
  },
  diTd: {
    padding: "5px 10px",
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    verticalAlign: "top",
    whiteSpace: "pre-wrap" as const,
  },
});

// ───────────────────────────────────────────────────────────────────────────────
// JSON Tree component
// ───────────────────────────────────────────────────────────────────────────────
interface JsonNodeProps {
  value: unknown;
  keyName?: string;
  depth?: number;
}

const JsonNode: React.FC<JsonNodeProps> = ({ value, keyName, depth = 0 }) => {
  const styles = useStyles();
  const [expanded, setExpanded] = useState(depth < 2);

  const keyEl = keyName !== undefined ? (
    <>
      <span className={styles.treeKey}>{keyName}</span>
      <span className={styles.treeColon}>:</span>
    </>
  ) : null;

  if (value === null) {
    return (
      <div style={{ display: "flex", gap: "4px" }}>
        {keyEl}
        <span className={styles.treeNullVal}>NULL</span>
      </div>
    );
  }
  if (typeof value === "string") {
    return (
      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
        {keyEl}
        <span className={styles.treeStringVal}>"{value}"</span>
      </div>
    );
  }
  if (typeof value === "number") {
    return (
      <div style={{ display: "flex", gap: "4px" }}>
        {keyEl}
        <span className={styles.treeNumberVal}>{value}</span>
      </div>
    );
  }
  if (typeof value === "boolean") {
    return (
      <div style={{ display: "flex", gap: "4px" }}>
        {keyEl}
        <span className={styles.treeBoolVal}>{value.toString()}</span>
      </div>
    );
  }
  if (Array.isArray(value)) {
    const count = value.length;
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "2px", cursor: "pointer" }} onClick={() => setExpanded(e => !e)}>
          <span className={styles.treeExpandBtn}>
            {expanded ? <ChevronDownRegular fontSize={11} /> : <ChevronRightRegular fontSize={11} />}
          </span>
          {keyEl}
          <span className={styles.treeObjectLabel}> [{count} item{count !== 1 ? "s" : ""}]</span>
        </div>
        {expanded && count > 0 && (
          <div className={styles.treeItem}>
            {value.map((item, i) => (
              <JsonNode key={i} value={item} keyName={String(i)} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    const count = entries.length;
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "2px", cursor: "pointer" }} onClick={() => setExpanded(e => !e)}>
          <span className={styles.treeExpandBtn}>
            {expanded ? <ChevronDownRegular fontSize={11} /> : <ChevronRightRegular fontSize={11} />}
          </span>
          {keyEl}
          <span className={styles.treeObjectLabel}> {"{"}{ count} item{count !== 1 ? "s" : ""}{"}"}</span>
        </div>
        {expanded && count > 0 && (
          <div className={styles.treeItem}>
            {entries.map(([k, v]) => (
              <JsonNode key={k} value={v} keyName={k} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: "4px" }}>
      {keyEl}
      <span>{String(value)}</span>
    </div>
  );
};

// ───────────────────────────────────────────────────────────────────────────────
// Field extraction helpers
// ───────────────────────────────────────────────────────────────────────────────
function extractFieldValue(obj: Record<string, unknown>): string {
  if (obj.valueCurrency && typeof obj.valueCurrency === "object") {
    const c = obj.valueCurrency as Record<string, unknown>;
    return `${c.currencySymbol ?? ""}${c.amount} ${c.currencyCode ?? ""}`.trim();
  }
  if (obj.valueAddress && typeof obj.valueAddress === "object") {
    const a = obj.valueAddress as Record<string, unknown>;
    return [a.road, a.city, a.state, a.postalCode, a.countryRegion].filter(Boolean).join(", ");
  }
  return (
    (obj.valueString as string) ??
    (obj.valueNumber as number)?.toString() ??
    (obj.valueDate as string) ??
    (obj.valueTime as string) ??
    (obj.valueInteger as number)?.toString() ??
    (obj.valueSelectionMark as string) ??
    (obj.valueBoolean as boolean | undefined)?.toString() ??
    (obj.valuePhoneNumber as string) ??
    (obj.valueCountryRegion as string) ??
    (obj.content as string) ??
    JSON.stringify(obj)
  );
}

function flattenFields(
  fields: Record<string, unknown>,
  prefix = ""
): Array<{ key: string; value: string; confidence?: number }> {
  const rows: Array<{ key: string; value: string; confidence?: number }> = [];
  for (const [k, v] of Object.entries(fields)) {
    const displayKey = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object") {
      const obj = v as Record<string, unknown>;
      if ("confidence" in obj) {
        rows.push({ key: displayKey, value: extractFieldValue(obj) ?? "(no value)", confidence: obj.confidence as number });
      } else if ("valueArray" in obj && Array.isArray(obj.valueArray)) {
        (obj.valueArray as Record<string, unknown>[]).forEach((item, i) => {
          if (item && typeof item === "object" && "valueObject" in item)
            rows.push(...flattenFields(item.valueObject as Record<string, unknown>, `${displayKey}[${i}]`));
        });
      } else if ("valueObject" in obj && typeof obj.valueObject === "object") {
        rows.push(...flattenFields(obj.valueObject as Record<string, unknown>, displayKey));
      } else {
        rows.push({ key: displayKey, value: JSON.stringify(v) });
      }
    } else {
      rows.push({ key: displayKey, value: String(v ?? "(null)") });
    }
  }
  return rows;
}

function confidenceColor(c: number | undefined): string {
  if (c === undefined) return tokens.colorNeutralForeground3;
  if (c >= 0.8) return tokens.colorStatusSuccessForeground1;
  if (c >= 0.5) return tokens.colorStatusWarningForeground1;
  return tokens.colorStatusDangerForeground1;
}

// ───────────────────────────────────────────────────────────────────────────────
// ResultPane
// ───────────────────────────────────────────────────────────────────────────────
// DI response shape helpers (not exported — internal rendering only)
// ───────────────────────────────────────────────────────────────────────────────
interface DiCell {
  content: string;
  rowIndex: number;
  columnIndex: number;
  rowSpan?: number;
  columnSpan?: number;
  kind?: string; // "content" | "rowHeader" | "columnHeader" | "stubHead"
}
interface DiTable {
  rowCount: number;
  columnCount: number;
  cells: DiCell[];
}
interface DiKvPair {
  key: { content: string };
  value?: { content?: string };
  confidence?: number;
}
// Shared figure shape — DI: analyzeResult.figures[] / CU: contents[0].figures[]
interface FigureItem {
  id?: string;
  kind?: string;          // CU: "chart" | "unknown"; DI: n/a at figure level
  description?: string;   // CU only — AI-generated description
  caption?: { content?: string };
  elements?: string[];
}

type PaneTab = "fields" | "tables" | "kvpairs" | "figures" | "markdown" | "raw";

interface ResultPaneProps {
  source: "di" | "cu";
  analyzerName: string;
  analyzerId: string;
  apiVersion: string;
  result: AnalyzerResult | null;
  loading: boolean;
  elapsedMs?: number;
}

const ResultPane: React.FC<ResultPaneProps> = ({
  source, analyzerName, analyzerId, apiVersion, result, loading, elapsedMs,
}) => {
  const styles = useStyles();
  const [activeTab, setActiveTab] = useState<string>("fields");

  // Auto-select best tab when a new result arrives
  useEffect(() => {
    if (result?.status !== "succeeded") return;
    const raw = result.result as Record<string, unknown> | null;
    if (!raw) return;
    if (source === "di") {
      const ar = raw.analyzeResult as Record<string, unknown> | undefined;
      const docFields = ((ar?.documents as Record<string, unknown>[])?.[0]?.fields as Record<string, unknown> | undefined);
      const hasDocs  = docFields ? Object.keys(docFields).length > 0 : false;
      if (hasDocs)                                                              setActiveTab("fields");
      else if (((ar?.tables         as unknown[]) ?? []).length > 0)           setActiveTab("tables");
      else if (((ar?.keyValuePairs  as unknown[]) ?? []).length > 0)           setActiveTab("kvpairs");
      else if (((ar?.figures        as unknown[]) ?? []).length > 0)           setActiveTab("figures");
      else if (ar?.content)                                                    setActiveTab("markdown");
      else                                                                     setActiveTab("raw");
    } else {
      const first = ((raw.result as Record<string, unknown> | undefined)?.contents as Record<string, unknown>[])?.[0];
      const hasFields  = Object.keys((first?.fields  as Record<string, unknown> | undefined) ?? {}).length > 0;
      const hasTables  = ((first?.tables  as unknown[]) ?? []).length > 0;
      const hasFigures = ((first?.figures as unknown[]) ?? []).length > 0;
      if (hasFields)           setActiveTab("fields");
      else if (hasTables)      setActiveTab("tables");
      else if (hasFigures)     setActiveTab("figures");
      else if (first?.markdown) setActiveTab("markdown");
      else                     setActiveTab("raw");
    }
  }, [result, source]); // eslint-disable-line react-hooks/exhaustive-deps

  const isDI = source === "di";
  const borderColor = isDI ? DI_BORDER : CU_BORDER;

  // ── Extract payload ──
  const rawResult = result?.result as Record<string, unknown> | null;

  // DI-specific
  let diDocFields: Record<string, unknown> | undefined;
  let diDocType: string | undefined;
  let diDocConf: number | undefined;
  let diTables: DiTable[] = [];
  let diKvPairs: DiKvPair[] = [];
  let diFigures: FigureItem[] = [];
  let diPages: Record<string, unknown>[] = [];

  // CU-specific
  let cuFields: Record<string, unknown> | undefined;
  let cuTables: DiTable[] = [];   // same cell structure as DI
  let cuFigures: FigureItem[] = [];
  let cuPageCount: number | undefined;

  // Shared
  let markdown: string | undefined;

  if (rawResult) {
    if (isDI) {
      const ar = rawResult.analyzeResult as Record<string, unknown> | undefined;
      const docs = (ar?.documents as Record<string, unknown>[]) ?? [];
      if (docs.length > 0) {
        diDocFields = docs[0].fields as Record<string, unknown> | undefined;
        diDocType   = docs[0].docType as string | undefined;
        diDocConf   = docs[0].confidence as number | undefined;
      }
      diTables   = (ar?.tables        ?? []) as DiTable[];
      diKvPairs  = (ar?.keyValuePairs ?? []) as DiKvPair[];
      diFigures  = (ar?.figures       ?? []) as FigureItem[];
      markdown   = ar?.content as string | undefined;
      diPages    = (ar?.pages         ?? []) as Record<string, unknown>[];
    } else {
      const cuOp   = rawResult.result as Record<string, unknown> | undefined;
      const contents = (cuOp?.contents as Record<string, unknown>[]) ?? [];
      const first  = contents[0] as Record<string, unknown> | undefined;
      cuFields    = first?.fields   as Record<string, unknown> | undefined;
      cuTables    = (first?.tables  ?? []) as DiTable[];
      cuFigures   = (first?.figures ?? []) as FigureItem[];
      markdown    = first?.markdown as string | undefined;
      cuPageCount = (first?.pages as unknown[] | undefined)?.length;
    }
  }

  const fieldRows = isDI
    ? (diDocFields ? flattenFields(diDocFields) : [])
    : (cuFields    ? flattenFields(cuFields)    : []);

  const pageCount = isDI ? (diPages.length || undefined) : cuPageCount;

  // ── Available tabs — only include what's actually present in the response ──
  const activeTables  = isDI ? diTables  : cuTables;
  const activeFigures = isDI ? diFigures : cuFigures;
  const computedTabs: { key: PaneTab; label: string }[] = [];
  if (fieldRows.length > 0)      computedTabs.push({ key: "fields",   label: `Fields (${fieldRows.length})` });
  if (activeTables.length > 0)   computedTabs.push({ key: "tables",   label: `Tables (${activeTables.length})` });
  if (diKvPairs.length > 0)      computedTabs.push({ key: "kvpairs",  label: `Key-Value (${diKvPairs.length})` });
  if (activeFigures.length > 0)  computedTabs.push({ key: "figures",  label: `Figures (${activeFigures.length})` });
  if (markdown)                  computedTabs.push({ key: "markdown", label: "Markdown" });
  computedTabs.push({ key: "raw", label: "JSON Tree" });

  return (
    <div className={styles.resultPanel} style={{ borderTop: `3px solid ${borderColor}` }}>
      {/* Header */}
      <div className={styles.resultPanelHeader}>
        <div className={styles.resultPanelHeaderLeft}>
          <Badge
            appearance="filled"
            style={isDI ? {} : { backgroundColor: CU_COLOR }}
            color={isDI ? "informative" : undefined}
          >
            {isDI ? "Document Intelligence" : "Content Understanding"}
          </Badge>
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
            <Text weight="semibold" size={300} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {analyzerName}
            </Text>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>{analyzerId}</Text>
          </div>
        </div>
        <div className={styles.resultPanelHeaderRight}>
          <Badge
            appearance="outline"
            style={isDI ? {} : { borderColor: CU_BORDER, color: CU_COLOR }}
            color={isDI ? "informative" : undefined}
          >
            {apiVersion}
          </Badge>
          {result && (
            <Badge
              appearance="filled"
              color={result.status === "succeeded" ? "success" : "danger"}
              icon={result.status === "succeeded" ? <CheckmarkCircleRegular /> : <ErrorCircleRegular />}
            >
              {result.status}
            </Badge>
          )}
          {elapsedMs !== undefined && (
            <Badge appearance="tint" color="subtle" icon={<ClockRegular />}>
              {(elapsedMs / 1000).toFixed(1)}s
            </Badge>
          )}
        </div>
      </div>

      {/* Tabs bar — only when succeeded */}
      {result?.status === "succeeded" && (
        <div className={styles.tabsBar}>
          <TabList
            selectedValue={activeTab}
            onTabSelect={(_, d) => setActiveTab(d.value as string)}
            size="small"
          >
            {computedTabs.map(t => <Tab key={t.key} value={t.key}>{t.label}</Tab>)}
          </TabList>
        </div>
      )}

      {/* Content area */}
      <div className={styles.tabContent}>
        {loading && (
          <div className={styles.emptyState}>
            <Spinner size="large" label="Running analysis…" />
          </div>
        )}

        {!loading && result?.status === "failed" && (
          <div className={styles.errorBox}>
            <Text weight="semibold">Error: </Text>{result.error}
          </div>
        )}

        {!loading && !result && (
          <div className={styles.emptyState}>
            <DocumentRegular style={{ fontSize: "42px", opacity: 0.28 }} />
            <Text size={300} style={{ opacity: 0.4 }}>
              Upload a document and run analysis
            </Text>
          </div>
        )}

        {!loading && result?.status === "succeeded" && (
          <>
            {/* Summary badges — values taken directly from API response */}
            <div className={styles.metaRow}>
              {pageCount !== undefined && (
                <Badge appearance="tint" color={isDI ? "brand" : undefined}
                  style={!isDI ? { backgroundColor: CU_BG, color: CU_COLOR } : {}}>
                  {pageCount} page{pageCount !== 1 ? "s" : ""}
                </Badge>
              )}
              {isDI && diDocType && (
                <Badge appearance="tint" color="informative">
                  {diDocType}{diDocConf !== undefined ? ` · ${(diDocConf * 100).toFixed(0)}% conf` : ""}
                </Badge>
              )}
            </div>

            {/* ── Extracted Fields (DI: documents[0].fields / CU: contents[0].fields) ── */}
            {activeTab === "fields" && (
              fieldRows.length === 0 ? (
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
                  No structured fields extracted.
                  {markdown ? ' Switch to the "Markdown" tab to view content.' : ""}
                </Text>
              ) : (
                <table className={styles.fieldsTable}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid ${tokens.colorNeutralStroke1}` }}>
                      <th style={{ textAlign: "left", padding: "4px 10px 6px 0", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold }}>FIELD</th>
                      <th style={{ textAlign: "left", padding: "4px 0 6px",      fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold }}>VALUE</th>
                      <th style={{ textAlign: "right", padding: "4px 0 6px 8px", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold }}>CONF.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fieldRows.map((row, i) => (
                      <tr key={i} className={styles.fieldsRow}>
                        <td className={styles.fieldKey}>
                          <Tooltip relationship="label" content={row.key}>
                            <span>{row.key}</span>
                          </Tooltip>
                        </td>
                        <td className={styles.fieldVal}>{row.value}</td>
                        <td className={styles.fieldConf} style={{ color: confidenceColor(row.confidence) }}>
                          {row.confidence !== undefined ? `${(row.confidence * 100).toFixed(0)}%` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {/* ── Tables (DI: analyzeResult.tables[] / CU: contents[0].tables[]) ── */}
            {activeTab === "tables" && (
              activeTables.length === 0 ? (
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No tables extracted.</Text>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                  {activeTables.map((tbl, ti) => {
                    // Build a 2-D render grid; cells carry absolute row/col + optional spans
                    const skip = new Set<string>();
                    const placed: (DiCell | null)[][] = Array.from({ length: tbl.rowCount }, () =>
                      Array<DiCell | null>(tbl.columnCount).fill(null)
                    );
                    tbl.cells.forEach(cell => {
                      const rs = cell.rowSpan   ?? 1;
                      const cs = cell.columnSpan ?? 1;
                      placed[cell.rowIndex][cell.columnIndex] = cell;
                      for (let r = cell.rowIndex; r < cell.rowIndex + rs; r++)
                        for (let c = cell.columnIndex; c < cell.columnIndex + cs; c++)
                          if (r !== cell.rowIndex || c !== cell.columnIndex)
                            skip.add(`${r}-${c}`);
                    });
                    return (
                      <div key={ti}>
                        <Text weight="semibold" size={200}
                          style={{ display: "block", marginBottom: "6px", color: tokens.colorNeutralForeground2 }}>
                          Table {ti + 1} — {tbl.rowCount} rows × {tbl.columnCount} cols
                        </Text>
                        <div style={{ overflowX: "auto" }}>
                          <table className={styles.diTable}>
                            <tbody>
                              {placed.map((row, ri) => (
                                <tr key={ri}>
                                  {row.map((cell, ci) => {
                                    if (skip.has(`${ri}-${ci}`)) return null;
                                    if (!cell) return <td key={ci} className={styles.diTd} />;
                                    const isHdr = cell.kind === "columnHeader" || cell.kind === "rowHeader" || cell.kind === "stubHead";
                                    const rs = cell.rowSpan   && cell.rowSpan   > 1 ? cell.rowSpan   : undefined;
                                    const cs = cell.columnSpan && cell.columnSpan > 1 ? cell.columnSpan : undefined;
                                    return isHdr
                                      ? <th key={ci} rowSpan={rs} colSpan={cs} className={styles.diTh}>{cell.content}</th>
                                      : <td key={ci} rowSpan={rs} colSpan={cs} className={styles.diTd}>{cell.content}</td>;
                                  })}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            )}

            {/* ── Key-Value Pairs (DI only: analyzeResult.keyValuePairs[]) ── */}
            {activeTab === "kvpairs" && isDI && (
              diKvPairs.length === 0 ? (
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No key-value pairs extracted.</Text>
              ) : (
                <table className={styles.fieldsTable}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid ${tokens.colorNeutralStroke1}` }}>
                      <th style={{ textAlign: "left", padding: "4px 10px 6px 0", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold }}>KEY</th>
                      <th style={{ textAlign: "left", padding: "4px 0 6px",      fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold }}>VALUE</th>
                      <th style={{ textAlign: "right", padding: "4px 0 6px 8px", fontSize: tokens.fontSizeBase100, color: tokens.colorNeutralForeground3, fontWeight: tokens.fontWeightSemibold }}>CONF.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {diKvPairs.map((kv, i) => (
                      <tr key={i} className={styles.fieldsRow}>
                        <td className={styles.fieldKey}>{kv.key?.content ?? ""}</td>
                        <td className={styles.fieldVal}>{kv.value?.content ?? "(empty)"}</td>
                        <td className={styles.fieldConf} style={{ color: confidenceColor(kv.confidence) }}>
                          {kv.confidence !== undefined ? `${(kv.confidence * 100).toFixed(0)}%` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}

            {/* ── Figures (DI: analyzeResult.figures[] / CU: contents[0].figures[]) ── */}
            {activeTab === "figures" && (
              activeFigures.length === 0 ? (
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No figures extracted.</Text>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                  {activeFigures.map((fig, fi) => (
                    <div key={fi} style={{
                      border: `1px solid ${tokens.colorNeutralStroke2}`,
                      borderRadius: tokens.borderRadiusMedium,
                      overflow: "hidden",
                    }}>
                      <div style={{
                        display: "flex", alignItems: "center", gap: "8px",
                        padding: "7px 12px",
                        backgroundColor: tokens.colorNeutralBackground2,
                        borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
                      }}>
                        <Text weight="semibold" size={200}>Figure {fi + 1}</Text>
                        {fig.kind && fig.kind !== "unknown" && (
                          <Badge appearance="tint" color="informative" size="small">{fig.kind}</Badge>
                        )}
                      </div>
                      <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: "6px" }}>
                        {fig.caption?.content && (
                          <div>
                            <Text size={100} weight="semibold"
                              style={{ color: tokens.colorNeutralForeground3, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "2px" }}>
                              Caption
                            </Text>
                            <Text size={200}>{fig.caption.content}</Text>
                          </div>
                        )}
                        {fig.description && (
                          <div>
                            <Text size={100} weight="semibold"
                              style={{ color: tokens.colorNeutralForeground3, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: "2px" }}>
                              Description
                            </Text>
                            <Text size={200}>{fig.description}</Text>
                          </div>
                        )}
                        {!fig.caption?.content && !fig.description && (
                          <Text size={200} style={{ color: tokens.colorNeutralForeground3, fontStyle: "italic" }}>
                            No caption or description available.
                          </Text>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )
            )}

            {/* ── Markdown — DI: analyzeResult.content (markdown) / CU: contents[0].markdown ── */}
            {activeTab === "markdown" && (
              markdown ? (
                <div className={styles.markdownBody}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                    {markdown}
                  </ReactMarkdown>
                </div>
              ) : (
                <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No markdown content available.</Text>
              )
            )}

            {/* ── JSON Tree — full raw response ── */}
            {activeTab === "raw" && (
              <div className={styles.treeRoot}>
                <JsonNode value={result.result} depth={0} />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

// ───────────────────────────────────────────────────────────────────────────────
// ComparePage
// ───────────────────────────────────────────────────────────────────────────────
const ComparePage: React.FC = () => {
  const styles = useStyles();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [analyzers, setAnalyzers]   = useState<PrebuiltAnalyzer[]>([]);
  const [apiVersions, setApiVersions] = useState<ApiVersions | null>(null);

  const [diAnalyzerId, setDiAnalyzerId] = useState("prebuilt-invoice");
  const [cuAnalyzerId, setCuAnalyzerId] = useState("prebuilt-documentSearch");
  const [diApiVersion, setDiApiVersion] = useState("2024-11-30");
  const [cuApiVersion, setCuApiVersion] = useState("2025-11-01");

  const [file, setFile]           = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const [diResult, setDiResult]   = useState<AnalyzerResult | null>(null);
  const [cuResult, setCuResult]   = useState<AnalyzerResult | null>(null);
  const [elapsedMs, setElapsedMs] = useState<number | undefined>(undefined);

  // Track what was actually submitted (for display in result headers)
  const [runDiId, setRunDiId]           = useState("prebuilt-invoice");
  const [runCuId, setRunCuId]           = useState("prebuilt-documentSearch");
  const [runDiVersion, setRunDiVersion] = useState("2024-11-30");
  const [runCuVersion, setRunCuVersion] = useState("2025-11-01");

  const diAnalyzers = useMemo(() => analyzers.filter(a => a.source === "di"), [analyzers]);
  const cuAnalyzers = useMemo(() => analyzers.filter(a => a.source === "cu"), [analyzers]);

  const diByCategory = useMemo(() => {
    const m = new Map<string, PrebuiltAnalyzer[]>();
    diAnalyzers.forEach(a => { const c = a.category ?? "Other"; if (!m.has(c)) m.set(c, []); m.get(c)!.push(a); });
    return m;
  }, [diAnalyzers]);

  const cuByCategory = useMemo(() => {
    const m = new Map<string, PrebuiltAnalyzer[]>();
    cuAnalyzers.forEach(a => { const c = a.category ?? "Other"; if (!m.has(c)) m.set(c, []); m.get(c)!.push(a); });
    return m;
  }, [cuAnalyzers]);

  const analyzerNameMap = useMemo(
    () => Object.fromEntries(analyzers.map(a => [`${a.source}:${a.id}`, a.name])),
    [analyzers]
  );

  useEffect(() => {
    fetchPrebuiltAnalyzers().then(setAnalyzers).catch(() => {
      const fb: PrebuiltAnalyzer[] = [
        { id: "prebuilt-invoice", name: "Invoice", source: "di", description: "", category: "Finance" },
        { id: "prebuilt-layout",  name: "Layout",  source: "di", description: "", category: "Document Analysis" },
        { id: "prebuilt-documentSearch", name: "Document Search", source: "cu", description: "", category: "Content Extraction" },
        { id: "prebuilt-layout",  name: "Layout",  source: "cu", description: "", category: "Content Extraction" },
      ];
      setAnalyzers(fb);
    });
    fetchApiVersions().then(setApiVersions).catch(() => {});
  }, []);

  const handleFileSelect = (f: File) => {
    setFile(f);
    setDiResult(null);
    setCuResult(null);
    setError(null);
  };

  const onDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFileSelect(dropped);
  }, []); // eslint-disable-line

  const handleRun = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setDiResult(null);
    setCuResult(null);
    setRunDiId(diAnalyzerId);
    setRunCuId(cuAnalyzerId);
    setRunDiVersion(diApiVersion);
    setRunCuVersion(cuApiVersion);

    const t0 = Date.now();
    try {
      const res: CompareResponse = await compareAnalyzers(
        file,
        [`di:${diAnalyzerId}`, `cu:${cuAnalyzerId}`],
        diApiVersion,
        cuApiVersion
      );
      setElapsedMs(Date.now() - t0);
      setDiResult(res.results.find(r => r.analyzer_id === `di:${diAnalyzerId}`) ?? null);
      setCuResult(res.results.find(r => r.analyzer_id === `cu:${cuAnalyzerId}`) ?? null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "An error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const effectiveDiVersions = (apiVersions ?? DEFAULT_API_VERSIONS).di;
  const effectiveCuVersions = (apiVersions ?? DEFAULT_API_VERSIONS).cu;

  const diDisplayName = analyzerNameMap[`di:${runDiId}`] ?? runDiId;
  const cuDisplayName = analyzerNameMap[`cu:${runCuId}`] ?? runCuId;

  return (
    <div className={styles.page}>

      {/* ═══════════════════════════════════ LEFT PANEL ══════════════════════ */}
      <div className={styles.leftPanel}>

        {/* Title bar */}
        <div className={styles.panelTitle}>
          <DocumentRegular style={{ fontSize: "18px", color: tokens.colorBrandForeground1 }} />
          <Text weight="semibold" size={400}>Analyzer Comparison</Text>
        </div>

        {/* Document upload */}
        <div className={styles.leftSection}>
          <Text className={styles.fieldLabel}>Source Document</Text>
          <div
            className={`${styles.dropzone} ${isDragging ? styles.dropzoneActive : ""}`}
            onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === "Enter" && fileInputRef.current?.click()}
          >
            <ArrowUploadRegular style={{ fontSize: "22px", color: tokens.colorBrandForeground1 }} />
            <Text weight="semibold" size={200}>
              {isDragging ? "Drop here" : "Click or drag & drop"}
            </Text>
            <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
              PDF · JPEG · PNG · TIFF · BMP
            </Text>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.bmp"
            style={{ display: "none" }}
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
          />
          {file && (
            <div className={styles.fileChip}>
              <DocumentRegular style={{ flexShrink: 0, color: tokens.colorBrandForeground1 }} />
              <Text size={200} weight="semibold" style={{ flex: "1 1 auto", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {file.name}
              </Text>
              <Text size={100} style={{ color: tokens.colorNeutralForeground3, flexShrink: 0 }}>
                {(file.size / 1024).toFixed(0)} KB
              </Text>
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular />}
                style={{ padding: "2px", minWidth: 0, flexShrink: 0 }}
                onClick={e => { e.stopPropagation(); setFile(null); setDiResult(null); setCuResult(null); }}
              />
            </div>
          )}
        </div>

        {/* Document Intelligence config */}
        <div className={styles.leftSection}>
          <div className={styles.serviceConfigCard} style={{ borderTop: `3px solid ${DI_BORDER}` }}>
            <div className={styles.serviceCardHeader}>
              <Badge appearance="filled" color="informative">Document Intelligence</Badge>
            </div>
            <div className={styles.serviceCardBody}>
              <div>
                <div className={styles.fieldLabel}>Analyzer</div>
                <Select
                  value={diAnalyzerId}
                  onChange={(_, d) => setDiAnalyzerId(d.value)}
                  style={{ width: "100%" }}
                >
                  {Array.from(diByCategory.entries()).map(([cat, items]) => (
                    <optgroup key={cat} label={cat}>
                      {items.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </optgroup>
                  ))}
                </Select>
              </div>
              <div>
                <div className={styles.fieldLabel}>API Version</div>
                <Select
                  value={diApiVersion}
                  onChange={(_, d) => setDiApiVersion(d.value)}
                  style={{ width: "100%" }}
                >
                  {effectiveDiVersions.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
                </Select>
              </div>
            </div>
          </div>
        </div>

        {/* Content Understanding config */}
        <div className={styles.leftSection}>
          <div className={styles.serviceConfigCard} style={{ borderTop: `3px solid ${CU_BORDER}` }}>
            <div className={styles.serviceCardHeader}>
              <Badge appearance="filled" style={{ backgroundColor: CU_COLOR }}>Content Understanding</Badge>
            </div>
            <div className={styles.serviceCardBody}>
              <div>
                <div className={styles.fieldLabel}>Analyzer</div>
                <Select
                  value={cuAnalyzerId}
                  onChange={(_, d) => setCuAnalyzerId(d.value)}
                  style={{ width: "100%" }}
                >
                  {Array.from(cuByCategory.entries()).map(([cat, items]) => (
                    <optgroup key={cat} label={cat}>
                      {items.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </optgroup>
                  ))}
                </Select>
              </div>
              <div>
                <div className={styles.fieldLabel}>API Version</div>
                <Select
                  value={cuApiVersion}
                  onChange={(_, d) => setCuApiVersion(d.value)}
                  style={{ width: "100%" }}
                >
                  {effectiveCuVersions.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
                </Select>
              </div>
            </div>
          </div>
        </div>

        {/* Run button */}
        <div className={styles.runSection}>
          {error && (
            <MessageBar intent="error">
              <MessageBarBody style={{ fontSize: tokens.fontSizeBase200 }}>{error}</MessageBarBody>
            </MessageBar>
          )}
          <Button
            appearance="primary"
            size="medium"
            disabled={!file || loading}
            onClick={handleRun}
            icon={loading ? <Spinner size="tiny" /> : <PlayRegular />}
            style={{ width: "100%" }}
          >
            {loading ? "Running analysis…" : "Run Analysis"}
          </Button>
          {!file && (
            <Text size={100} style={{ color: tokens.colorNeutralForeground3, textAlign: "center" as const }}>
              Upload a document to enable
            </Text>
          )}
        </div>
      </div>

      {/* ══════════════════════ CENTER — Document Intelligence ══════════════ */}
      <div style={{ width: "1px", flexShrink: 0, backgroundColor: tokens.colorNeutralStroke2 }} />
      <ResultPane
        source="di"
        analyzerName={diDisplayName}
        analyzerId={runDiId}
        apiVersion={runDiVersion}
        result={diResult}
        loading={loading}
        elapsedMs={diResult?.elapsed_ms ?? elapsedMs}
      />

      {/* ═══════════════════════ RIGHT — Content Understanding ══════════════ */}
      <div style={{ width: "1px", flexShrink: 0, backgroundColor: tokens.colorNeutralStroke2 }} />
      <ResultPane
        source="cu"
        analyzerName={cuDisplayName}
        analyzerId={runCuId}
        apiVersion={runCuVersion}
        result={cuResult}
        loading={loading}
        elapsedMs={cuResult?.elapsed_ms ?? elapsedMs}
      />
    </div>
  );
};

export default ComparePage;
