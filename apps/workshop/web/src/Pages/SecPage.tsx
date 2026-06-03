import React, { useEffect, useRef, useState } from "react";
import {
  Badge,
  Body1Strong,
  Button,
  Caption1,
  Card,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Dropdown,
  Option,
  Popover,
  PopoverSurface,
  PopoverTrigger,
  Switch,
  Tab,
  TabList,
  Text,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import {
  PlayRegular,
  SaveRegular,
  CheckmarkCircleRegular,
  DocumentPdfRegular,
  DocumentDataRegular,
  DocumentRegular,
  ArrowUploadRegular,
  DismissRegular,
} from "@fluentui/react-icons";
import { toast } from "react-toastify";

import {
  fetchSecSamples,
  runSecExtractionStream,
  runSecExtractionUploadStream,
  runSecValidation,
  saveSecExpected,
  secSampleFileUrl,
  apiUrl,
  formatCost,
  SecSample,
  SecExtractionResult,
  SecStepEvent,
  SecValidationResult,
  CostBreakdown,
} from "../services/secService";
import StatementTabs from "../Components/Sec/StatementTabs";
import RunProgress from "../Components/Sec/RunProgress";
import ValidationPanel from "../Components/Sec/ValidationPanel";
import RawJsonPanel from "../Components/Sec/RawJsonPanel";
import SourcePdfViewer from "../Components/Sec/SourcePdfViewer";

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
  sampleCard: { ...shorthands.padding("8px", "10px") },
  main: {
    display: "flex",
    flexDirection: "column",
    rowGap: "8px",
    overflow: "hidden",
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
  mainBody: {
    flex: 1,
    display: "grid",
    columnGap: "0",
    overflow: "hidden",
  },
  mainBodyNoDebug: { gridTemplateColumns: "1fr" },
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
    ":hover": { backgroundColor: tokens.colorNeutralStroke2 },
  },
  paneContent: {
    flex: 1,
    overflow: "auto",
    ...shorthands.padding("8px"),
    backgroundColor: tokens.colorNeutralBackground1,
    ...shorthands.borderRadius("4px"),
  },
  artifactRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    ...shorthands.padding("6px", "8px"),
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
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
        </div>
      </PopoverSurface>
    </Popover>
  );
}

type OutputTab = "statements" | "raw" | "validation";
type RefTab = "preview" | "artifacts";

export default function SecPage() {
  const styles = useStyles();
  const [samples, setSamples] = useState<SecSample[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [useCache, setUseCache] = useState(true);
  const [events, setEvents] = useState<SecStepEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [runDialogOpen, setRunDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SecExtractionResult | null>(null);
  const [validation, setValidation] = useState<SecValidationResult | null>(null);
  const [outTab, setOutTab] = useState<OutputTab>("statements");
  const [refTab, setRefTab] = useState<RefTab>("preview");
  const [savingGt, setSavingGt] = useState(false);
  const [validating, setValidating] = useState(false);
  const [showConfidence, setShowConfidence] = useState(true);
  const [pdfPage, setPdfPage] = useState<number>(1);

  // ── User-uploaded PDF (alternative to picking a bundled sample) ─────
  // When `uploadFile` is set we hit /sec/extract/upload/stream which never
  // touches the canonical cache so sample fixtures stay pristine.
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadObjectUrl, setUploadObjectUrl] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!uploadFile) {
      setUploadObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(uploadFile);
    setUploadObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [uploadFile]);

  const handleUploadSelect = (f: File) => {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Only PDF uploads are supported for SEC extraction.");
      return;
    }
    setUploadFile(f);
    setSelected("");
    setResult(null);
    setValidation(null);
    setEvents([]);
    setError(null);
    setPdfPage(1);
  };
  const clearUpload = () => {
    setUploadFile(null);
    setResult(null);
    setValidation(null);
  };

  const handleSelectStatement = (stmt: { page_start?: number | null }) => {
    if (stmt.page_start && stmt.page_start > 0) {
      setPdfPage(stmt.page_start);
      setRefTab("preview");
    }
  };

  // Splitter — output vs reference panes, default 55/45 to favor data.
  const [splitPct, setSplitPct] = useState<number>(55);
  const mainBodyRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!draggingRef.current || !mainBodyRef.current) return;
      const rect = mainBodyRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPct(Math.max(25, Math.min(80, pct)));
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

  useEffect(() => {
    fetchSecSamples()
      .then((s) => {
        setSamples(s);
        if (s.length > 0) setSelected(s[0].file_name);
      })
      .catch((e) => toast.error(`Failed to load samples: ${e}`));
  }, []);

  const handleRun = async () => {
    if (!selected && !uploadFile) return;
    setRunning(true);
    setError(null);
    setEvents([]);
    setResult(null);
    setValidation(null);
    setRunDialogOpen(true);
    try {
      if (uploadFile) {
        await runSecExtractionUploadStream(uploadFile, {
          onStep: (evt) => setEvents((prev) => [...prev, evt]),
          onComplete: (r) => setResult(r),
          onError: (e) => setError(e),
        });
      } else {
        await runSecExtractionStream(selected, {
          useCache,
          // When running live, persist the raw CU response so the next
          // load can recover per-segment page numbers (click-to-jump).
          saveAsCanonical: !useCache,
          onStep: (evt) => setEvents((prev) => [...prev, evt]),
          onComplete: (r) => setResult(r),
          onError: (e) => setError(e),
        });
      }
    } catch {
      /* error already surfaced */
    } finally {
      setRunning(false);
    }
  };

  const handleValidate = async () => {
    if (!result) return;
    setValidating(true);
    try {
      const v = await runSecValidation(result);
      setValidation(v);
      setOutTab("validation");
      if (!v.has_ground_truth) {
        toast.info("No ground truth on file — use Save result to seed it.");
      }
    } catch (e: any) {
      toast.error(`Validate failed: ${e?.message ?? e}`);
    } finally {
      setValidating(false);
    }
  };

  const handleSaveGt = async () => {
    if (!result) return;
    setSavingGt(true);
    try {
      const r = await saveSecExpected(result);
      toast.success(`Wrote ${r.written} (${(r.bytes / 1024).toFixed(1)} KB)`);
      const v = await runSecValidation(result);
      setValidation(v);
      const s = await fetchSecSamples();
      setSamples(s);
    } catch (e: any) {
      toast.error(`Save failed: ${e?.message ?? e}`);
    } finally {
      setSavingGt(false);
    }
  };

  // Auto-validate after each successful run.
  useEffect(() => {
    if (!result) return;
    runSecValidation(result)
      .then(setValidation)
      .catch(() => setValidation(null));
  }, [result]);

  const sample = samples.find((s) => s.file_name === selected);
  const cost = result?.meta?.cost as CostBreakdown | undefined;
  const hasCost = !!cost && typeof (cost as any).total === "number";
  const excelUrl = result?.meta?.artifacts?.excel
    ? apiUrl(result.meta.artifacts.excel)
    : null;
  const pdfUrl = uploadFile
    ? uploadObjectUrl
    : selected
    ? secSampleFileUrl(selected)
    : null;
  const fileStem = uploadFile
    ? uploadFile.name.replace(/\.[^.]+$/, "")
    : selected
    ? selected.replace(/\.[^.]+$/, "")
    : "sec";
  const headerName = uploadFile?.name || selected || "—";

  const segCount = result?.meta?.segment_categories
    ? Object.values(result.meta.segment_categories).reduce(
        (a: number, b: any) => a + (typeof b === "number" ? b : 0),
        0
      )
    : null;

  return (
    <div className={styles.root}>
      {/* ── Left rail ────────────────────────────────────────────────── */}
      <div className={styles.rail}>
        <div>
          <Caption1>Sample 10-K / 10-Q</Caption1>
          <Dropdown
            value={selected}
            selectedOptions={[selected]}
            onOptionSelect={(_, d) => {
              const v = (d.optionValue as string) ?? "";
              setSelected(v);
              if (v) setUploadFile(null);
            }}
            disabled={running || samples.length === 0}
            style={{ width: "100%" }}
          >
            {samples.map((s) => (
              <Option key={s.file_name} value={s.file_name} text={s.file_name}>
                {s.file_name}
              </Option>
            ))}
          </Dropdown>
        </div>

        {sample && !uploadFile && (
          <Card className={styles.sampleCard}>
            <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <DocumentPdfRegular style={{ color: "#B00020", fontSize: 24, flex: "0 0 24px" }} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <Text weight="semibold" style={{ wordBreak: "break-word" }}>
                  {sample.file_name}
                </Text>
                <div>
                  <Caption1>
                    PDF · {sample.size_kb.toFixed(0)} KB
                    {sample.has_cached_result ? " · cached" : ""}
                    {sample.has_ground_truth ? " · GT" : ""}
                  </Caption1>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* ── Upload your own PDF ───────────────────────────── */}
        <Text weight="semibold" style={{ marginTop: 8 }}>Or upload your own</Text>
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
          <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>PDF only</Caption1>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUploadSelect(f);
            e.target.value = "";
          }}
        />
        {uploadFile && (
          <div className={styles.fileChip}>
            <DocumentPdfRegular style={{ flexShrink: 0, color: "#B00020" }} />
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
            Upload mode always runs live (cache and ground-truth comparison are disabled).
          </Caption1>
        )}

        <div>
          <Caption1>Classifier</Caption1>
          <Card className={styles.sampleCard}>
            <Text weight="semibold">secClassifierV1</Text>
            <Caption1>
              method: classify → analyze
              <br />
              5 financial-statement categories
            </Caption1>
            <Caption1 style={{ marginTop: 4, color: tokens.colorNeutralForeground3 }}>
              analyzer: <code>secFinancialTablesV1</code>
            </Caption1>
          </Card>
        </div>

        <div>
          <Caption1>Options</Caption1>
          <Card className={styles.sampleCard}>
            <Switch
              checked={useCache}
              onChange={(_, d) => setUseCache(!!d.checked)}
              label="Use cached result when available"
              disabled={running}
            />
            <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
              Off = call Content Understanding live. Cached payloads return instantly with no Azure cost.
            </Caption1>
          </Card>
        </div>

        <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
          Workshop notebooks at <code>demo/sec/notebooks/</code> call the same
          service functions used here — no drift between UI and code.
        </Caption1>
      </div>

      {/* ── Main column ──────────────────────────────────────────────── */}
      <div className={styles.main}>
        {/* Top header strip */}
        <div className={styles.headerStrip}>
          <Body1Strong>{headerName}</Body1Strong>
          <span className={styles.metaPill}>pipeline: classify → analyze</span>
          {result && (
            <>
              <span className={styles.metaPill}>
                {result.statements.length} statements
                {segCount != null ? ` · ${segCount} segments` : ""}
              </span>
              {result.meta.elapsed_sec != null && (
                <span className={styles.metaPill}>
                  {result.meta.elapsed_sec.toFixed(1)}s
                </span>
              )}
              {result.meta.from_cache && (
                <Badge appearance="filled" color="informative">cache</Badge>
              )}
              {result.meta.retries ? (
                <Badge appearance="outline" color="warning">
                  {result.meta.retries} retries
                </Badge>
              ) : null}
              {hasCost ? (
                <CostPill cost={cost as CostBreakdown} />
              ) : (
                <span
                  className={styles.metaPill}
                  title="No CU usage block in this payload (typical for cached runs)"
                >
                  est. n/a
                </span>
              )}
            </>
          )}

          <span style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <Switch
              checked={showConfidence}
              onChange={(_, d) => setShowConfidence(!!d.checked)}
              label="Show confidence"
            />
            <Button
              appearance="primary"
              icon={<PlayRegular />}
              onClick={handleRun}
              disabled={running || (!selected && !uploadFile)}
            >
              {running ? "Running…" : "Run"}
            </Button>
            <Button
              icon={<SaveRegular />}
              onClick={handleSaveGt}
              disabled={!result || savingGt || !!uploadFile}
              title={uploadFile ? "Disabled for uploaded files" : "Write current line items to demo/sec/reference/expected-output/<stem>.json"}
            >
              {savingGt ? "Saving…" : "Save result"}
            </Button>
            <Button
              icon={<CheckmarkCircleRegular />}
              onClick={handleValidate}
              disabled={!result || validating || !!uploadFile}
              title={uploadFile ? "Disabled for uploaded files" : undefined}
            >
              {validating ? "Validating…" : "Validate"}
            </Button>
          </span>
        </div>

        <Dialog
          open={runDialogOpen}
          onOpenChange={(_, d) => {
            // Block dismissal while the run is in flight.
            if (running && d.open === false) return;
            setRunDialogOpen(!!d.open);
          }}
        >
          <DialogSurface style={{ width: "min(720px, 92vw)", maxWidth: "92vw" }}>
            <DialogBody>
              <DialogTitle>
                {running ? "Running extraction\u2026" : error ? "Extraction failed" : "Extraction complete"}
              </DialogTitle>
              <DialogContent>
                <Caption1 style={{ display: "block", marginBottom: 8, color: "var(--colorNeutralForeground3)" }}>
                  {headerName} · pipeline: classify → analyze
                </Caption1>
                <RunProgress events={events} running={running} error={error} />
              </DialogContent>
              <DialogActions>
                <Button
                  appearance="primary"
                  disabled={running}
                  onClick={() => setRunDialogOpen(false)}
                >
                  Close
                </Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>

        {/* Split body: output | splitter | reference */}
        <div
          ref={mainBodyRef}
          className={styles.mainBody}
          style={{
            gridTemplateColumns: `${splitPct}% 6px 1fr`,
          }}
        >
          {/* Left: output */}
          <div className={styles.leftPane}>
            <div className={styles.paneHeader}>
              <Body1Strong>Output</Body1Strong>
              <Caption1>Extracted statements from this run</Caption1>
            </div>
            <TabList
              selectedValue={outTab}
              onTabSelect={(_, d) => setOutTab(d.value as OutputTab)}
              size="small"
            >
              <Tab value="statements" icon={<DocumentDataRegular />}>Statements</Tab>
              <Tab value="raw">Raw JSON</Tab>
              <Tab value="validation" disabled={!result}>Validation</Tab>
            </TabList>
            <div className={styles.paneContent}>
              {!result && (
                <Caption1>
                  Run an extraction to see the parsed financial statements,
                  the raw CU payload, and a validation report.
                </Caption1>
              )}
              {result && outTab === "statements" && (
                <StatementTabs
                  statements={result.statements}
                  showConfidence={showConfidence}
                  onSelectStatement={handleSelectStatement}
                />
              )}
              {result && outTab === "raw" && (
                <RawJsonPanel
                  data={result.raw ?? result}
                  filenameStem={`${fileStem}__raw`}
                />
              )}
              {result && outTab === "validation" && (
                <ValidationPanel validation={validation} />
              )}
            </div>
          </div>

          {/* Splitter */}
          <div className={styles.splitter} onMouseDown={onSplitterMouseDown} />

          {/* Right: reference */}
          <div className={styles.rightPane}>
            <div className={styles.paneHeader}>
              <Body1Strong>Reference</Body1Strong>
              <Caption1>Source PDF and downloadable artifacts</Caption1>
            </div>
            <TabList
              selectedValue={refTab}
              onTabSelect={(_, d) => setRefTab(d.value as RefTab)}
              size="small"
            >
              <Tab value="preview" icon={<DocumentPdfRegular />}>PDF preview</Tab>
              <Tab value="artifacts" disabled={!excelUrl}>Artifacts</Tab>
            </TabList>
            <div className={styles.paneContent}>
              {refTab === "preview" && pdfUrl && (
                <div style={{ height: "100%", minHeight: 520 }}>
                  <SourcePdfViewer url={pdfUrl} initialPage={pdfPage} />
                </div>
              )}
              {refTab === "preview" && !pdfUrl && (
                <Caption1>Pick a sample or upload a PDF to preview the source.</Caption1>
              )}
              {refTab === "artifacts" && excelUrl && (
                <div>
                  <div className={styles.artifactRow}>
                    <DocumentDataRegular style={{ color: "#107C41", fontSize: 20 }} />
                    <div style={{ flex: 1 }}>
                      <Text weight="semibold">{fileStem}.xlsx</Text>
                      <div>
                        <Caption1>Multi-sheet workbook with hierarchical formatting</Caption1>
                      </div>
                    </div>
                    <Button
                      size="small"
                      as="a"
                      {...({
                        href: excelUrl,
                        target: "_blank",
                        rel: "noopener noreferrer",
                      } as any)}
                    >
                      Download
                    </Button>
                  </div>
                  {result?.meta?.run_id && (
                    <Caption1
                      style={{ color: tokens.colorNeutralForeground3, marginTop: 8, display: "block" }}
                    >
                      run_id: <code>{result.meta.run_id}</code>
                    </Caption1>
                  )}
                </div>
              )}
              {refTab === "artifacts" && !excelUrl && (
                <Caption1>No artifacts yet — run an extraction first.</Caption1>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
