import React from "react";
import { Badge, Body1Strong, Caption1, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow } from "@fluentui/react-components";
import type { FraudSignal } from "../../services/proService";

interface Props {
  ruleSignals: FraudSignal[];
  cuSignals: FraudSignal[];
}

const SEV_COLOR = { low: "informative", medium: "warning", high: "danger" } as const;

const Row: React.FC<{ s: FraudSignal; origin: "rule" | "cu" }> = ({ s, origin }) => (
  <TableRow>
    <TableCell>
      <Badge appearance="tint" color={SEV_COLOR[s.severity]}>{s.severity}</Badge>
    </TableCell>
    <TableCell>
      <Body1Strong>{s.title}</Body1Strong>
      <Caption1 style={{ display: "block", marginTop: 2 }}>
        <code style={{ fontSize: 11 }}>{s.rule_id}</code> · {origin === "rule" ? "rule engine" : "CU reasoning"} · weight {s.weight}
      </Caption1>
    </TableCell>
    <TableCell>
      <Caption1>{s.evidence}</Caption1>
      {s.source_documents.length > 0 && (
        <Caption1 style={{ display: "block", marginTop: 4, opacity: 0.7 }}>
          Source: {s.source_documents.join(" · ")}
        </Caption1>
      )}
    </TableCell>
  </TableRow>
);

const FraudSignalsTable: React.FC<Props> = ({ ruleSignals, cuSignals }) => {
  const total = ruleSignals.length + cuSignals.length;
  if (total === 0) {
    return <Caption1>No fraud signals detected — package looks consistent.</Caption1>;
  }
  return (
    <Table size="small">
      <TableHeader>
        <TableRow>
          <TableHeaderCell style={{ width: 90 }}>Severity</TableHeaderCell>
          <TableHeaderCell style={{ width: 300 }}>Signal</TableHeaderCell>
          <TableHeaderCell>Evidence</TableHeaderCell>
        </TableRow>
      </TableHeader>
      <TableBody>
        {ruleSignals.map((s) => <Row key={`r-${s.rule_id}`} s={s} origin="rule" />)}
        {cuSignals.map((s) => <Row key={`c-${s.rule_id}`} s={s} origin="cu" />)}
      </TableBody>
    </Table>
  );
};

export default FraudSignalsTable;
