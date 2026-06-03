import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Badge,
  Body1Strong,
  Button,
  Caption1,
  Divider,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Switch,
  Tab,
  TabList,
  Text,
  Title3,
  tokens,
} from "@fluentui/react-components";
import {
  PlayRegular,
  CloudArrowUpRegular,
  BookRegular,
  ArrowUploadRegular,
  DismissRegular,
  DocumentRegular,
} from "@fluentui/react-icons";
import { toast } from "react-toastify";

import {
  analyzeSample,
  analyzeUpload,
  deployAnalyzers,
  getHealth,
  listSamples,
  ProClaimsResult,
  ProFraudResult,
  ProHealthcheck,
  ProSampleManifest,
  Scenario,
} from "../services/proService";
import SampleSelector from "../Components/Pro/SampleSelector";
import ClaimsResultView from "../Components/Pro/ClaimsResultView";
import FraudResultView from "../Components/Pro/FraudResultView";
import ProReferencePane from "../Components/Pro/ProReferencePane";

const ProPage: React.FC = () => {
  const [scenario, setScenario] = useState<Scenario>("claims");
  const [samples, setSamples] = useState<ProSampleManifest[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [claimsResult, setClaimsResult] = useState<ProClaimsResult | null>(null);
  const [fraudResult, setFraudResult] = useState<ProFraudResult | null>(null);
  const [health, setHealth] = useState<ProHealthcheck | null>(null);

  // ── User-uploaded files (alternative to picking a bundled sample) ──
  // Pro mode is multi-input: claims accept FNOL + police report + estimate
  // + photo together. We mirror that by allowing multi-file upload.
  const [uploadMode, setUploadMode] = useState(false);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const addUploadFiles = (incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    if (!arr.length) return;
    setUploadFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      const next = [...prev];
      for (const f of arr) {
        const key = `${f.name}:${f.size}`;
        if (!seen.has(key)) {
          next.push(f);
          seen.add(key);
        }
      }
      return next;
    });
  };
  const removeUploadFile = (i: number) =>
    setUploadFiles((prev) => prev.filter((_, idx) => idx !== i));
  const clearUploadFiles = () => setUploadFiles([]);


  useEffect(() => {
    listSamples()
      .then(setSamples)
      .catch((e) => toast.error(`Failed to load samples: ${e.message}`));
    getHealth().then(setHealth).catch(() => undefined);
  }, []);

  // Auto-pick a default sample matching the scenario
  useEffect(() => {
    if (selectedId) {
      const cur = samples.find((s) => s.id === selectedId);
      if (cur && cur.scenario === scenario) return;
    }
    const first = samples.find((s) => s.scenario === scenario);
    setSelectedId(first ? first.id : null);
  }, [scenario, samples, selectedId]);

  const onRun = async () => {
    if (uploadMode) {
      if (uploadFiles.length === 0) {
        toast.warn("Drop in at least one file first.");
        return;
      }
      setRunning(true);
      try {
        const r = await analyzeUpload(uploadFiles, scenario);
        if (scenario === "claims") {
          setClaimsResult(r as ProClaimsResult);
        } else {
          setFraudResult(r as ProFraudResult);
        }
        toast.success("Analysis complete.");
      } catch (e: any) {
        toast.error(`Analyze failed: ${e?.response?.data?.detail ?? e.message}`);
      } finally {
        setRunning(false);
      }
      return;
    }
    if (!selectedId) {
      toast.warn("Pick a sample first.");
      return;
    }
    setRunning(true);
    try {
      const r = await analyzeSample(selectedId, scenario);
      if (scenario === "claims") {
        setClaimsResult(r as ProClaimsResult);
      } else {
        setFraudResult(r as ProFraudResult);
      }
      toast.success("Analysis complete.");
    } catch (e: any) {
      toast.error(`Analyze failed: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setRunning(false);
    }
  };

  const onDeploy = async () => {
    setDeploying(true);
    try {
      const r = await deployAnalyzers(false);
      toast.success(`Deploy OK: ${JSON.stringify(r)}`);
      const h = await getHealth();
      setHealth(h);
    } catch (e: any) {
      toast.error(`Deploy failed: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setDeploying(false);
    }
  };

  const selected = samples.find((s) => s.id === selectedId) || null;
  const analyzersDeployed = useMemo(() => {
    const a = health?.analyzers ?? {};
    return Object.values(a).every(Boolean) && Object.keys(a).length > 0;
  }, [health]);

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "360px 1fr",
      columnGap: 16,
      padding: 16,
      height: "calc(100vh - 64px)",
      boxSizing: "border-box",
    }}>
      {/* Left rail */}
      <div style={{ display: "flex", flexDirection: "column", rowGap: 12, overflowY: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Title3>Pro Mode</Title3>
          <Badge appearance="filled" color="warning" size="small">PREVIEW</Badge>
        </div>
        <Caption1>
          Azure Content Understanding <b>pro mode</b> — preview API <code>2025-05-01-preview</code>.
          Multi-input, multi-step reasoning, with the auto policy deployed as reference data.
        </Caption1>

        <TabList
          selectedValue={scenario}
          onTabSelect={(_, d) => setScenario(d.value as Scenario)}
          size="small"
        >
          <Tab value="claims">Claims</Tab>
          <Tab value="fraud">Fraud Detection</Tab>
        </TabList>

        <Switch
          checked={uploadMode}
          onChange={(_, d) => {
            const on = !!d.checked;
            setUploadMode(on);
            if (on) {
              setClaimsResult(null);
              setFraudResult(null);
            } else {
              clearUploadFiles();
            }
          }}
          label="Use my own files"
        />

        {!uploadMode && (
          <SampleSelector
            samples={samples}
            selectedId={selectedId}
            onSelect={setSelectedId}
            filterScenario={scenario}
          />
        )}

        {uploadMode && (
          <>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 4,
                padding: "14px 10px",
                border: `1.5px dashed ${isDragging ? tokens.colorBrandStroke1 : tokens.colorNeutralStroke2}`,
                borderRadius: 6,
                backgroundColor: isDragging ? tokens.colorBrandBackground2 : tokens.colorNeutralBackground2,
                cursor: "pointer",
                textAlign: "center",
                transition: "all 150ms",
              }}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files?.length) addUploadFiles(e.dataTransfer.files);
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
              <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
                PDF · PNG · JPG · TIFF (multi-file)
              </Caption1>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff"
              multiple
              style={{ display: "none" }}
              onChange={(e) => {
                if (e.target.files?.length) addUploadFiles(e.target.files);
                e.target.value = "";
              }}
            />
            {uploadFiles.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {uploadFiles.map((f, i) => (
                  <div
                    key={`${f.name}:${i}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "6px 8px",
                      border: `1px solid ${tokens.colorNeutralStroke2}`,
                      borderRadius: 4,
                      backgroundColor: tokens.colorNeutralBackground1,
                    }}
                  >
                    <DocumentRegular style={{ flexShrink: 0, color: tokens.colorBrandForeground1 }} />
                    <Text
                      size={200}
                      weight="semibold"
                      style={{
                        flex: "1 1 auto",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {f.name}
                    </Text>
                    <Caption1 style={{ color: tokens.colorNeutralForeground3, flexShrink: 0 }}>
                      {(f.size / 1024).toFixed(0)} KB
                    </Caption1>
                    <Button
                      appearance="subtle"
                      size="small"
                      icon={<DismissRegular />}
                      style={{ padding: 2, minWidth: 0, flexShrink: 0 }}
                      onClick={(e) => { e.stopPropagation(); removeUploadFile(i); }}
                      aria-label={`Remove ${f.name}`}
                    />
                  </div>
                ))}
                <Button size="small" appearance="subtle" onClick={clearUploadFiles}>
                  Clear all
                </Button>
              </div>
            )}
            <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
              For <b>claims</b> upload the FNOL, police report, repair estimate
              and damage photo together. For <b>fraud</b> include the same
              bundle — the rule engine compares them.
            </Caption1>
          </>
        )}

        <Divider />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button
            appearance="primary"
            icon={running ? <Spinner size="tiny" /> : <PlayRegular />}
            disabled={
              running ||
              (uploadMode ? uploadFiles.length === 0 : !selectedId)
            }
            onClick={onRun}
          >
            {running ? "Analyzing…" : `Analyze ${scenario}`}
          </Button>
          <Button
            appearance="secondary"
            icon={deploying ? <Spinner size="tiny" /> : <CloudArrowUpRegular />}
            disabled={deploying}
            onClick={onDeploy}
          >
            {deploying ? "Deploying…" : "Deploy analyzers"}
          </Button>
        </div>

        {health && (
          <Caption1>
            Endpoint: {health.endpoint_configured ? "OK" : "missing"} ·
            Analyzers: {Object.entries(health.analyzers).map(([k, v]) => `${k}:${v ? "✓" : "✗"}`).join(" ")}
            {health.error ? ` · ${health.error}` : ""}
          </Caption1>
        )}

        {!analyzersDeployed && health && (
          <MessageBar intent="info">
            <MessageBarBody>
              <MessageBarTitle>Deploy required</MessageBarTitle>
              Click <b>Deploy analyzers</b> once to register the pro-mode analyzers and bake the reference policy.
            </MessageBarBody>
          </MessageBar>
        )}
      </div>

      {/* Main panel: Output (left) | Reference (right) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)",
          columnGap: 12,
          overflow: "hidden",
        }}
      >
        {/* Output column */}
        <div style={{ overflowY: "auto", padding: "0 8px 0 4px", borderRight: "1px solid var(--colorNeutralStroke2)" }}>
          {!uploadMode && selected && (
            <div style={{ marginBottom: 12 }}>
              <Body1Strong>{selected.title}</Body1Strong>
              <Caption1 style={{ display: "block" }}>
                <Badge appearance="tint" color={selected.scenario === "fraud" ? "danger" : "success"} style={{ marginRight: 6 }}>
                  {selected.scenario}
                </Badge>
                {selected.description}
              </Caption1>
            </div>
          )}
          {uploadMode && uploadFiles.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Body1Strong>Uploaded bundle ({uploadFiles.length} file{uploadFiles.length === 1 ? "" : "s"})</Body1Strong>
              <Caption1 style={{ display: "block" }}>
                <Badge appearance="tint" color={scenario === "fraud" ? "danger" : "success"} style={{ marginRight: 6 }}>
                  {scenario}
                </Badge>
                {uploadFiles.map((f) => f.name).join(" · ")}
              </Caption1>
            </div>
          )}

          {scenario === "claims" && (claimsResult
            ? <ClaimsResultView result={claimsResult} />
            : <EmptyState scenario="claims" />)}

          {scenario === "fraud" && (fraudResult
            ? <FraudResultView result={fraudResult} />
            : <EmptyState scenario="fraud" />)}
        </div>

        {/* Reference column */}
        <div style={{ overflow: "hidden", paddingLeft: 8, display: "flex", flexDirection: "column" }}>
          <div style={{ paddingBottom: 4, borderBottom: "1px solid var(--colorNeutralStroke2)", marginBottom: 6 }}>
            <Body1Strong>Reference</Body1Strong>
            <Caption1 style={{ display: "block" }}>
              {uploadMode
                ? "Uploaded source files and the raw CU response for this run."
                : "Source documents and the raw CU response for this run."}
            </Caption1>
          </div>
          <div style={{ flex: 1, overflow: "hidden" }}>
            {uploadMode ? (
              <UploadedReferencePane
                files={uploadFiles}
                rawResponse={
                  scenario === "claims"
                    ? (claimsResult?.raw ?? null)
                    : (fraudResult?.raw ?? null)
                }
              />
            ) : (
              <ProReferencePane
                sample={selected}
                rawResponse={
                  scenario === "claims"
                    ? (claimsResult?.raw ?? null)
                    : (fraudResult?.raw ?? null)
                }
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const EmptyState: React.FC<{ scenario: Scenario }> = ({ scenario }) => (
  <div style={{ padding: 24, opacity: 0.7 }}>
    <BookRegular fontSize={28} />
    <Body1Strong style={{ display: "block", marginTop: 8 }}>
      {scenario === "claims" ? "Claims processing demo" : "Fraud detection demo"}
    </Body1Strong>
    <Caption1 style={{ display: "block", marginTop: 6 }}>
      {scenario === "claims"
        ? "Pick a sample and click Analyze claims to see the pro-mode analyzer reason across all four claim documents (FNOL, police report, repair estimate, damage photo) against the reference policy."
        : "Pick the fraud-seeded sample and click Analyze fraud to see CU reasoning signals blended with the local rule engine. A 0–100 risk score combines both."}
    </Caption1>
  </div>
);

/**
 * Minimal reference pane used when the user uploaded their own files.
 * Renders a previewable list of the uploaded files (object URLs) plus a
 * raw-CU-response tab, mirroring the layout of `ProReferencePane` without
 * requiring a server-side sample manifest.
 */
const UploadedReferencePane: React.FC<{
  files: File[];
  rawResponse: Record<string, unknown> | null;
}> = ({ files, rawResponse }) => {
  const [tab, setTab] = useState<"preview" | "raw">("preview");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [objectUrls, setObjectUrls] = useState<string[]>([]);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setObjectUrls(urls);
    setSelectedIdx(0);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  const active = files[selectedIdx];
  const activeUrl = objectUrls[selectedIdx];
  const isImage = active && /\.(png|jpe?g|tiff?|bmp|gif)$/i.test(active.name);
  const isPdf = active && /\.pdf$/i.test(active.name);

  if (!files.length) {
    return (
      <div style={{ padding: 16, opacity: 0.7 }}>
        <Caption1>Upload one or more files to preview them here.</Caption1>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <TabList
        selectedValue={tab}
        onTabSelect={(_, d) => setTab(d.value as "preview" | "raw")}
        size="small"
      >
        <Tab value="preview">Files ({files.length})</Tab>
        <Tab value="raw" disabled={!rawResponse}>Raw response</Tab>
      </TabList>
      <div style={{ flex: 1, overflow: "auto", paddingTop: 8 }}>
        {tab === "preview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {files.map((f, i) => (
                <Button
                  key={`${f.name}:${i}`}
                  size="small"
                  appearance={i === selectedIdx ? "primary" : "secondary"}
                  onClick={() => setSelectedIdx(i)}
                >
                  {f.name}
                </Button>
              ))}
            </div>
            <div
              style={{
                border: "1px solid var(--colorNeutralStroke2)",
                borderRadius: 4,
                padding: 8,
                background: "#fafafa",
                minHeight: 320,
              }}
            >
              {isImage && (
                <img
                  src={activeUrl}
                  alt={active.name}
                  style={{ maxWidth: "100%", height: "auto", display: "block" }}
                />
              )}
              {isPdf && (
                <iframe
                  src={activeUrl}
                  title={active.name}
                  style={{ width: "100%", height: 600, border: 0 }}
                />
              )}
              {!isImage && !isPdf && (
                <Caption1>
                  No inline preview for <code>{active.name}</code>.
                </Caption1>
              )}
            </div>
          </div>
        )}
        {tab === "raw" && rawResponse && (
          <pre
            style={{
              fontFamily: "Consolas, monospace",
              fontSize: 12,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              margin: 0,
            }}
          >
            {JSON.stringify(rawResponse, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
};

export default ProPage;
