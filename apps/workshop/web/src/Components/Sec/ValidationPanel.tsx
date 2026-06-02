import React from "react";
import {
  Caption1,
  Body1Strong,
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Badge,
} from "@fluentui/react-components";
import type { SecValidationResult } from "../../services/secService";

interface Props {
  validation: SecValidationResult | null;
}

const ValidationPanel: React.FC<Props> = ({ validation }) => {
  if (!validation) return null;
  if (!validation.has_ground_truth) {
    return (
      <Caption1>
        No ground-truth file present for this sample under
        <code> demo/sec/reference/expected-output/</code>.
      </Caption1>
    );
  }
  const pct = Math.round(validation.overall_match_rate * 100);
  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Body1Strong>Validation</Body1Strong>{" "}
        <Badge appearance="filled" color={pct >= 80 ? "success" : pct >= 50 ? "warning" : "danger"}>
          {pct}% line-item match
        </Badge>
      </div>
      <Table size="small">
        <TableHeader>
          <TableRow>
            <TableHeaderCell>Statement</TableHeaderCell>
            <TableHeaderCell>Expected</TableHeaderCell>
            <TableHeaderCell>Actual</TableHeaderCell>
            <TableHeaderCell>Matched</TableHeaderCell>
            <TableHeaderCell>Missing</TableHeaderCell>
            <TableHeaderCell>Extra</TableHeaderCell>
          </TableRow>
        </TableHeader>
        <TableBody>
          {validation.statements.map((s, i) => (
            <TableRow key={i}>
              <TableCell>{s.statement_type}</TableCell>
              <TableCell>{s.expected_rows}</TableCell>
              <TableCell>{s.actual_rows}</TableCell>
              <TableCell>{s.matched_rows}</TableCell>
              <TableCell>{s.missing_rows.length}</TableCell>
              <TableCell>{s.extra_rows.length}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};

export default ValidationPanel;
