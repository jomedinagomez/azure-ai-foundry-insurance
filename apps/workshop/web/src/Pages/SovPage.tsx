import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Card,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  DialogTrigger,
  Dropdown,
  MessageBar,
  MessageBarBody,
  Option,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Spinner,
  Tab,
  TabList,
  Text,
  Textarea,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";import {
  CheckmarkCircleFilled,
  DismissCircleFilled,
  PlayRegular,
  ArrowSyncRegular,
  ArrowUploadRegular,
  DismissRegular,
  DocumentTableRegular,
  DocumentPdfRegular,
  DocumentRegular,
} from "@fluentui/react-icons";
import {
  TransformWrapper,
  TransformComponent,
  type ReactZoomPanPinchRef,
} from "react-zoom-pan-pinch";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";

import {
  fetchAnalyzers,
  fetchAnalyzerTemplate,
  fetchCachedExtraction,
  fetchSovSamples,
  pushAnalyzerToFoundry,
  runSovPipelineStream,
  runSovUploadStream,
  runValidation,
  saveAnalyzerTemplate,
  saveResultToCache,
  uploadAndExtract,
  apiUrl,
  SovAnalyzer,
  SovExtractionResult,
  SovSample,
  SovValidationResult,
  SovValidationDiff,
  CostBreakdown,
  formatCost,
} from "../services/sovService";
import {
  fetchPipelines,
  Pipeline,
} from "../services/pipelinesService";
import AnalyzerEditor from "../Components/Sov/AnalyzerEditor";
import RunDialog, { RunStreamFn } from "../Components/Pipelines/RunDialog";

// `uploadAndExtract` is still re-exported for any consumers that want the
// non-streaming endpoint, but the page itself drives uploads through
// `runSovUploadStream` so xlsx goes through the proper TIFF → sovExtractV1
// pipeline (extract schema) instead of the legacy generate-schema fallback.
void uploadAndExtract;

function resolveUploadPipeline(
  file: File,
  pipelines: Pipeline[]
): Pipeline | null {
  const ext = "." + file.name.split(".").pop()!.toLowerCase();
  const matches = pipelines.filter((p) => p.input_extensions.includes(ext));
  return matches.find((p) => p.is_default) ?? matches[0] ?? null;
}

function makeUploadStreamFn(file: File): RunStreamFn {
  return async (pipelineId, _sampleName, cb, _saveAsCanonical, signal) => {
    await runSovUploadStream(
      file,
      {
        onStep: cb.onStep,
        onComplete: cb.onComplete,
        onError: cb.onError,
      },
      pipelineId,
      signal
    );
  };
}

// Use pdf.js's bundled worker (served by webpack). The CDN fallback the
// react-pdf docs suggest doesn't work behind corporate networks.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.js",
  import.meta.url
).toString();

function FileTypeIcon({ type }: { type: string }) {
  if (type === "xlsx") return <DocumentTableRegular style={{ color: "#107C41" }} />;
  if (type === "pdf") return <DocumentPdfRegular style={{ color: "#B00020" }} />;
  return <DocumentRegular />;
}

/**
 * Header pill that shows the estimated USD cost of a run, with a Popover
 * that breaks the total down by line item. Click the pill to reveal
 * components (CU pages, GPT completions, local compute, etc.) plus the
 * raw counters under "inputs" for transparency.
 */
function CostPill({ cost }: { cost: CostBreakdown }) {
  return (
    <Popover withArrow positioning="below">
      <PopoverTrigger disableButtonEnhancement>
        <button
          type="button"
          style={{
            cursor: "pointer",
            backgroundColor: tokens.colorBrandBackground2,
            color: tokens.colorBrandForeground1,
            border: `1px solid ${tokens.colorBrandStroke2}`,
            padding: "2px 8px",
            borderRadius: "10px",
            fontSize: 12,
            fontWeight: 600,
            lineHeight: 1.4,
          }}
          title="Estimated cost — click for breakdown"
        >
          est. {formatCost(cost)}
        </button>
      </PopoverTrigger>
      <PopoverSurface>
        <div style={{ minWidth: 320, maxWidth: 480 }}>
          <Text weight="semibold">Cost breakdown (estimate)</Text>
          <div style={{ marginTop: 8 }}>
            <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #ddd", padding: "4px 6px" }}>Component</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: "4px 6px" }}>Qty</th>
                  <th style={{ textAlign: "right", borderBottom: "1px solid #ddd", padding: "4px 6px" }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {cost.components.map((c, i) => (
                  <tr key={i}>
                    <td style={{ padding: "4px 6px" }}>{c.label}</td>
                    <td style={{ padding: "4px 6px", textAlign: "right" }}>
                      {c.qty} {c.unit}
                    </td>
                    <td style={{ padding: "4px 6px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                      ${c.amount.toFixed(4)}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td style={{ padding: "4px 6px", fontWeight: 600, borderTop: "1px solid #ddd" }}>Total</td>
                  <td style={{ borderTop: "1px solid #ddd" }}></td>
                  <td style={{ padding: "4px 6px", textAlign: "right", fontWeight: 600, borderTop: "1px solid #ddd", fontVariantNumeric: "tabular-nums" }}>
                    {formatCost(cost)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <Caption1 style={{ color: tokens.colorNeutralForeground3, marginTop: 8, display: "block" }}>
            Estimate based on configured per-unit pricing. Verify against your enterprise agreement before quoting.
          </Caption1>
          <Caption1 style={{ color: tokens.colorNeutralForeground3, marginTop: 4, display: "block" }}>
            <b>Tip:</b> Most cost comes from LLM tokens. You can lower it further
            by replacing <code>classify</code> fields with <code>extract</code>
            and normalizing values in post-processing — accuracy stays the same,
            schema gets smaller, prompts stay leaner.
          </Caption1>
        </div>
      </PopoverSurface>
    </Popover>
  );
}

const useStyles = makeStyles({
  root: {
    display: "grid",
    gridTemplateColumns: "320px 1fr",
    columnGap: "16px",
    padding: "16px",
    height: "calc(100vh - 64px)",
    boxSizing: "border-box",
  },
  rail: {
    display: "flex",
    flexDirection: "column",
    rowGap: "8px",
    overflowY: "auto",
  },
  sampleCard: {
    cursor: "pointer",
    ...shorthands.padding("8px", "10px"),
  },
  sampleCardSelected: {
    outline: `2px solid ${tokens.colorBrandStroke1}`,
  },
  main: {
    display: "flex",
    flexDirection: "column",
    rowGap: "12px",
    overflow: "hidden",
  },
  mainBody: {
    flex: 1,
    display: "grid",
    // gridTemplateColumns is set inline so the splitter can resize it.
    columnGap: "0",
    overflow: "hidden",
  },
  mainBodyNoDebug: {
    gridTemplateColumns: "1fr",
  },
  leftPane: {
    display: "flex",
    flexDirection: "column",
    rowGap: "8px",
    overflow: "hidden",
    minWidth: 0,
    paddingRight: "12px",
  },
  rightPane: {
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    borderLeft: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingLeft: "12px",
    minWidth: 0,
  },
  paneHeader: {
    display: "flex",
    alignItems: "center",
    columnGap: "8px",
    paddingBottom: "4px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    marginBottom: "4px",
  },
  splitter: {
    cursor: "col-resize",
    width: "6px",
    marginLeft: "-3px",
    marginRight: "-3px",
    position: "relative",
    zIndex: 1,
    ":hover": {
      backgroundColor: tokens.colorNeutralStroke2,
    },
  },
  rightPaneContent: {
    flex: 1,
    overflow: "auto",
    ...shorthands.padding("8px"),
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.borderRadius("4px"),
  },
  previewImg: {
    maxWidth: "100%",
    height: "auto",
    display: "block",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: "#fff",
  },
  viewerToolbar: {
    display: "flex",
    alignItems: "center",
    columnGap: "8px",
    flexWrap: "wrap",
    marginBottom: "6px",
  },
  viewerStage: {
    position: "relative",
    width: "100%",
    height: "640px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: "#f5f5f5",
    overflow: "hidden",
  },
  viewerImgWrap: {
    position: "relative",
    display: "inline-block",
    lineHeight: 0,
  },
  viewerImg: {
    display: "block",
    userSelect: "none",
    pointerEvents: "none",
  },
  viewerOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    pointerEvents: "none",
  },
  rowHoverable: {
    cursor: "default",
    ":hover": {
      backgroundColor: tokens.colorNeutralBackground2,
    },
  },
  rowHovered: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  pdfFrame: {
    width: "100%",
    minHeight: "560px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: "#fff",
  },
  mdHtml: {
    fontSize: "12px",
    lineHeight: 1.4,
    "& table": { borderCollapse: "collapse", margin: "8px 0", width: "100%" },
    "& th, & td": {
      border: `1px solid ${tokens.colorNeutralStroke2}`,
      padding: "3px 6px",
      verticalAlign: "top",
      textAlign: "left",
    },
    "& th": {
      backgroundColor: tokens.colorNeutralBackground2,
      fontWeight: 600,
    },
    "& h1": { fontSize: "16px", marginTop: "12px" },
    "& h2": { fontSize: "14px", marginTop: "10px" },
    "& h3": { fontSize: "13px", marginTop: "8px" },
    "& p": { margin: "4px 0" },
  },
  headerStrip: {
    display: "flex",
    alignItems: "center",
    columnGap: "12px",
    flexWrap: "wrap",
  },
  metaPill: {
    ...shorthands.padding("2px", "8px"),
    ...shorthands.borderRadius("12px"),
    backgroundColor: tokens.colorNeutralBackground3,
    fontSize: "12px",
  },
  tabContent: {
    flex: 1,
    overflow: "auto",
    ...shorthands.padding("8px"),
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.borderRadius("4px"),
  },
  kvTable: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px",
  },
  th: {
    textAlign: "left",
    ...shorthands.padding("6px", "8px"),
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    fontWeight: 600,
    backgroundColor: tokens.colorNeutralBackground2,
    position: "sticky",
    top: 0,
  },
  td: {
    ...shorthands.padding("6px", "8px"),
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    verticalAlign: "top",
  },
  diffMatch: { color: tokens.colorPaletteGreenForeground1 },
  diffMiss: { color: tokens.colorPaletteRedForeground1 },
  json: {
    fontFamily: "Consolas, monospace",
    fontSize: "12px",
    whiteSpace: "pre",
  },
  markdown: {
    fontFamily: "Consolas, monospace",
    fontSize: "12px",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  artifactRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    ...shorthands.padding("6px", "8px"),
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  subTabBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "4px",
  },
  dropzone: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "4px",
    ...shorthands.padding("14px", "10px"),
    border: `1.5px dashed ${tokens.colorNeutralStroke2}`,
    ...shorthands.borderRadius("6px"),
    backgroundColor: tokens.colorNeutralBackground2,
    cursor: "pointer",
    textAlign: "center",
    transitionProperty: "all",
    transitionDuration: "150ms",
    ":hover": {
      borderColor: tokens.colorBrandStroke1,
      backgroundColor: tokens.colorBrandBackground2,
    },
  },
  dropzoneActive: {
    borderColor: tokens.colorBrandStroke1,
    backgroundColor: tokens.colorBrandBackground2,
  },
  fileChip: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    ...shorthands.padding("6px", "8px"),
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    ...shorthands.borderRadius("4px"),
    backgroundColor: tokens.colorNeutralBackground1,
  },
});

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function fmtConf(c: number | null | undefined): string {
  if (c === null || c === undefined) return "—";
  return c.toFixed(2);
}

function confColor(c: number | null | undefined): string | undefined {
  if (c === null || c === undefined) return undefined;
  if (c >= 0.9) return tokens.colorPaletteGreenForeground1;
  if (c >= 0.7) return tokens.colorPaletteDarkOrangeForeground1;
  return tokens.colorPaletteRedForeground1;
}

const ACCOUNT_FIELDS: { key: keyof SovExtractionResult["account"]; label: string }[] = [
  { key: "insured_name", label: "Insured" },
  { key: "dba", label: "DBA" },
  { key: "mailing_address", label: "Mailing Address" },
  { key: "effective_date", label: "Effective" },
  { key: "expiration_date", label: "Expiration" },
  { key: "primary_operations", label: "Primary Operations" },
  { key: "naics", label: "NAICS" },
  { key: "currency", label: "Currency" },
  { key: "valuation_date", label: "Valuation Date" },
  { key: "total_insured_value", label: "Total Insured Value" },
  { key: "location_count", label: "Location Count" },
  { key: "broker_name", label: "Broker" },
  { key: "broker_contact", label: "Broker Contact" },
  { key: "broker_email", label: "Broker Email" },
  { key: "broker_phone", label: "Broker Phone" },
  { key: "prepared_by", label: "Prepared By" },
  { key: "prepared_date", label: "Prepared Date" },
];

// Account field key (snake_case) -> CU field name (PascalCase) for overlay lookup.
// Mirror of `_CU_TO_SCALAR` in apps/workshop/api/app/services/sov_service.py.
const ACCOUNT_KEY_TO_CU: Record<string, string> = {
  insured_name: "InsuredName",
  dba: "DBA",
  mailing_address: "MailingAddress",
  effective_date: "EffectiveDate",
  expiration_date: "ExpirationDate",
  primary_operations: "PrimaryOperations",
  naics: "NAICS",
  currency: "Currency",
  valuation_date: "ValuationDate",
  total_insured_value: "TotalInsuredValue",
  location_count: "LocationCount",
  broker_name: "BrokerName",
  broker_contact: "BrokerContact",
  broker_email: "BrokerEmail",
  broker_phone: "BrokerPhone",
  prepared_by: "PreparedBy",
  prepared_date: "PreparedDate",
};

// Per-location field key (snake_case) -> CU sub-field name (PascalCase).
const LOCATION_KEY_TO_CU: Record<string, string> = {
  location_number: "LocationNumber",
  building_number: "BuildingNumber",
  street: "Street",
  city: "City",
  state: "State",
  zip: "Zip",
  construction_type: "Construction",
  occupancy: "Occupancy",
  year_built: "YearBuilt",
  square_feet: "SquareFeet",
  building_value: "BuildingValue",
  bpp_value: "BppValue",
  bi_value: "BiValue",
  stories: "Stories",
  unit_count: "UnitCount",
  protection_class: "ProtectionClass",
  flood_zone: "FloodZone",
  distance_to_coast_mi: "DistanceToCoast",
  notes: "Notes",
};

// Build a stable identifier used to coordinate hover state between the Output
// pane and the image overlay. Account fields use the CU PascalCase name;
// location fields use "Locations[<idx>].<CuSubField>".
function buildFieldId(scope: "account" | "location", key: string, locIdx?: number): string | null {
  if (scope === "account") {
    const cu = ACCOUNT_KEY_TO_CU[key];
    return cu ? cu : null;
  }
  const cu = LOCATION_KEY_TO_CU[key];
  if (!cu || locIdx == null) return null;
  return `Locations[${locIdx}].${cu}`;
}

const LOCATION_COLS: { key: keyof SovExtractionResult["locations"][number]; label: string }[] = [
  { key: "location_number", label: "#" },
  { key: "street", label: "Street" },
  { key: "city", label: "City" },
  { key: "state", label: "State" },
  { key: "zip", label: "Zip" },
  { key: "construction_type", label: "Construction" },
  { key: "occupancy", label: "Occupancy" },
  { key: "year_built", label: "Yr Built" },
  { key: "square_footage", label: "Sqft" },
  { key: "building_value", label: "Bldg Value" },
  { key: "bpp_value", label: "BPP" },
  { key: "bi_ee_value", label: "BI/EE" },
  { key: "sprinklered", label: "Sprinklered" },
  { key: "flood_zone", label: "Flood" },
  { key: "source", label: "Source" },
];

export default function SovPage() {
  const styles = useStyles();
  const [samples, setSamples] = useState<SovSample[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [result, setResult] = useState<SovExtractionResult | null>(null);
  const [validation, setValidation] = useState<SovValidationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("account");
  const [showConfidence, setShowConfidence] = useState(true);

  // ── User-uploaded file (alternative to picking a bundled sample) ─────
  // Mirrors the Analyzer Compare upload UX: hidden file input + dropzone.
  // When `uploadFile` is set we bypass the pipeline RunDialog and call
  // /sov/extract/upload directly (it routes by extension server-side).
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleUploadSelect = (f: File) => {
    setUploadFile(f);
    setSelected(null);
    setResult(null);
    setValidation(null);
    setError(null);
  };
  const clearUpload = () => {
    setUploadFile(null);
    setResult(null);
    setValidation(null);
  };


  // Cross-pane hover: Output pane sets this on row hover, ImagePreview reads
  // it to highlight the corresponding polygon. Null when nothing is hovered.
  const [hoveredField, setHoveredField] = useState<string | null>(null);

  // Splitter between Output (left) and Reference (right) panes — default 50/50.
  const [splitPct, setSplitPct] = useState<number>(50);
  const mainBodyRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current || !mainBodyRef.current) return;
      const rect = mainBodyRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.max(20, Math.min(80, pct)));
    };
    const onUp = () => {
      draggingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);
  const onSplitterMouseDown = (e: React.MouseEvent) => {
    draggingRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  };

  // Pipeline picker for next Run (null = use extension default on server)
  const [runPipelineId, setRunPipelineId] = useState<string | null>(null);

  // Pipeline catalog (read-only on this page; full editing lives on /pipelines)
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);

  // Live-progress dialog (W2.4 reuse) — always shown on Run
  const [runDialogOpen, setRunDialogOpen] = useState(false);
  const [runDialogPipeline, setRunDialogPipeline] = useState<Pipeline | null>(null);

  // Analyzer mgmt
  const [analyzers, setAnalyzers] = useState<SovAnalyzer[]>([]);
  const [selectedAnalyzer, setSelectedAnalyzer] = useState<string | null>(null);
  const [analyzerDialogOpen, setAnalyzerDialogOpen] = useState(false);
  const [analyzerJson, setAnalyzerJson] = useState<string>("");
  const [analyzerLoading, setAnalyzerLoading] = useState(false);
  const [analyzerStatus, setAnalyzerStatus] = useState<string | null>(null);

  useEffect(() => {
    fetchSovSamples()
      .then((s) => {
        setSamples(s);
        if (s.length && !selected) setSelected(s[0].file_name);
      })
      .catch((e) => setError(`Failed to load samples: ${e.message}`));
    fetchAnalyzers()
      .then((a) => {
        setAnalyzers(a);
        if (a.length) setSelectedAnalyzer(a[0].template_file);
      })
      .catch((e) => setError(`Failed to load analyzers: ${e.message}`));
    fetchPipelines()
      .then(setPipelines)
      .catch((e) => setError(`Failed to load pipelines: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-load cached result when sample changes
  useEffect(() => {
    if (!selected) return;
    setError(null);
    setResult(null);
    setValidation(null);
    const sample = samples.find((s) => s.file_name === selected);
    if (sample?.has_cached_result) {
      fetchCachedExtraction(selected)
        .then(setResult)
        .catch((e) => setError(`Cache load failed: ${e.message}`));
    }
  }, [selected, samples]);

  const resolvePipelineForRun = (): Pipeline | null => {
    if (!selected) return null;
    if (runPipelineId) {
      return pipelines.find((p) => p.id === runPipelineId) ?? null;
    }
    // Auto: pick the default pipeline for this sample's extension.
    const sample = samples.find((s) => s.file_name === selected);
    if (!sample) return null;
    const ext = "." + sample.file_name.split(".").pop()!.toLowerCase();
    const matches = pipelines.filter((p) => p.input_extensions.includes(ext));
    return matches.find((p) => p.is_default) ?? matches[0] ?? null;
  };

  const onRun = async () => {
    setError(null);
    if (uploadFile) {
      // Honor explicit Pipeline selection in upload mode; otherwise pick the
      // default for the uploaded file's extension. xlsx → preflight → PDF
      // → TIFF → sovExtractV1 (extract schema).
      const p = runPipelineId
        ? pipelines.find((x) => x.id === runPipelineId) ?? null
        : resolveUploadPipeline(uploadFile, pipelines);
      if (!p) {
        setError(
          `No pipeline available for ${uploadFile.name}. Wait for /pipelines to load.`
        );
        return;
      }
      setRunDialogPipeline(p);
      setRunDialogOpen(true);
      return;
    }
    if (!selected) return;
    const p = resolvePipelineForRun();
    if (!p) {
      setError(
        `No pipeline available for ${selected}. Pick one explicitly or wait for /pipelines to load.`
      );
      return;
    }
    setRunDialogPipeline(p);
    setRunDialogOpen(true);
  };

  const onValidate = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const v = await runValidation(selected, false);
      setValidation(v);
      setTab("validation");
    } catch (e: any) {
      setError(`Validation failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const onSaveResult = async () => {
    if (!selected || !result) return;
    setLoading(true);
    setError(null);
    try {
      await saveResultToCache(selected, result.raw);
      // Reflect new cache state
      setSamples((s) => s.map((x) => (x.file_name === selected ? { ...x, has_cached_result: true } : x)));
      setError("Saved as canonical cached result.");
    } catch (e: any) {
      setError(`Save failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const selectedSample = samples.find((s) => s.file_name === selected);
  const selectedAnalyzerObj = analyzers.find((a) => a.template_file === selectedAnalyzer);

  const openAnalyzerDialog = async () => {
    if (!selectedAnalyzer) return;
    setAnalyzerStatus(null);
    setAnalyzerLoading(true);
    try {
      const tpl = await fetchAnalyzerTemplate(selectedAnalyzer);
      setAnalyzerJson(JSON.stringify(tpl, null, 2));
      setAnalyzerDialogOpen(true);
    } catch (e: any) {
      setError(`Failed to load analyzer: ${e.response?.data?.detail || e.message}`);
    } finally {
      setAnalyzerLoading(false);
    }
  };

  const onSaveAnalyzer = async () => {
    if (!selectedAnalyzer) return;
    setAnalyzerStatus(null);
    setAnalyzerLoading(true);
    try {
      const parsed = JSON.parse(analyzerJson);
      await saveAnalyzerTemplate(selectedAnalyzer, parsed);
      setAnalyzerStatus("Saved to file.");
    } catch (e: any) {
      setAnalyzerStatus(
        e instanceof SyntaxError
          ? `Invalid JSON: ${e.message}`
          : `Save failed: ${e.response?.data?.detail || e.message}`
      );
    } finally {
      setAnalyzerLoading(false);
    }
  };

  const onPushAnalyzer = async () => {
    if (!selectedAnalyzerObj) return;
    setAnalyzerStatus(null);
    setAnalyzerLoading(true);
    try {
      // Save first (so file matches what we push)
      const parsed = JSON.parse(analyzerJson);
      await saveAnalyzerTemplate(selectedAnalyzerObj.template_file, parsed);
      const r = await pushAnalyzerToFoundry(
        selectedAnalyzerObj.template_file,
        selectedAnalyzerObj.id
      );
      setAnalyzerStatus(
        `Pushed '${r.analyzer_id}' to Foundry in ${r.elapsed_sec}s` +
          (r.previous_deleted ? " (replaced previous version)" : "")
      );
    } catch (e: any) {
      setAnalyzerStatus(
        e instanceof SyntaxError
          ? `Invalid JSON: ${e.message}`
          : `Push failed: ${e.response?.data?.detail || e.message}`
      );
    } finally {
      setAnalyzerLoading(false);
    }
  };

  return (
    <div className={styles.root}>
      {/* Left rail: sample dropdown + metadata */}
      <div className={styles.rail}>
        <Text weight="semibold">Sample SOV</Text>
        <Dropdown
          value={selected ?? ""}
          selectedOptions={selected ? [selected] : []}
          onOptionSelect={(_, d) => d.optionValue && setSelected(d.optionValue)}
          placeholder="Pick a sample…"
        >
          {samples.map((s) => (
            <Option key={s.file_name} value={s.file_name} text={s.file_name}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <FileTypeIcon type={s.file_type} />
                <span>{s.file_name}</span>
              </div>
            </Option>
          ))}
        </Dropdown>
        {selectedSample && (
          <Card className={styles.sampleCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <FileTypeIcon type={selectedSample.file_type} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                <Body1 block>{selectedSample.file_name}</Body1>
                <Caption1 block>
                  {selectedSample.file_type.toUpperCase()} · {selectedSample.size_kb} KB
                  {selectedSample.has_cached_result ? " · cached" : ""}
                  {selectedSample.has_ground_truth ? " · GT" : ""}
                </Caption1>
              </div>
            </div>
          </Card>
        )}

        {/* ── Upload your own SOV ────────────────────────────────────────── */}
        <Text weight="semibold" style={{ marginTop: 12 }}>Or upload your own</Text>
        <div
          className={`${styles.dropzone}${isDragging ? " " + styles.dropzoneActive : ""}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handleUploadSelect(f);
          }}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
        >
          <ArrowUploadRegular style={{ fontSize: 20, color: tokens.colorBrandForeground1 }} />
          <Text size={200} weight="semibold">
            {isDragging ? "Drop here" : "Click or drag & drop"}
          </Text>
          <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>PDF · XLSX</Caption1>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.xlsx"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUploadSelect(f);
            e.target.value = "";
          }}
        />
        {uploadFile && (
          <div className={styles.fileChip}>
            <DocumentRegular style={{ flexShrink: 0, color: tokens.colorBrandForeground1 }} />
            <Text size={200} weight="semibold" style={{ flex: "1 1 auto", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {uploadFile.name}
            </Text>
            <Caption1 style={{ color: tokens.colorNeutralForeground3, flexShrink: 0 }}>
              {(uploadFile.size / 1024).toFixed(0)} KB
            </Caption1>
            <Button
              appearance="subtle"
              size="small"
              icon={<DismissRegular />}
              style={{ padding: 2, minWidth: 0, flexShrink: 0 }}
              onClick={(e) => { e.stopPropagation(); clearUpload(); }}
              aria-label="Clear uploaded file"
            />
          </div>
        )}
        {uploadFile && (
          <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
            Upload mode bypasses sample-bound pipelines and validation. Cached
            results and ground-truth comparison are not available.
          </Caption1>
        )}

        <Text weight="semibold" style={{ marginTop: 12 }}>Analyzer</Text>
        <Dropdown
          value={selectedAnalyzer ?? ""}
          selectedOptions={selectedAnalyzer ? [selectedAnalyzer] : []}
          onOptionSelect={(_, d) => d.optionValue && setSelectedAnalyzer(d.optionValue)}
          placeholder="Pick an analyzer…"
        >
          {analyzers.map((a) => (
            <Option key={a.template_file} value={a.template_file} text={a.id}>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span>{a.id}</span>
                <Caption1>{a.method} · {a.use_case}</Caption1>
              </div>
            </Option>
          ))}
        </Dropdown>
        {selectedAnalyzerObj && (
          <Card className={styles.sampleCard}>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <Body1>{selectedAnalyzerObj.id}</Body1>
              <Caption1>
                method: {selectedAnalyzerObj.method} · {selectedAnalyzerObj.use_case}
              </Caption1>
              <Caption1>{selectedAnalyzerObj.template_file} · {(selectedAnalyzerObj.size_bytes/1024).toFixed(1)} KB</Caption1>
              <Button size="small" appearance="primary" onClick={openAnalyzerDialog} style={{ marginTop: 4 }}>
                View / Edit
              </Button>
            </div>
          </Card>
        )}

        {/* Pipelines: read-only summary; full editing on /pipelines */}
        <Text weight="semibold" style={{ marginTop: 12 }}>Pipeline</Text>
        <Dropdown
          value={
            runPipelineId
              ? pipelines.find((p) => p.id === runPipelineId)?.name ?? runPipelineId
              : uploadFile
              ? `Auto → ${
                  resolveUploadPipeline(uploadFile, pipelines)?.name ??
                  "(no pipeline)"
                }`
              : "Auto (by file type)"
          }
          selectedOptions={[runPipelineId ?? "__auto"]}
          onOptionSelect={(_, d) => {
            const v = d.optionValue ?? "__auto";
            setRunPipelineId(v === "__auto" ? null : v);
          }}
        >
          <Option value="__auto" text="Auto (by file type)">
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span>Auto</span>
              <Caption1>
                {uploadFile
                  ? "use the default pipeline for the uploaded file's extension"
                  : "use the default pipeline for the sample's extension"}
              </Caption1>
            </div>
          </Option>
          {(uploadFile
            ? pipelines.filter((p) =>
                p.input_extensions.includes(
                  "." + uploadFile.name.split(".").pop()!.toLowerCase()
                )
              )
            : pipelines
          ).map((p) => (
            <Option key={p.id} value={p.id} text={p.name}>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span>
                  {p.name}
                  {p.is_default && " (default)"}
                </span>
                <Caption1>
                  {p.input_extensions.join(", ")} · {p.steps.length} step{p.steps.length === 1 ? "" : "s"}
                </Caption1>
              </div>
            </Option>
          ))}
        </Dropdown>
        <Card className={styles.sampleCard}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Body1>Manage pipelines</Body1>
            <Caption1>
              Edit step parameters, swap analyzers, or build new pipelines on the
              {" "}<a href="#/pipelines">Pipelines tab</a>.
            </Caption1>
          </div>
        </Card>
      </div>

      {/* Analyzer JSON dialog */}
      <Dialog open={analyzerDialogOpen} onOpenChange={(_, d) => setAnalyzerDialogOpen(d.open)}>
        <DialogSurface style={{ maxWidth: "95vw", width: 1400 }}>
          <DialogBody>
            <DialogTitle>
              {selectedAnalyzerObj?.id} — {selectedAnalyzerObj?.template_file}
            </DialogTitle>
            <DialogContent>
              {analyzerStatus && (
                <MessageBar
                  intent={analyzerStatus.toLowerCase().includes("fail") || analyzerStatus.toLowerCase().includes("invalid") ? "error" : "success"}
                  style={{ marginBottom: 8 }}
                >
                  <MessageBarBody>{analyzerStatus}</MessageBarBody>
                </MessageBar>
              )}
              <AnalyzerEditor
                initialJson={analyzerJson}
                onChange={(json) => setAnalyzerJson(json)}
              />
            </DialogContent>
            <DialogActions>
              {analyzerLoading && <Spinner size="tiny" />}
              <Button onClick={onSaveAnalyzer} disabled={analyzerLoading}>
                Save to file
              </Button>
              <Button appearance="primary" onClick={onPushAnalyzer} disabled={analyzerLoading}>
                Save & Push to Foundry
              </Button>
              <DialogTrigger disableButtonEnhancement>
                <Button appearance="secondary">Close</Button>
              </DialogTrigger>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>

      {/* Main area */}
      <div className={styles.main}>
        {error && (
          <MessageBar intent="error">
            <MessageBarBody>{error}</MessageBarBody>
          </MessageBar>
        )}

        <div className={styles.headerStrip}>
          <Text size={500} weight="semibold">{selected ?? uploadFile?.name ?? "Pick a sample"}</Text>
          {result && (
            <span className={styles.metaPill}>
              {result.meta.pipeline_name || result.meta.pipeline_id
                ? `pipeline: ${result.meta.pipeline_name ?? result.meta.pipeline_id}`
                : `analyzer: ${result.meta.analyzer_id}`}
            </span>
          )}
          {result && (
            <span className={styles.metaPill}>
              locations: {result.location_count_actual}
            </span>
          )}
          {result?.meta.from_cache && (
            <Badge appearance="outline" color="informative">cached</Badge>
          )}
          {result?.meta.image_calls != null && (
            <span className={styles.metaPill}>
              images: {result.meta.image_calls} · +rows: {result.meta.added_from_images} · complements: {result.meta.field_complements}
            </span>
          )}
          {result && (result.meta.elapsed_total_sec || result.meta.elapsed_sec) && (
            <span className={styles.metaPill}>
              {(result.meta.elapsed_total_sec ?? result.meta.elapsed_sec ?? 0).toFixed(1)}s
            </span>
          )}
          {result && (result.meta as { cost?: CostBreakdown }).cost && (
            <CostPill cost={(result.meta as { cost?: CostBreakdown }).cost!} />
          )}

          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <Button
              size="small"
              appearance={showConfidence ? "primary" : "outline"}
              onClick={() => setShowConfidence((v) => !v)}
            >
              {showConfidence ? "Hide confidence" : "Show confidence"}
            </Button>
            <Dropdown
              size="small"
              value={
                runPipelineId
                  ? pipelines.find((p) => p.id === runPipelineId)?.name ?? runPipelineId
                  : uploadFile
                  ? `Auto → ${
                      resolveUploadPipeline(uploadFile, pipelines)?.name ??
                      "(no pipeline)"
                    }`
                  : "Auto"
              }
              selectedOptions={[runPipelineId ?? "__auto"]}
              onOptionSelect={(_, d) => {
                const v = d.optionValue ?? "__auto";
                setRunPipelineId(v === "__auto" ? null : v);
              }}
              style={{ minWidth: 220 }}
            >
              <Option value="__auto" text="Auto">
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span>Auto</span>
                  <Caption1>
                    {uploadFile
                      ? "default pipeline for the uploaded file's extension"
                      : "default pipeline for sample's extension"}
                  </Caption1>
                </div>
              </Option>
              {(uploadFile
                ? pipelines.filter((p) =>
                    p.input_extensions.includes(
                      "." + uploadFile.name.split(".").pop()!.toLowerCase()
                    )
                  )
                : pipelines
              ).map((p) => (
                <Option key={p.id} value={p.id} text={p.name}>
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <span>
                      {p.name}
                      {p.is_default && " (default)"}
                    </span>
                    <Caption1>
                      {p.input_extensions.join(", ")} · {p.steps.length} step{p.steps.length === 1 ? "" : "s"}
                    </Caption1>
                  </div>
                </Option>
              ))}
            </Dropdown>
            <Button
              icon={<PlayRegular />}
              appearance="primary"
              onClick={onRun}
              disabled={(!selected && !uploadFile) || loading || runDialogOpen}
            >
              Run
            </Button>
            <Button
              onClick={onSaveResult}
              disabled={!selected || loading || !result}
            >
              Save result
            </Button>
            <Button
              onClick={onValidate}
              disabled={!selected || loading || !selectedSample?.has_ground_truth}
            >
              Validate
            </Button>
            {loading && <Spinner size="tiny" />}
          </div>
        </div>

        <div
          className={styles.mainBody}
          ref={mainBodyRef}
          style={{
            gridTemplateColumns: `minmax(0, ${splitPct}fr) 6px minmax(0, ${100 - splitPct}fr)`,
          }}
        >
          <div className={styles.leftPane}>
            <div className={styles.paneHeader}>
              <Text weight="semibold">Output</Text>
              <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
                Extracted fields from this run
              </Caption1>
            </div>
            <TabList selectedValue={tab} onTabSelect={(_, d) => setTab(String(d.value))}>
              <Tab value="account">Account</Tab>
              <Tab value="locations">Locations</Tab>
              <Tab value="raw">Raw JSON</Tab>
              <Tab value="validation" disabled={!validation}>
                Validation
                {validation && (
                  <span style={{ marginLeft: 6 }}>
                    {validation.summary.account_mismatches_in_source +
                      validation.summary.location_mismatches_in_source === 0 ? (
                      <CheckmarkCircleFilled style={{ color: "#107C10" }} />
                    ) : (
                      <DismissCircleFilled style={{ color: "#A4262C" }} />
                    )}
                  </span>
                )}
              </Tab>
            </TabList>

            <div className={styles.tabContent}>
              {!result && !loading && (
                <Text>Pick a sample on the left and click <b>Run</b>.</Text>
              )}

              {result && tab === "account" && <AccountTab result={result} showConfidence={showConfidence} onHoverField={setHoveredField} />}
              {result && tab === "locations" && <LocationsTab result={result} showConfidence={showConfidence} onHoverField={setHoveredField} />}
              {result && tab === "raw" && (
                <pre className={styles.json}>{JSON.stringify(result.raw, null, 2)}</pre>
              )}
              {validation && tab === "validation" && <ValidationTab validation={validation} result={result} />}
            </div>
          </div>

          <div
            className={styles.splitter}
            onMouseDown={onSplitterMouseDown}
            role="separator"
            aria-orientation="vertical"
            aria-valuenow={Math.round(splitPct)}
            aria-valuemin={20}
            aria-valuemax={80}
            title="Drag to resize"
          />

          <div className={styles.rightPane}>
            <div className={styles.paneHeader}>
              <Text weight="semibold">Reference</Text>
              <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
                Image sent to CU and raw markdown
              </Caption1>
            </div>
            <DebugPane result={result} hoveredField={hoveredField} />
          </div>
        </div>
      </div>

      {/* Live-progress run dialog (W2.4 reuse — drives /sov/extract/pipeline/stream
          for samples, or a synthetic one-step stream for uploaded files). */}
      {runDialogPipeline && (selected || uploadFile) && (
        <RunDialog
          open={runDialogOpen}
          pipeline={runDialogPipeline}
          sampleName={uploadFile ? uploadFile.name : selected!}
          streamFn={uploadFile ? makeUploadStreamFn(uploadFile) : runSovPipelineStream}
          onClose={() => setRunDialogOpen(false)}
          onComplete={(payload) => {
            // SOV stream emits { result: SovExtractionResult, timings, artifacts }
            const sovResult = (payload as { result?: SovExtractionResult }).result;
            if (sovResult) {
              setResult(sovResult);
              setValidation(null);
            }
          }}
        />
      )}
    </div>
  );
}

function MarkdownTab({ result }: { result: SovExtractionResult }) {
  const styles = useStyles();
  // CU returns markdown per page in payload.contents[*].markdown
  const raw = result.raw as { contents?: Array<{ markdown?: string }> };
  const blocks = (raw.contents ?? [])
    .map((c, i) => ({ idx: i, md: c?.markdown ?? "" }))
    .filter((b) => b.md.trim().length > 0);
  if (blocks.length === 0) {
    return <Text>No markdown available in this extraction payload.</Text>;
  }
  return (
    <div>
      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
        Markdown returned by Content Understanding (one block per page).
      </Text>
      {blocks.map((b) => (
        <details key={b.idx} open={blocks.length === 1} style={{ marginTop: 12 }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>
            Page {b.idx + 1} ({b.md.length.toLocaleString()} chars)
          </summary>
          <div
            className={styles.mdHtml}
            dangerouslySetInnerHTML={{ __html: sanitizeMarkdownHtml(b.md) }}
          />
        </details>
      ))}
    </div>
  );
}

// Strip script/iframe tags and inline event handlers before injecting CU markdown
// (CU returns rich markdown that often includes raw HTML tables).
function sanitizeMarkdownHtml(s: string): string {
  return s
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<iframe[^>]*>[\s\S]*?<\/iframe>/gi, "")
    .replace(/\s+on\w+\s*=\s*"[^"]*"/gi, "")
    .replace(/\s+on\w+\s*=\s*'[^']*'/gi, "")
    .replace(/javascript:/gi, "");
}

type DebugSubTab = "image" | "markdown" | "artifacts";

function DebugPane({
  result,
  hoveredField,
}: {
  result: SovExtractionResult | null;
  hoveredField: string | null;
}) {
  const styles = useStyles();
  const [sub, setSub] = useState<DebugSubTab>("image");
  if (!result) {
    return (
      <>
        <div className={styles.subTabBar}>
          <Text weight="semibold">Debug pane</Text>
        </div>
        <div className={styles.rightPaneContent}>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
            Run a pipeline to see the rasterized image, returned markdown, and downloadable artifacts.
          </Text>
        </div>
      </>
    );
  }
  return (
    <>
      <div className={styles.subTabBar}>
        <TabList
          size="small"
          selectedValue={sub}
          onTabSelect={(_, d) => setSub(d.value as DebugSubTab)}
        >
          <Tab value="image">Image preview</Tab>
          <Tab value="markdown">Markdown</Tab>
          <Tab value="artifacts">Artifacts</Tab>
        </TabList>
      </div>
      <div className={styles.rightPaneContent}>
        {sub === "image" && <ImagePreview result={result} hoveredField={hoveredField} />}
        {sub === "markdown" && <MarkdownTab result={result} />}
        {sub === "artifacts" && <ArtifactsTab result={result} />}
      </div>
    </>
  );
}

// ── Image / PDF visualizer ─────────────────────────────────────────────────
// Parses CU `source` polygon strings of the form
//   "D(page,x1,y1,x2,y2,x3,y3,x4,y4);D(...)"
// (coords in source-pixel space) into a list of {page, points[]} regions.
type Polygon = { page: number; points: { x: number; y: number }[] };

function parseSource(src: string | undefined): Polygon[] {
  if (!src) return [];
  const out: Polygon[] = [];
  const re = /D\(\s*(\d+)\s*,([^)]+)\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    const page = parseInt(m[1], 10);
    const nums = m[2]
      .split(",")
      .map((s) => parseFloat(s.trim()))
      .filter((n) => Number.isFinite(n));
    const points: { x: number; y: number }[] = [];
    for (let i = 0; i + 1 < nums.length; i += 2) {
      points.push({ x: nums[i], y: nums[i + 1] });
    }
    if (points.length >= 3) out.push({ page, points });
  }
  return out;
}

// Walk the CU result extracting every field's polygons + an identifier
// that matches what AccountTab/LocationsTab emits on hover.
type FieldRegion = { id: string; label: string; polygons: Polygon[] };

function extractFieldRegions(result: SovExtractionResult): FieldRegion[] {
  const raw = result.raw as {
    contents?: { fields?: Record<string, unknown> }[];
  };
  const fields = raw.contents?.[0]?.fields ?? {};
  const out: FieldRegion[] = [];
  for (const [name, val] of Object.entries(fields)) {
    if (!val || typeof val !== "object") continue;
    const v = val as { source?: string; valueArray?: unknown[] };
    if (typeof v.source === "string") {
      const polys = parseSource(v.source);
      if (polys.length) out.push({ id: name, label: name, polygons: polys });
    }
    // Locations array: each entry has nested fields with their own `source`.
    if (name === "Locations" && Array.isArray(v.valueArray)) {
      v.valueArray.forEach((item, idx) => {
        const obj = item as { valueObject?: Record<string, { source?: string }> };
        const sub = obj.valueObject ?? {};
        for (const [subName, subVal] of Object.entries(sub)) {
          if (subVal && typeof subVal === "object" && typeof subVal.source === "string") {
            const polys = parseSource(subVal.source);
            if (polys.length) {
              out.push({
                id: `Locations[${idx}].${subName}`,
                label: `Locations[${idx}].${subName}`,
                polygons: polys,
              });
            }
          }
        }
      });
    }
  }
  return out;
}

type ArtifactInfo = {
  name: string;
  size: number;
  suffix: string;
  pages: number;
  page_dimensions?: { width: number; height: number }[];
};

function ImagePreview({
  result,
  hoveredField,
}: {
  result: SovExtractionResult;
  hoveredField: string | null;
}) {
  const meta = result.meta as { pipeline_artifacts?: Record<string, string> };
  const artifacts = meta.pipeline_artifacts ?? {};
  const regions = useMemo(() => extractFieldRegions(result), [result]);

  // Prefer TIFF (the artifact actually sent to CU); fall back to PDF.
  // Match the extension anywhere in the URL — the `/sov/samples/{name}/raw`
  // route appends `/raw` after the filename, so a $-anchored regex misses it.
  const tiffEntry = Object.entries(artifacts).find(([, u]) => /\.tiff?\b/i.test(u));
  const pdfEntry = Object.entries(artifacts).find(([, u]) => /\.pdf\b/i.test(u));
  const entry = tiffEntry ?? pdfEntry;

  if (!entry) {
    return (
      <Text>
        No image / PDF artifact in this pipeline. (Visualizer is available for
        pipelines that emit a rasterized TIFF or PDF, e.g.{" "}
        <code>xlsx_via_pdf_tiff</code>.)
      </Text>
    );
  }
  const [key, url] = entry;
  const isPdf = !tiffEntry;

  return isPdf ? (
    <PdfPreview artifactKey={key} url={url} />
  ) : (
    <TiffPreview
      artifactKey={key}
      url={url}
      regions={regions}
      hoveredField={hoveredField}
    />
  );
}

function PdfPreview({ artifactKey, url }: { artifactKey: string; url: string }) {
  const styles = useStyles();
  const src = apiUrl(url);
  const [numPages, setNumPages] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const transformRef = useRef<ReactZoomPanPinchRef | null>(null);

  // react-pdf needs a stable file ref — passing { url } object is fine but
  // the docs warn against re-creating it on every render. Memoize.
  const file = useMemo(() => ({ url: src }), [src]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 600 }}>
      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
        PDF artifact (<code>{artifactKey}</code>) rendered with pdf.js. Scroll
        to zoom, drag to pan.
      </Text>

      <div className={styles.viewerToolbar} style={{ marginTop: 8 }}>
        <Button size="small" onClick={() => transformRef.current?.zoomOut()}>−</Button>
        <Button size="small" onClick={() => transformRef.current?.resetTransform()}>Fit</Button>
        <Button size="small" onClick={() => transformRef.current?.zoomIn()}>+</Button>
        {numPages > 1 && (
          <>
            <span style={{ marginLeft: 12 }}>Page</span>
            <Button
              size="small"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              ◀
            </Button>
            <span>{page} / {numPages}</span>
            <Button
              size="small"
              disabled={page >= numPages}
              onClick={() => setPage((p) => Math.min(numPages, p + 1))}
            >
              ▶
            </Button>
          </>
        )}
        <a href={src} target="_blank" rel="noreferrer" style={{ marginLeft: "auto" }}>
          Open in new tab
        </a>
      </div>

      <div className={styles.viewerStage} style={{ flex: 1 }}>
        <TransformWrapper
          ref={transformRef}
          minScale={0.2}
          maxScale={8}
          initialScale={1}
          wheel={{ step: 0.15 }}
          doubleClick={{ disabled: false, mode: "reset" }}
        >
          <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }}>
            <Document
              file={file}
              onLoadSuccess={({ numPages: n }) => {
                setNumPages(n);
                setPage(1);
              }}
              loading={<Text>Loading PDF…</Text>}
              error={<Text>Failed to load PDF.</Text>}
            >
              <Page
                pageNumber={page}
                width={900}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>
          </TransformComponent>
        </TransformWrapper>
      </div>
    </div>
  );
}

function TiffPreview({
  artifactKey,
  url,
  regions,
  hoveredField,
}: {
  artifactKey: string;
  url: string;
  regions: FieldRegion[];
  hoveredField: string | null;
}) {
  const styles = useStyles();
  const [info, setInfo] = useState<ArtifactInfo | null>(null);
  const [page, setPage] = useState<number>(0);
  const [showAll, setShowAll] = useState<boolean>(false);

  // Per-page rendered image natural size (PNG after server-side max_dim resize).
  const [renderedSize, setRenderedSize] = useState<{ w: number; h: number } | null>(null);
  const transformRef = useRef<ReactZoomPanPinchRef | null>(null);

  // Fetch artifact info to learn page count + source dimensions.
  useEffect(() => {
    let cancelled = false;
    setInfo(null);
    setPage(0);
    fetch(apiUrl(`${url}/info`))
      .then((r) => r.json())
      .then((j: ArtifactInfo) => {
        if (!cancelled) setInfo(j);
      })
      .catch(() => {
        /* leave info null; we still render the image */
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  // When overlay is on, request the untrimmed PNG so CU's source-pixel
  // coordinates map 1:1 (after a single uniform scale). Trim shifts the
  // origin and would require returning the bbox to the client.
  const trim = showAll || hoveredField ? 0 : 1;
  const pngUrl = apiUrl(`${url}?as=png&page=${page}&trim=${trim}&max_dim=2400`);

  const sourceDims = info?.page_dimensions?.[page];
  // Scale factor source-pixel -> rendered-pixel. If we don't know either, fall
  // back to 1 (overlay will simply be unaligned).
  const scale =
    sourceDims && renderedSize
      ? Math.min(renderedSize.w / sourceDims.width, renderedSize.h / sourceDims.height)
      : 1;

  const visibleRegions = regions
    .map((r) => ({
      ...r,
      polygons: r.polygons.filter((p) => p.page === page + 1),
    }))
    .filter((r) => r.polygons.length > 0);

  const fitToWidth = () => {
    transformRef.current?.resetTransform();
  };

  return (
    <div>
      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
        Rasterized SOV sent to Content Understanding (<code>{artifactKey}</code>).
        Scroll to zoom, drag to pan. Hover an Output row to highlight its source region.
      </Text>

      <div className={styles.viewerToolbar} style={{ marginTop: 8 }}>
        <Button size="small" onClick={() => transformRef.current?.zoomOut()}>−</Button>
        <Button size="small" onClick={fitToWidth}>Fit</Button>
        <Button size="small" onClick={() => transformRef.current?.zoomIn()}>+</Button>
        <Button
          size="small"
          appearance={showAll ? "primary" : "secondary"}
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? "Hide" : "Show"} all field boxes
        </Button>
        {info && info.pages > 1 && (
          <>
            <span style={{ marginLeft: 12 }}>Page</span>
            <Button
              size="small"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ◀
            </Button>
            <span>{page + 1} / {info.pages}</span>
            <Button
              size="small"
              disabled={page >= info.pages - 1}
              onClick={() => setPage((p) => Math.min(info.pages - 1, p + 1))}
            >
              ▶
            </Button>
          </>
        )}
      </div>

      <div className={styles.viewerStage}>
        <TransformWrapper
          ref={transformRef}
          minScale={0.2}
          maxScale={8}
          initialScale={1}
          wheel={{ step: 0.15 }}
          doubleClick={{ disabled: false, mode: "reset" }}
        >
          <TransformComponent wrapperStyle={{ width: "100%", height: "100%" }}>
            <div className={styles.viewerImgWrap}>
              <img
                src={pngUrl}
                alt={`SOV preview page ${page + 1}`}
                className={styles.viewerImg}
                onLoad={(e) => {
                  const img = e.currentTarget;
                  setRenderedSize({ w: img.naturalWidth, h: img.naturalHeight });
                }}
              />
              {renderedSize && sourceDims && (showAll || hoveredField) && (
                <svg
                  className={styles.viewerOverlay}
                  width={renderedSize.w}
                  height={renderedSize.h}
                  viewBox={`0 0 ${renderedSize.w} ${renderedSize.h}`}
                >
                  {visibleRegions.map((r) =>
                    r.polygons.map((poly, pi) => {
                      const isHovered = hoveredField === r.id;
                      // When hovering, only draw the hovered field unless
                      // showAll is on (in which case still highlight it).
                      if (!showAll && !isHovered) return null;
                      const pts = poly.points
                        .map((p) => `${p.x * scale},${p.y * scale}`)
                        .join(" ");
                      return (
                        <polygon
                          key={`${r.id}-${pi}`}
                          points={pts}
                          fill={isHovered ? "rgba(0,120,212,0.20)" : "rgba(0,120,212,0.08)"}
                          stroke={isHovered ? "#0078d4" : "#0078d4"}
                          strokeWidth={isHovered ? 3 : 1.5}
                          strokeOpacity={isHovered ? 1 : 0.55}
                        />
                      );
                    })
                  )}
                </svg>
              )}
            </div>
          </TransformComponent>
        </TransformWrapper>
      </div>

      <div style={{ marginTop: 8 }}>
        <a href={apiUrl(url)} download>
          Download original .tiff
        </a>
      </div>
    </div>
  );
}

function ArtifactsTab({ result }: { result: SovExtractionResult }) {
  const styles = useStyles();
  const meta = result.meta as { pipeline_artifacts?: Record<string, string>; run_id?: string };
  const artifacts = meta.pipeline_artifacts ?? {};
  const entries = Object.entries(artifacts);
  if (entries.length === 0) {
    return (
      <Text>
        No pipeline artifacts available. Run a pipeline (e.g.{" "}
        <code>xlsx_via_pdf_tiff</code>) to produce downloadable intermediates.
      </Text>
    );
  }
  return (
    <div>
      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>
        Intermediate files produced by this pipeline run. Useful for inspecting
        the rendered PDF / rasterized TIFF before extraction.
      </Text>
      <div style={{ marginTop: 12 }}>
        {entries.map(([key, url]) => {
          const isDownload = url.startsWith("/sov/runs/");
          const fileName = url.split("/").pop() ?? key;
          return (
            <div key={key} className={styles.artifactRow}>
              <span style={{ minWidth: 140, fontWeight: 600 }}>{key}</span>
              {isDownload ? (
                <a href={apiUrl(url)} download={fileName}>
                  {fileName}
                </a>
              ) : (
                <span style={{ color: tokens.colorNeutralForeground3 }}>{url}</span>
              )}
            </div>
          );
        })}
      </div>
      {meta.run_id && (
        <Text size={200} style={{ color: tokens.colorNeutralForeground3, marginTop: 8 }}>
          run_id: <code>{meta.run_id}</code>
        </Text>
      )}
    </div>
  );
}

function AccountTab({
  result,
  showConfidence,
  onHoverField,
}: {
  result: SovExtractionResult;
  showConfidence: boolean;
  onHoverField?: (id: string | null) => void;
}) {
  const styles = useStyles();
  return (
    <table className={styles.kvTable}>
      <thead>
        <tr>
          <th className={styles.th}>Field</th>
          <th className={styles.th}>Value</th>
          {showConfidence && <th className={styles.th} style={{ width: 90 }}>Confidence</th>}
        </tr>
      </thead>
      <tbody>
        {ACCOUNT_FIELDS.map(({ key, label }) => {
          const c = result.account_confidence?.[key as string];
          const fieldId = buildFieldId("account", key as string);
          return (
            <tr
              key={key}
              className={styles.rowHoverable}
              onMouseEnter={() => fieldId && onHoverField?.(fieldId)}
              onMouseLeave={() => onHoverField?.(null)}
            >
              <td className={styles.td} style={{ width: 200 }}>{label}</td>
              <td className={styles.td}>{fmt(result.account[key])}</td>
              {showConfidence && (
                <td className={styles.td} style={{ color: confColor(c) }}>{fmtConf(c)}</td>
              )}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function LocationsTab({
  result,
  showConfidence,
  onHoverField,
}: {
  result: SovExtractionResult;
  showConfidence: boolean;
  onHoverField?: (id: string | null) => void;
}) {
  const styles = useStyles();
  return (
    <table className={styles.kvTable}>
      <thead>
        <tr>
          {LOCATION_COLS.map((c) => (
            <th key={String(c.key)} className={styles.th}>{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {result.locations.map((loc, i) => {
          const conf = result.locations_confidence?.[i] ?? {};
          return (
            <tr
              key={i}
              className={styles.rowHoverable}
              onMouseLeave={() => onHoverField?.(null)}
            >
              {LOCATION_COLS.map((col) => {
                const c = conf[col.key as string];
                const fieldId = buildFieldId("location", col.key as string, i);
                return (
                  <td
                    key={String(col.key)}
                    className={styles.td}
                    onMouseEnter={() => fieldId && onHoverField?.(fieldId)}
                  >
                    <span>{fmt(loc[col.key])}</span>
                    {showConfidence && c != null && (
                      <span
                        style={{
                          marginLeft: 6,
                          fontSize: 10,
                          color: confColor(c),
                          opacity: 0.85,
                        }}
                      >
                        {fmtConf(c)}
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ValidationTab({
  validation,
  result,
}: {
  validation: SovValidationResult;
  result: SovExtractionResult | null;
}) {
  const styles = useStyles();
  const [showAll, setShowAll] = useState(false);

  const accountConf = result?.account_confidence ?? {};
  // Map loc number -> per-field confidence dict
  const locConfByKey = useMemo(() => {
    const map: Record<string, Record<string, number | null>> = {};
    if (!result) return map;
    result.locations.forEach((loc, i) => {
      const k = loc.location_number;
      if (k === null || k === undefined) return;
      map[String(k)] = result.locations_confidence?.[i] ?? {};
    });
    return map;
  }, [result]);

  const accountDiffs = useMemo(
    () => validation.account.filter((d) => showAll || (d.in_source && !d.match)),
    [validation, showAll]
  );

  const locDiffs = useMemo(() => {
    const filtered = validation.locations.filter(
      (d) => showAll || (d.in_source && !d.match)
    );
    // Sort numerically by location_key (1, 2, 3 ...) instead of lexicographic.
    return [...filtered].sort((a, b) => {
      const ka = a.location_key, kb = b.location_key;
      const na = typeof ka === "number" ? ka : parseFloat(String(ka));
      const nb = typeof kb === "number" ? kb : parseFloat(String(kb));
      const aNum = !isNaN(na), bNum = !isNaN(nb);
      if (aNum && bNum && na !== nb) return na - nb;
      if (aNum && !bNum) return -1;
      if (!aNum && bNum) return 1;
      return String(ka ?? "").localeCompare(String(kb ?? ""));
    });
  }, [validation, showAll]);

  const total =
    validation.summary.account_mismatches_in_source +
    validation.summary.location_mismatches_in_source;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <Badge appearance="filled" color={total === 0 ? "success" : "danger"}>
          {total} in-source mismatches
        </Badge>
        <Caption1>
          locations actual: {validation.summary.location_count_actual} ·
          expected: {validation.summary.location_count_expected}
        </Caption1>
        <Button size="small" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Show mismatches only" : "Show all fields"}
        </Button>
      </div>

      <Text weight="semibold">
        Account ({validation.summary.account_mismatches_in_source} in-source mismatches)
      </Text>
      <DiffTable
        rows={accountDiffs}
        getConfidence={(d) => accountConf[d.field]}
      />

      <Text weight="semibold">
        Locations ({validation.summary.location_mismatches_in_source} in-source mismatches)
      </Text>
      <DiffTable
        rows={locDiffs}
        showLocKey
        getConfidence={(d) =>
          d.location_key != null
            ? locConfByKey[String(d.location_key)]?.[d.field]
            : null
        }
      />
    </div>
  );
}

function DiffTable({
  rows,
  showLocKey,
  getConfidence,
}: {
  rows: SovValidationDiff[];
  showLocKey?: boolean;
  getConfidence?: (d: SovValidationDiff) => number | null | undefined;
}) {
  const styles = useStyles();
  if (!rows.length) return <Caption1>(none)</Caption1>;
  return (
    <table className={styles.kvTable}>
      <thead>
        <tr>
          {showLocKey && <th className={styles.th}>Loc</th>}
          <th className={styles.th}>Field</th>
          <th className={styles.th}>Actual</th>
          <th className={styles.th}>Expected</th>
          {getConfidence && <th className={styles.th} style={{ width: 90 }}>Confidence</th>}
          <th className={styles.th}>In source</th>
          <th className={styles.th}>Match</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((d, i) => {
          const c = getConfidence?.(d);
          return (
            <tr key={i}>
              {showLocKey && <td className={styles.td}>{fmt(d.location_key)}</td>}
              <td className={styles.td}>{d.field}</td>
              <td className={styles.td}>{fmt(d.actual)}</td>
              <td className={styles.td}>{fmt(d.expected)}</td>
              {getConfidence && (
                <td className={styles.td} style={{ color: confColor(c) }}>{fmtConf(c)}</td>
              )}
              <td className={styles.td}>{d.in_source ? "yes" : "no"}</td>
              <td className={`${styles.td} ${d.match ? styles.diffMatch : styles.diffMiss}`}>
                {d.match ? "✓" : "✗"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
