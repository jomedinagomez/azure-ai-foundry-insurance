import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Body1,
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  ProgressBar,
  Text,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { DismissRegular } from "@fluentui/react-icons";

import {
  Pipeline,
  PipelineRunResult,
  StepEvent,
  runPipelineStream,
} from "../../services/pipelinesService";
import PipelineDagView from "./PipelineDagView";

export interface RunDialogProps {
  open: boolean;
  pipeline: Pipeline;
  sampleName: string;
  onClose: () => void;
  onComplete?: (result: PipelineRunResult) => void;
}

const useStyles = makeStyles({
  surface: { width: "min(960px, 95vw)", maxHeight: "90vh" },
  dag: {
    height: "320px",
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke3),
    ...shorthands.borderRadius("6px"),
    backgroundColor: tokens.colorNeutralBackground2,
    marginBottom: "12px",
  },
  steps: {
    display: "flex",
    flexDirection: "column",
    rowGap: "6px",
    maxHeight: "240px",
    overflowY: "auto",
    ...shorthands.padding("8px"),
    ...shorthands.borderRadius("6px"),
    backgroundColor: tokens.colorNeutralBackground2,
  },
  row: {
    display: "grid",
    gridTemplateColumns: "20px 1fr 80px",
    columnGap: "8px",
    alignItems: "center",
    fontSize: "13px",
  },
  rowDone: { color: tokens.colorPaletteGreenForeground1 },
  rowError: { color: tokens.colorPaletteRedForeground1 },
  rowRunning: { color: tokens.colorPaletteBlueForeground2, fontWeight: 600 },
  meta: { color: tokens.colorNeutralForeground3 },
});

function statusGlyph(s: StepEvent["status"]): string {
  if (s === "running") return "●";
  if (s === "done") return "✓";
  if (s === "error") return "✕";
  return "○";
}

export default function RunDialog({
  open,
  pipeline,
  sampleName,
  onClose,
  onComplete,
}: RunDialogProps) {
  const styles = useStyles();
  const [events, setEvents] = useState<Record<string, StepEvent>>({});
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineRunResult | null>(null);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Reset state every time the dialog opens for a new run.
  useEffect(() => {
    if (!open) return;
    setEvents({});
    setErrMsg(null);
    setResult(null);
    setRunning(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    runPipelineStream(
      pipeline.id,
      sampleName,
      {
        onStep: (e) => {
          setEvents((prev) => ({ ...prev, [e.step_id]: e }));
        },
        onComplete: (r) => {
          setResult(r);
          setRunning(false);
          onComplete?.(r);
        },
        onError: (m) => {
          setErrMsg(m);
          setRunning(false);
        },
      },
      false,
      ctrl.signal
    ).catch(() => {
      // surfaced via onError
    });

    return () => {
      ctrl.abort();
      setRunning(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, pipeline.id, sampleName]);

  const totalSteps = pipeline.steps.length;
  const doneSteps = Object.values(events).filter((e) => e.status === "done").length;
  const progress = totalSteps === 0 ? 0 : doneSteps / totalSteps;

  const orderedSteps = useMemo(() => {
    return pipeline.steps.map((s) => ({ step: s, ev: events[s.id] }));
  }, [pipeline, events]);

  return (
    <Dialog
      open={open}
      onOpenChange={(_, d) => {
        if (!d.open) {
          abortRef.current?.abort();
          onClose();
        }
      }}
      modalType="modal"
    >
      <DialogSurface className={styles.surface}>
        <DialogBody>
          <DialogTitle>
            Running <Text weight="semibold">{pipeline.name}</Text> on{" "}
            <Text weight="semibold">{sampleName}</Text>
          </DialogTitle>
          <DialogContent>
            <div className={styles.dag}>
              <PipelineDagView pipeline={pipeline} inputLabel={sampleName} events={events} />
            </div>
            <ProgressBar value={progress} thickness="medium" />
            <div style={{ display: "flex", justifyContent: "space-between", margin: "6px 0 12px" }}>
              <Caption1>
                {doneSteps}/{totalSteps} steps complete
              </Caption1>
              <Caption1>{running ? "running…" : result ? "done" : errMsg ? "error" : ""}</Caption1>
            </div>

            <div className={styles.steps}>
              {orderedSteps.map(({ step, ev }) => {
                const cls =
                  ev?.status === "running"
                    ? styles.rowRunning
                    : ev?.status === "done"
                    ? styles.rowDone
                    : ev?.status === "error"
                    ? styles.rowError
                    : "";
                const metaBits: string[] = [];
                if (ev?.meta?.size_bytes)
                  metaBits.push(`${(ev.meta.size_bytes as number).toLocaleString()} B`);
                if (ev?.meta?.dpi) metaBits.push(`${ev.meta.dpi} dpi`);
                if (ev?.meta?.image_count) metaBits.push(`${ev.meta.image_count} imgs`);
                if (ev?.meta?.image_call_count)
                  metaBits.push(`${ev.meta.image_call_count} CU calls`);
                return (
                  <div key={step.id} className={`${styles.row} ${cls}`}>
                    <div style={{ textAlign: "center" }}>{statusGlyph(ev?.status ?? "pending")}</div>
                    <div>
                      {step.label || step.kind}
                      {metaBits.length > 0 && (
                        <span className={styles.meta}> · {metaBits.join(" · ")}</span>
                      )}
                      {ev?.error && (
                        <Body1 style={{ color: tokens.colorPaletteRedForeground1 }}>
                          {ev.error}
                        </Body1>
                      )}
                    </div>
                    <div style={{ textAlign: "right" }}>
                      {ev?.elapsed_sec != null ? `${ev.elapsed_sec}s` : ""}
                    </div>
                  </div>
                );
              })}
            </div>

            {errMsg && (
              <Body1 style={{ color: tokens.colorPaletteRedForeground1, marginTop: 12 }}>
                {errMsg}
              </Body1>
            )}
            {result && (
              <div style={{ marginTop: 12 }}>
                <Body1>
                  Pipeline completed in{" "}
                  <strong>
                    {Object.values(result.timings).reduce((a, b) => a + b, 0).toFixed(2)}s
                  </strong>
                  .
                </Body1>
              </div>
            )}
          </DialogContent>
          <DialogActions>
            <Button
              icon={<DismissRegular />}
              appearance="secondary"
              onClick={() => {
                abortRef.current?.abort();
                onClose();
              }}
            >
              Close
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
