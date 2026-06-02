import React from "react";
import {
  Tab,
  TabList,
  TabValue,
  Caption1,
  Body1Strong,
} from "@fluentui/react-components";
import HierarchicalTable from "./HierarchicalTable";
import type { SecStatement, StatementType } from "../../services/secService";

interface Props {
  statements: SecStatement[];
  showConfidence?: boolean;
  onSelectStatement?: (statement: SecStatement) => void;
}

const ORDER: StatementType[] = [
  "BalanceSheet",
  "IncomeStatement",
  "ComprehensiveIncome",
  "Equity",
  "CashFlow",
  "Other",
];

const LABELS: Record<StatementType, string> = {
  BalanceSheet: "Balance Sheet",
  IncomeStatement: "Income",
  ComprehensiveIncome: "Comp. Income",
  Equity: "Equity",
  CashFlow: "Cash Flows",
  Other: "Other",
};

const StatementTabs: React.FC<Props> = ({ statements, showConfidence = true, onSelectStatement }) => {
  const sorted = [...statements].sort(
    (a, b) => ORDER.indexOf(a.statement_type) - ORDER.indexOf(b.statement_type)
  );
  const [selected, setSelected] = React.useState<TabValue>(
    sorted[0] ? `${sorted[0].statement_type}__0` : "none"
  );

  if (sorted.length === 0) {
    return <Caption1>No financial statements extracted.</Caption1>;
  }

  return (
    <div>
      <TabList
        selectedValue={selected}
        onTabSelect={(_, d) => {
          setSelected(d.value);
          if (onSelectStatement) {
            const idx = sorted.findIndex(
              (s, i) => `${s.statement_type}__${i}` === d.value
            );
            if (idx >= 0) onSelectStatement(sorted[idx]);
          }
        }}
        size="small"
      >
        {sorted.map((s, i) => (
          <Tab key={`${s.statement_type}__${i}`} value={`${s.statement_type}__${i}`}>
            {LABELS[s.statement_type]} {i > 0 && sorted[i - 1].statement_type === s.statement_type ? `#${i + 1}` : ""}
          </Tab>
        ))}
      </TabList>
      <div style={{ marginTop: 12 }}>
        {sorted.map((s, i) => {
          const key = `${s.statement_type}__${i}`;
          if (key !== selected) return null;
          return (
            <div key={key}>
              <div style={{ marginBottom: 8 }}>
                <Body1Strong>{s.table_title || LABELS[s.statement_type]}</Body1Strong>
                {(s.company_name || s.unit || s.page_start) && (
                  <div>
                    <Caption1>
                      {[
                        s.company_name,
                        s.unit ? `in ${s.unit}` : null,
                        s.page_start ? `pp. ${s.page_start}${s.page_end && s.page_end !== s.page_start ? `–${s.page_end}` : ""}` : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </Caption1>
                  </div>
                )}
              </div>
              <HierarchicalTable
                statement={s}
                showConfidence={showConfidence}
                onRowClick={onSelectStatement ? (stmt) => onSelectStatement(stmt) : undefined}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default StatementTabs;
