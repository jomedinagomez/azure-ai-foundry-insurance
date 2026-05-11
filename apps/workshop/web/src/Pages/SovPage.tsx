import React, { useEffect, useMemo, useState } from "react";
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
  Spinner,
  Tab,
  TabList,
  Text,
  Textarea,
  Tooltip,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import {
  CheckmarkCircleFilled,
  DismissCircleFilled,
  PlayRegular,
  ArrowSyncRegular,
  DocumentTableRegular,
  DocumentPdfRegular,
  DocumentRegular,
} from "@fluentui/react-icons";

import {
  fetchAnalyzers,
  fetchAnalyzerTemplate,
  fetchCachedExtraction,
  fetchSovSamples,
  pushAnalyzerToFoundry,
  runPipelineExtraction,
  runValidation,
  saveAnalyzerTemplate,
  saveResultToCache,
  Pattern,
  SovAnalyzer,
  SovExtractionResult,
  SovSample,
  SovValidationResult,
  SovValidationDiff,
} from "../services/sovService";
import {
  fetchPipelines,
  Pipeline,
} from "../services/pipelinesService";
import AnalyzerEditor from "../Components/Sov/AnalyzerEditor";

function FileTypeIcon({ type }: { type: string }) {
  if (type === "xlsx") return <DocumentTableRegular style={{ color: "#107C41" }} />;
  if (type === "pdf") return <DocumentPdfRegular style={{ color: "#B00020" }} />;
  return <DocumentRegular />;
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
  headerStrip: {
    display: "flex",
    alignItems: "center",
    columnGap: "12px",
    flexWrap: "wrap",
  },
  patternBadgeA: { backgroundColor: "#0F6CBD", color: "#fff" },
  patternBadgeB: { backgroundColor: "#107C10", color: "#fff" },
  patternBadgeC: { backgroundColor: "#7B2FAE", color: "#fff" },
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
});

const PATTERN_DESC: Record<Pattern, string> = {
  A: "Pattern A — PDF + method=extract (OCR grounding + confidence)",
  B: "Pattern B — xlsx + method=generate (LLM, no grounding)",
  C: "Pattern C — xlsx + per-image fan-out, merged client-side",
};

function PatternBadge({ pattern }: { pattern: Pattern }) {
  const styles = useStyles();
  const cls =
    pattern === "A" ? styles.patternBadgeA :
    pattern === "B" ? styles.patternBadgeB :
                       styles.patternBadgeC;
  return (
    <Tooltip content={PATTERN_DESC[pattern]} relationship="description">
      <span className={cls} style={{ padding: "2px 10px", borderRadius: 12, fontSize: 12, fontWeight: 700 }}>
        {`Pattern ${pattern}`}
      </span>
    </Tooltip>
  );
}

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

  // Pipeline picker for next Run (null = use extension default on server)
  const [runPipelineId, setRunPipelineId] = useState<string | null>(null);

  // Pipeline catalog (read-only on this page; full editing lives on /pipelines)
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);

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

  const onRun = async () => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const r = await runPipelineExtraction(selected, runPipelineId);
      setResult(r);
      setValidation(null);
    } catch (e: any) {
      setError(`Extraction failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
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
              <Caption1>use the default pipeline for the sample's extension</Caption1>
            </div>
          </Option>
          {pipelines.map((p) => (
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
          <Text size={500} weight="semibold">{selected ?? "Pick a sample"}</Text>
          {result && <PatternBadge pattern={result.meta.pattern} />}
          {result && (
            <span className={styles.metaPill}>analyzer: {result.meta.analyzer_id}</span>
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
                  <Caption1>default pipeline for sample's extension</Caption1>
                </div>
              </Option>
              {pipelines.map((p) => (
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
              disabled={!selected || loading}
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

          {result && tab === "account" && <AccountTab result={result} showConfidence={showConfidence} />}
          {result && tab === "locations" && <LocationsTab result={result} showConfidence={showConfidence} />}
          {result && tab === "raw" && (
            <pre className={styles.json}>{JSON.stringify(result.raw, null, 2)}</pre>
          )}
          {validation && tab === "validation" && <ValidationTab validation={validation} result={result} />}
        </div>
      </div>
    </div>
  );
}

function AccountTab({ result, showConfidence }: { result: SovExtractionResult; showConfidence: boolean }) {
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
          return (
            <tr key={key}>
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

function LocationsTab({ result, showConfidence }: { result: SovExtractionResult; showConfidence: boolean }) {
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
            <tr key={i}>
              {LOCATION_COLS.map((col) => {
                const c = conf[col.key as string];
                return (
                  <td key={String(col.key)} className={styles.td}>
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
