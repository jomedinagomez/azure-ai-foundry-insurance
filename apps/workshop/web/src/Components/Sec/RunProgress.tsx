import React from "react";
import {
  Spinner,
  Caption1,
  Body1Strong,
  Badge,
} from "@fluentui/react-components";
import {
  CheckmarkCircleFilled,
  ErrorCircleRegular,
} from "@fluentui/react-icons";
import type { SecStepEvent } from "../../services/secService";

interface Props {
  events: SecStepEvent[];
  running: boolean;
  error?: string | null;
}

const LABELS: Record<string, string> = {
  load_cache: "Load cached payload",
  deploy_analyzers: "Deploy analyzers",
  cu_classify_and_extract: "Classify + extract",
  merge_segments: "Merge segments",
  excel_export: "Export to Excel",
};

const RunProgress: React.FC<Props> = ({ events, running, error }) => {
  // Coalesce by step_id (running -> done)
  const byStep = new Map<string, SecStepEvent>();
  events.forEach((e) => byStep.set(e.step_id, e));
  const ordered = Array.from(byStep.values());

  if (!running && ordered.length === 0 && !error) return null;

  return (
    <div
      style={{
        border: "1px solid var(--colorNeutralStroke2)",
        borderRadius: 6,
        padding: 12,
        marginTop: 12,
      }}
    >
      <Body1Strong>Run progress</Body1Strong>
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0 0" }}>
        {ordered.map((e) => {
          const label = LABELS[e.step_id] || e.step_id;
          let icon: React.ReactNode = null;
          if (e.status === "running") icon = <Spinner size="tiny" />;
          else if (e.status === "done")
            icon = <CheckmarkCircleFilled style={{ color: "var(--colorPaletteGreenForeground1)" }} />;
          else if (e.status === "error") icon = <ErrorCircleRegular />;

          const extras: string[] = [];
          if (e.step_id === "cu_classify_and_extract" && e.status === "done") {
            const retries = e.retries as number | undefined;
            const cats = e.segment_categories as Record<string, number> | undefined;
            if (retries && retries > 0) extras.push(`${retries} retries`);
            if (cats) extras.push(`segments: ${Object.entries(cats).map(([k, v]) => `${k}:${v}`).join(", ")}`);
          }
          if (e.step_id === "load_cache" && e.status === "done") {
            extras.push(e.from_cache ? "cache hit" : "no cache");
          }

          return (
            <li
              key={e.step_id}
              style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 0" }}
            >
              <span style={{ width: 18, display: "inline-flex" }}>{icon}</span>
              <span style={{ minWidth: 180 }}>{label}</span>
              {extras.length > 0 && (
                <Caption1 style={{ color: "var(--colorNeutralForeground3)" }}>
                  {extras.join(" · ")}
                </Caption1>
              )}
            </li>
          );
        })}
      </ul>
      {error && (
        <div style={{ marginTop: 8 }}>
          <Badge appearance="filled" color="danger">
            {error}
          </Badge>
        </div>
      )}
    </div>
  );
};

export default RunProgress;
