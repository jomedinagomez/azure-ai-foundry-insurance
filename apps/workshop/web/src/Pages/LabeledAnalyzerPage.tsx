import React, { useEffect, useRef, useState } from "react";
import {
  Badge,
  Body1,
  Body1Strong,
  Button,
  Caption1,
  Dropdown,
  Option,
  Spinner,
  Switch,
  Tab,
  TabList,
  Text,
  Title3,
  Tooltip,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { DismissRegular, PlayRegular } from "@fluentui/react-icons";

import SourcePdfViewer from "../Components/Sec/SourcePdfViewer";
import {
  FieldScore,
  LabeledAnalyzerSample,
  LabeledAnalyzerStatus,
  LabeledEvaluationReport,
  LabeledStepEvent,
  fetchLabeledAnalyzerSamples,
  fetchLabeledAnalyzerStatus,
  fetchLabeledEvaluationReport,
  labeledAnalyzerSampleUrl,
  runLabeledEvaluationStream,
} from "../services/labeledAnalyzerService";

type ResultTab = "comparison" | "thresholds" | "raw";

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    height: "calc(100vh - 56px)",
    minWidth: "1180px",
    boxSizing: "border-box",
    overflow: "hidden",
  },
  toolbar: {
    display: "flex",
    alignItems: "center",
    columnGap: "12px",
    minHeight: "58px",
    padding: "8px 16px",
    boxSizing: "border-box",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  toolbarTitle: {
    display: "flex",
    flexDirection: "column",
    minWidth: "230px",
  },
  spacer: { flex: 1 },
  metrics: {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(180px, 1fr))",
    minHeight: "82px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  metric: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    rowGap: "3px",
    padding: "10px 18px",
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  metricValue: {
    fontSize: "24px",
    lineHeight: "28px",
    fontWeight: 600,
  },
  workspace: {
    flex: 1,
    display: "grid",
    gridTemplateColumns: "minmax(470px, 0.9fr) minmax(650px, 1.35fr)",
    minHeight: 0,
    overflow: "hidden",
  },
  source: {
    minWidth: 0,
    minHeight: 0,
    padding: "12px",
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    overflow: "hidden",
  },
  results: {
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
    minHeight: 0,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  resultHeader: {
    display: "flex",
    alignItems: "center",
    padding: "8px 12px 0",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  resultBody: {
    flex: 1,
    minHeight: 0,
    overflow: "auto",
    padding: "10px 12px 16px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    tableLayout: "fixed",
    fontSize: "12px",
    "& th": {
      position: "sticky",
      top: 0,
      zIndex: 1,
      padding: "8px",
      textAlign: "left",
      backgroundColor: tokens.colorNeutralBackground3,
      borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    },
    "& td": {
      verticalAlign: "top",
      padding: "8px",
      borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
      overflowWrap: "anywhere",
    },
  },
  fieldColumn: { width: "22%" },
  truthColumn: { width: "26%" },
  resultColumn: { width: "26%" },
  valueCell: {
    display: "flex",
    flexDirection: "column",
    rowGap: "4px",
  },
  correct: {
    boxShadow: `inset 3px 0 0 ${tokens.colorPaletteGreenBorderActive}`,
    backgroundColor: tokens.colorPaletteGreenBackground1,
  },
  incorrect: {
    boxShadow: `inset 3px 0 0 ${tokens.colorPaletteRedBorderActive}`,
    backgroundColor: tokens.colorPaletteRedBackground1,
  },
  cellMeta: {
    display: "flex",
    alignItems: "center",
    columnGap: "6px",
    minHeight: "22px",
  },
  empty: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    rowGap: "8px",
    textAlign: "center",
    color: tokens.colorNeutralForeground3,
    ...shorthands.padding("24px"),
  },
  error: {
    padding: "8px 12px",
    color: tokens.colorPaletteRedForeground1,
    backgroundColor: tokens.colorPaletteRedBackground1,
    borderBottom: `1px solid ${tokens.colorPaletteRedBorder1}`,
  },
  progress: {
    display: "flex",
    alignItems: "center",
    columnGap: "8px",
    minWidth: "210px",
  },
  raw: {
    margin: 0,
    fontFamily: "Cascadia Code, Consolas, monospace",
    fontSize: "11px",
    lineHeight: "16px",
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
  },
});

const percent = (value: number | null | undefined) =>
  value == null ? "--" : `${(value * 100).toFixed(1)}%`;

const displayValue = (value: unknown) => {
  if (value == null || value === "") return "Missing";
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
};

const fieldLabel = (value: string) => value.replace(/([a-z])([A-Z])/g, "$1 $2");

const sourcePage = (source?: string | null) => {
  const match = source?.match(/^D\((\d+)/);
  return match ? Number(match[1]) : null;
};

const LabeledAnalyzerPage: React.FC = () => {
  const styles = useStyles();
  const [status, setStatus] = useState<LabeledAnalyzerStatus | null>(null);
  const [samples, setSamples] = useState<LabeledAnalyzerSample[]>([]);
  const [selected, setSelected] = useState("");
  const [report, setReport] = useState<LabeledEvaluationReport | null>(null);
  const [activeTab, setActiveTab] = useState<ResultTab>("comparison");
  const [live, setLive] = useState(false);
  const [repeats, setRepeats] = useState(1);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState("Ready");
  const [error, setError] = useState<string | null>(null);
  const [initialPage, setInitialPage] = useState(1);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchLabeledAnalyzerStatus(), fetchLabeledAnalyzerSamples()])
      .then(async ([nextStatus, nextSamples]) => {
        const nextReport = nextStatus.cached_report
          ? await fetchLabeledEvaluationReport()
          : null;
        if (!active) return;
        setStatus(nextStatus);
        setSamples(nextSamples);
        setSelected(nextSamples[0]?.file_name || "");
        setReport(nextReport);
        if (nextReport) setRepeats(nextReport.repeats);
      })
      .catch((reason) => active && setError(String(reason)));
    return () => {
      active = false;
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => setInitialPage(1), [selected]);

  const runEvaluation = async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    setError(null);
    setProgress(live ? "Starting live evaluation" : "Loading cached report");
    try {
      await runLabeledEvaluationStream(
        { forceLive: live, repeats, signal: controller.signal },
        {
          onStep: (event) => setProgress(progressLabel(event)),
          onComplete: (nextReport) => {
            setReport(nextReport);
            setProgress("Evaluation complete");
          },
          onError: (message) => setError(message),
        }
      );
    } catch (reason) {
      if (!controller.signal.aborted) setError(String(reason));
    } finally {
      setRunning(false);
    }
  };

  const selectedSample = samples.find((sample) => sample.file_name === selected);
  const zeroDocument = report?.variants.zero_shot.documents[selected];
  const labeledDocument = report?.variants.labeled.documents[selected];
  const zeroRun = zeroDocument?.runs[0];
  const labeledRun = labeledDocument?.runs[0];
  const summary = report?.summary;
  const delta = summary?.accuracy_delta_points;

  return (
    <div className={styles.root}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarTitle}>
          <Title3>Labeled Analyzer A/B</Title3>
          <Caption1>Same schema and GPT-5.2 model; labeled samples are the only variable.</Caption1>
        </div>
        <Dropdown
          aria-label="Held-out sample"
          value={selectedSample?.file_name || "Select sample"}
          selectedOptions={selected ? [selected] : []}
          onOptionSelect={(_, data) => setSelected(String(data.optionValue || ""))}
        >
          {samples.map((sample) => (
            <Option
              key={sample.file_name}
              value={sample.file_name}
              text={`${sample.file_name}${sample.challenge === "handwritten" ? " · handwritten" : ""}`}
            >
              {sample.file_name}{sample.challenge === "handwritten" ? " · handwritten" : ""}
            </Option>
          ))}
        </Dropdown>
        <Dropdown
          aria-label="Evaluation repeats"
          value={`${repeats} run${repeats === 1 ? "" : "s"}`}
          selectedOptions={[String(repeats)]}
          onOptionSelect={(_, data) => setRepeats(Number(data.optionValue || 1))}
        >
          {[1, 2, 3].map((count) => (
            <Option
              key={count}
              value={String(count)}
              text={`${count} run${count === 1 ? "" : "s"}`}
            >
              {count} run{count === 1 ? "" : "s"}
            </Option>
          ))}
        </Dropdown>
        <Switch
          checked={live}
          onChange={(_, data) => setLive(data.checked)}
          label="Live Azure run"
        />
        <Button
          appearance="primary"
          icon={<PlayRegular />}
          disabled={running || (!live && !status?.cached_report)}
          onClick={runEvaluation}
        >
          Run evaluation
        </Button>
        {running && (
          <Button
            appearance="subtle"
            icon={<DismissRegular />}
            onClick={() => abortRef.current?.abort()}
          >
            Cancel
          </Button>
        )}
        <div className={styles.spacer} />
        <div className={styles.progress}>
          {running && <Spinner size="tiny" />}
          <Caption1>{progress}</Caption1>
        </div>
        <Badge appearance="outline" color={status?.labeled_data.ready ? "success" : "warning"}>
          {status?.labeled_data.ready ? "Labels ready" : "Label setup pending"}
        </Badge>
        <Badge appearance="outline" color={status?.cached_report ? "success" : "informative"}>
          {status?.cached_report ? "Cached evidence" : "No cached evidence"}
        </Badge>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.metrics}>
        <Metric label="Zero-shot grouped accuracy" value={percent(summary?.zero_shot_accuracy)} detail="GPT-5.2 · unique claims equally weighted" />
        <Metric label="Labeled grouped accuracy" value={percent(summary?.labeled_accuracy)} detail="GPT-5.2 · unique claims equally weighted" />
        <Metric
          label="Accuracy delta"
          value={delta == null ? "--" : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pp`}
          detail={delta == null ? "Awaiting evaluation" : delta > 0 ? "Measured improvement" : "No measured improvement"}
        />
        <Metric
          label="False accepts at 0.90"
          value={summary ? `${summary.zero_shot_false_accepts_at_090} → ${summary.labeled_false_accepts_at_090}` : "--"}
          detail="Confident fields that were incorrect"
        />
      </div>

      <div className={styles.workspace}>
        <div className={styles.source}>
          {selected ? (
            <SourcePdfViewer
              url={labeledAnalyzerSampleUrl(selected)}
              initialPage={initialPage}
            />
          ) : (
            <div className={styles.empty}><Spinner label="Loading samples" /></div>
          )}
        </div>
        <div className={styles.results}>
          <div className={styles.resultHeader}>
            <TabList
              selectedValue={activeTab}
              onTabSelect={(_, data) => setActiveTab(String(data.value) as ResultTab)}
              size="small"
            >
              <Tab value="comparison">Field comparison</Tab>
              <Tab value="thresholds">Threshold performance</Tab>
              <Tab value="raw">Raw evidence</Tab>
            </TabList>
            <div className={styles.spacer} />
            {selectedSample?.challenge === "handwritten" && (
              <Badge color="warning" appearance="filled">Handwritten challenge slice</Badge>
            )}
          </div>
          <div className={styles.resultBody}>
            {!report || !zeroRun || !labeledRun ? (
              <div className={styles.empty}>
                <Body1Strong>No evaluation evidence available</Body1Strong>
                <Body1>Complete the labeled-data notebooks, or enable Live Azure run after both analyzers are built.</Body1>
              </div>
            ) : activeTab === "comparison" ? (
              <ComparisonTable
                zeroFields={zeroRun.score.fields}
                labeledFields={labeledRun.score.fields}
                onPage={setInitialPage}
                styles={styles}
              />
            ) : activeTab === "thresholds" ? (
              <ThresholdTable report={report} styles={styles} />
            ) : (
              <pre className={styles.raw}>{JSON.stringify({ zero_shot: zeroRun, labeled: labeledRun }, null, 2)}</pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const Metric: React.FC<{ label: string; value: string; detail: string }> = ({ label, value, detail }) => {
  const styles = useStyles();
  return (
    <div className={styles.metric}>
      <Caption1>{label}</Caption1>
      <div className={styles.metricValue}>{value}</div>
      <Caption1>{detail}</Caption1>
    </div>
  );
};

const ComparisonTable: React.FC<{
  zeroFields: FieldScore[];
  labeledFields: FieldScore[];
  onPage: (page: number) => void;
  styles: ReturnType<typeof useStyles>;
}> = ({ zeroFields, labeledFields, onPage, styles }) => {
  const labeledByName = new Map(labeledFields.map((field) => [field.field_name, field]));
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={styles.fieldColumn}>Field</th>
          <th className={styles.truthColumn}>Ground truth</th>
          <th className={styles.resultColumn}>Zero-shot · GPT-5.2</th>
          <th className={styles.resultColumn}>Labeled · GPT-5.2</th>
        </tr>
      </thead>
      <tbody>
        {zeroFields.map((zeroField) => {
          const labeledField = labeledByName.get(zeroField.field_name);
          return (
            <tr key={zeroField.field_name}>
              <td><Body1Strong>{fieldLabel(zeroField.field_name)}</Body1Strong></td>
              <td>{displayValue(zeroField.expected)}</td>
              <ResultCell field={zeroField} onPage={onPage} styles={styles} />
              {labeledField && <ResultCell field={labeledField} onPage={onPage} styles={styles} />}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};

const ResultCell: React.FC<{
  field: FieldScore;
  onPage: (page: number) => void;
  styles: ReturnType<typeof useStyles>;
}> = ({ field, onPage, styles }) => {
  const page = sourcePage(field.source);
  return (
    <td className={field.correct ? styles.correct : styles.incorrect}>
      <div className={styles.valueCell}>
        <Text>{displayValue(field.actual)}</Text>
        <div className={styles.cellMeta}>
          <Badge size="small" appearance="outline" color={field.correct ? "success" : "danger"}>
            {field.correct ? "Correct" : "Incorrect"}
          </Badge>
          <Caption1>{field.confidence == null ? "No confidence" : `${(field.confidence * 100).toFixed(1)}%`}</Caption1>
          {page && (
            <Tooltip content={field.source || "Grounded source"} relationship="description">
              <Button appearance="subtle" size="small" onClick={() => onPage(page)}>p.{page}</Button>
            </Tooltip>
          )}
        </div>
      </div>
    </td>
  );
};

const ThresholdTable: React.FC<{
  report: LabeledEvaluationReport;
  styles: ReturnType<typeof useStyles>;
}> = ({ report, styles }) => (
  <table className={styles.table}>
    <thead>
      <tr>
        <th>Threshold</th>
        <th>Zero-shot coverage</th>
        <th>Zero-shot false accepts</th>
        <th>Labeled coverage</th>
        <th>Labeled false accepts</th>
      </tr>
    </thead>
    <tbody>
      {Object.keys(report.variants.zero_shot.aggregate.thresholds).map((threshold) => {
        const zero = report.variants.zero_shot.aggregate.thresholds[threshold];
        const labeled = report.variants.labeled.aggregate.thresholds[threshold];
        return (
          <tr key={threshold}>
            <td><Body1Strong>{Number(threshold).toFixed(2)}</Body1Strong></td>
            <td>{percent(zero.coverage)}</td>
            <td>{zero.false_accepts}</td>
            <td>{percent(labeled.coverage)}</td>
            <td>{labeled.false_accepts}</td>
          </tr>
        );
      })}
    </tbody>
  </table>
);

const progressLabel = (event: LabeledStepEvent) => {
  if (event.step_id === "load_report") return event.status === "done" ? "Cached report loaded" : "Loading cached report";
  if (event.step_id === "score") return event.status === "done" ? "Scoring complete" : "Scoring held-out fields";
  const variant = event.variant === "labeled" ? "Labeled" : "Zero-shot";
  return `${variant}: ${event.file_name || "sample"} · run ${event.repeat || 1}`;
};

export default LabeledAnalyzerPage;