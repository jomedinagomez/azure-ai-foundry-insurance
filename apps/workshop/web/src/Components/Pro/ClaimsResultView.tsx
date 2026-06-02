import React from "react";
import { Card, CardHeader, Badge, Body1Strong, Caption1, Divider, Text } from "@fluentui/react-components";
import type { ProClaimsResult } from "../../services/proService";

interface Props {
  result: ProClaimsResult;
}

const PILL = (label: string, value?: string | null) => (
  <div style={{ display: "flex", flexDirection: "column", minWidth: 140 }}>
    <Caption1 style={{ opacity: 0.7 }}>{label}</Caption1>
    <Body1Strong>{value ?? "—"}</Body1Strong>
  </div>
);

const COVERAGE_COLOR = {
  Yes: "success",
  Partial: "warning",
  No: "danger",
  Unknown: "informative",
} as const;

const ClaimsResultView: React.FC<Props> = ({ result }) => {
  const f = result.fields;
  const m = result.meta;
  const totalStr = f.estimated_total != null ? `$${f.estimated_total.toLocaleString()}` : "—";
  const coverageColor = COVERAGE_COLOR[(f.coverage_applies as keyof typeof COVERAGE_COLOR) || "Unknown"];

  return (
    <div style={{ display: "flex", flexDirection: "column", rowGap: 12 }}>
      {/* meta strip */}
      <Caption1>
        Analyzer <code>{m.analyzer_id}</code> · API {m.api_version} · {m.input_files.length} inputs · {m.elapsed_sec?.toFixed?.(1) ?? "?"}s
      </Caption1>

      {/* headline pills */}
      <Card>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 24, padding: 12 }}>
          {PILL("Claimant", f.claimant_name)}
          {PILL("Policy #", f.policy_number)}
          {PILL("VIN", f.vin)}
          {PILL("Date of loss", f.date_of_loss)}
          {PILL("Loss location", f.loss_location)}
          {PILL("Estimated total", totalStr)}
        </div>
      </Card>

      {/* coverage + completeness */}
      <Card>
        <CardHeader header={<Body1Strong>Coverage verdict</Body1Strong>} />
        <div style={{ display: "flex", gap: 16, padding: "0 12px 12px 12px", flexWrap: "wrap" }}>
          <Badge appearance="tint" color={coverageColor as never} size="large">
            Coverage applies: {f.coverage_applies ?? "Unknown"}
          </Badge>
          <Badge appearance="tint" size="large">
            Police report: {f.police_report_present ?? "Unknown"}
          </Badge>
          <Badge appearance="tint" size="large">
            Document set: {f.document_set_completeness ?? "Unknown"}
          </Badge>
        </div>
      </Card>

      {/* narratives */}
      {f.incident_narrative && (
        <Card>
          <CardHeader header={<Body1Strong>Incident narrative</Body1Strong>} />
          <Text style={{ padding: "0 12px 12px 12px", whiteSpace: "pre-wrap" }}>
            {f.incident_narrative}
          </Text>
        </Card>
      )}

      {f.damage_visible_in_photo && (
        <Card>
          <CardHeader header={<Body1Strong>Damage visible in photo</Body1Strong>} />
          <Text style={{ padding: "0 12px 12px 12px" }}>{f.damage_visible_in_photo}</Text>
        </Card>
      )}

      {f.claims_handler_verdict && (
        <Card>
          <CardHeader header={<Body1Strong>Claims-handler verdict</Body1Strong>} />
          <Text style={{ padding: "0 12px 12px 12px", whiteSpace: "pre-wrap" }}>
            {f.claims_handler_verdict}
          </Text>
        </Card>
      )}
    </div>
  );
};

export default ClaimsResultView;
