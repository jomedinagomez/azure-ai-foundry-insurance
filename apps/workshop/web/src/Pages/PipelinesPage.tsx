import React, { useEffect, useMemo, useState } from "react";
import {
  Badge,
  Body1,
  Button,
  Caption1,
  Dropdown,
  MessageBar,
  MessageBarBody,
  Option,
  Subtitle2,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { PlayRegular } from "@fluentui/react-icons";

import { fetchPipelines, Pipeline } from "../services/pipelinesService";
import { fetchSovSamples, SovSample } from "../services/sovService";
import PipelineDagView from "../Components/Pipelines/PipelineDagView";
import RunDialog from "../Components/Pipelines/RunDialog";

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
    rowGap: "12px",
    overflowY: "auto",
  },
  group: {
    display: "flex",
    flexDirection: "column",
    rowGap: "6px",
  },
  groupHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  card: {
    cursor: "pointer",
    display: "flex",
    flexDirection: "column",
    rowGap: "4px",
    ...shorthands.padding("10px", "12px"),
    ...shorthands.borderRadius("8px"),
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke2),
    backgroundColor: tokens.colorNeutralBackground1,
  },
  cardSelected: {
    outline: `2px solid ${tokens.colorBrandStroke1}`,
  },
  cardName: {
    display: "flex",
    alignItems: "center",
    columnGap: "6px",
    fontWeight: 600,
  },
  main: {
    display: "flex",
    flexDirection: "column",
    rowGap: "12px",
    minWidth: 0,
  },
  headerStrip: {
    display: "flex",
    alignItems: "center",
    columnGap: "12px",
    flexWrap: "wrap",
  },
  dagWrap: {
    flex: 1,
    minHeight: "360px",
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke3),
    ...shorthands.borderRadius("8px"),
    backgroundColor: tokens.colorNeutralBackground2,
  },
  jsonBox: {
    fontFamily: "Consolas, monospace",
    fontSize: "12px",
    whiteSpace: "pre",
    maxHeight: "200px",
    overflow: "auto",
    ...shorthands.padding("8px"),
    backgroundColor: tokens.colorNeutralBackground3,
    ...shorthands.borderRadius("6px"),
  },
});

function groupExtensions(pipelines: Pipeline[]): Record<string, Pipeline[]> {
  const groups: Record<string, Pipeline[]> = {};
  for (const p of pipelines) {
    const key = [...p.input_extensions].sort().join(", ") || "(none)";
    if (!groups[key]) groups[key] = [];
    groups[key].push(p);
  }
  return groups;
}

export default function PipelinesPage() {
  const styles = useStyles();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [samples, setSamples] = useState<SovSample[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runOpen, setRunOpen] = useState(false);
  const [runSample, setRunSample] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchPipelines(), fetchSovSamples()])
      .then(([ps, ss]) => {
        setPipelines(ps);
        setSamples(ss);
        if (ps.length && !selectedId) setSelectedId(ps[0].id);
      })
      .catch((e: any) => setError(e?.message ?? String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = useMemo(
    () => pipelines.find((p) => p.id === selectedId) ?? null,
    [pipelines, selectedId]
  );
  const groups = useMemo(() => groupExtensions(pipelines), [pipelines]);

  // Default the run sample to one whose extension matches the selected pipeline.
  useEffect(() => {
    if (!selected || samples.length === 0) return;
    const exts = selected.input_extensions.map((e) => e.toLowerCase());
    const candidate = samples.find((s) =>
      exts.includes("." + s.file_name.toLowerCase().split(".").pop())
    );
    setRunSample(candidate?.file_name ?? samples[0].file_name);
  }, [selected, samples]);

  return (
    <div className={styles.root}>
      {/* Left rail: pipelines grouped by extension */}
      <div className={styles.rail}>
        <Subtitle2>Pipelines</Subtitle2>
        {Object.entries(groups).map(([exts, ps]) => (
          <div key={exts} className={styles.group}>
            <div className={styles.groupHeader}>
              <Caption1>{exts}</Caption1>
            </div>
            {ps.map((p) => (
              <div
                key={p.id}
                className={`${styles.card} ${p.id === selectedId ? styles.cardSelected : ""}`}
                onClick={() => setSelectedId(p.id)}
              >
                <div className={styles.cardName}>
                  {p.name}
                  {p.is_default && <Badge appearance="filled" color="brand">default</Badge>}
                </div>
                <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>
                  {p.steps.length} step{p.steps.length === 1 ? "" : "s"}
                  {" · "}
                  terminal: {p.steps[p.steps.length - 1]?.params.analyzer_id ?? "?"}
                </Caption1>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Main: header + DAG + run controls */}
      <div className={styles.main}>
        {error && (
          <MessageBar intent="error">
            <MessageBarBody>{error}</MessageBarBody>
          </MessageBar>
        )}

        {selected && (
          <>
            <div className={styles.headerStrip}>
              <Subtitle2 style={{ flex: 1 }}>{selected.name}</Subtitle2>
              <Dropdown
                placeholder="Pick a sample"
                value={runSample ?? ""}
                selectedOptions={runSample ? [runSample] : []}
                onOptionSelect={(_, d) => setRunSample(d.optionValue ?? null)}
                style={{ minWidth: 240 }}
              >
                {samples.map((s) => (
                  <Option key={s.file_name} value={s.file_name}>
                    {s.file_name}
                  </Option>
                ))}
              </Dropdown>
              <Button
                appearance="primary"
                icon={<PlayRegular />}
                disabled={!runSample}
                onClick={() => setRunOpen(true)}
              >
                Run pipeline
              </Button>
            </div>

            {selected.description && <Body1>{selected.description}</Body1>}

            <div className={styles.dagWrap}>
              <PipelineDagView pipeline={selected} inputLabel={runSample ?? undefined} />
            </div>
          </>
        )}
      </div>

      {selected && runSample && (
        <RunDialog
          open={runOpen}
          pipeline={selected}
          sampleName={runSample}
          onClose={() => setRunOpen(false)}
        />
      )}
    </div>
  );
}
