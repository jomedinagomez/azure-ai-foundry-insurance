import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from "@fluentui/react-components";
import type { SecStatement } from "../../services/secService";

interface Props {
  statement: SecStatement;
  showConfidence?: boolean;
  onRowClick?: (statement: SecStatement, rowIndex: number) => void;
}

// Color thresholds mirror the SOV view: green ≥ 0.80, amber ≥ 0.60, red < 0.60.
function confColor(c: number | null | undefined): string | undefined {
  if (c == null || Number.isNaN(c)) return undefined;
  if (c >= 0.8) return "#107C10";
  if (c >= 0.6) return "#B7791F";
  return "#B00020";
}

// Collapse consecutive identical group labels into spanned header cells, e.g.
// ["Year Ended December 31,", "Year Ended December 31,", "Year Ended December 31,"]
// -> [{ label: "Year Ended December 31,", span: 3 }]
function spanGroups(groups: string[]): { label: string; span: number }[] {
  const out: { label: string; span: number }[] = [];
  for (const g of groups) {
    const last = out[out.length - 1];
    if (last && last.label === g) {
      last.span += 1;
    } else {
      out.push({ label: g, span: 1 });
    }
  }
  return out;
}

const HierarchicalTable: React.FC<Props> = ({ statement, showConfidence = true, onRowClick }) => {
  const { period_headers, period_groups, rows } = statement;
  const hasGroups = period_groups.some((g) => !!g);
  const grouped = hasGroups ? spanGroups(period_groups) : [];

  return (
    <div style={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHeader>
          {hasGroups && (
            <TableRow>
              <TableHeaderCell />
              {grouped.map((g, i) => (
                <TableHeaderCell
                  key={`g${i}`}
                  // Fluent's TableHeaderCell forwards unknown props to the underlying <th>.
                  {...({ colSpan: g.span } as any)}
                  style={{
                    fontStyle: "italic",
                    textAlign: "center",
                    borderBottom: g.label
                      ? "1px solid var(--colorNeutralStroke2)"
                      : undefined,
                  }}
                >
                  {g.label}
                </TableHeaderCell>
              ))}
            </TableRow>
          )}
          <TableRow>
            <TableHeaderCell>Line Item</TableHeaderCell>
            {period_headers.map((h, i) => (
              <TableHeaderCell
                key={`h${i}`}
                style={{ textAlign: "center", whiteSpace: "nowrap" }}
              >
                {h}
              </TableHeaderCell>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r, i) => {
            const indent = "   ".repeat(r.level);
            const labelStyle: React.CSSProperties = {
              whiteSpace: "pre",
              fontWeight: r.is_section_header || r.is_subtotal ? 600 : 400,
              borderTop: r.is_subtotal ? "1px solid var(--colorNeutralStroke1)" : undefined,
            };
            const valStyle: React.CSSProperties = {
              textAlign: "right",
              fontVariantNumeric: "tabular-nums",
              fontWeight: r.is_subtotal ? 600 : 400,
              borderTop: r.is_subtotal ? "1px solid var(--colorNeutralStroke1)" : undefined,
            };
            return (
              <TableRow
                key={i}
                onClick={onRowClick ? () => onRowClick(statement, i) : undefined}
                style={onRowClick ? { cursor: "pointer" } : undefined}
                title={onRowClick && statement.page_start ? `Jump to PDF p. ${statement.page_start}` : undefined}
              >
                <TableCell style={labelStyle}>{`${indent}${r.line_item}`}</TableCell>
                {period_headers.map((_, j) => {
                  const conf = r.value_confidences?.[j] ?? null;
                  const cellStyle: React.CSSProperties = { ...valStyle };
                  if (showConfidence) {
                    const c = confColor(conf);
                    if (c) cellStyle.color = c;
                  }
                  const title =
                    conf != null ? `confidence: ${conf.toFixed(3)}` : undefined;
                  return (
                    <TableCell key={j} style={cellStyle} title={title}>
                      {r.values[j] ?? ""}
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
};

export default HierarchicalTable;
