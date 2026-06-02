import React, { useEffect, useMemo, useState } from "react";
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
  Tab,
  TabList,
  Title3,
} from "@fluentui/react-components";
import { PlayRegular, CloudArrowUpRegular, BookRegular } from "@fluentui/react-icons";
import { toast } from "react-toastify";

import {
  analyzeSample,
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
        <Title3>Pro Mode</Title3>
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

        <SampleSelector
          samples={samples}
          selectedId={selectedId}
          onSelect={setSelectedId}
          filterScenario={scenario}
        />

        <Divider />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button
            appearance="primary"
            icon={running ? <Spinner size="tiny" /> : <PlayRegular />}
            disabled={running || !selectedId}
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
          {selected && (
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
              Source documents and the raw CU response for this run.
            </Caption1>
          </div>
          <div style={{ flex: 1, overflow: "hidden" }}>
            <ProReferencePane
              sample={selected}
              rawResponse={
                scenario === "claims"
                  ? (claimsResult?.raw ?? null)
                  : (fraudResult?.raw ?? null)
              }
            />
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

export default ProPage;
