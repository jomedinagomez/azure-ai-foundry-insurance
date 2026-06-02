import React from "react";
import { Card, CardHeader, Body1Strong, Caption1, Text } from "@fluentui/react-components";
import type { ProFraudResult } from "../../services/proService";
import RiskScoreGauge from "./RiskScoreGauge";
import FraudSignalsTable from "./FraudSignalsTable";

interface Props {
  result: ProFraudResult;
}

const FraudResultView: React.FC<Props> = ({ result }) => {
  const m = result.meta;
  const f = result.fields;
  return (
    <div style={{ display: "flex", flexDirection: "column", rowGap: 12 }}>
      <Caption1>
        Analyzer <code>{m.analyzer_id}</code> · API {m.api_version} · {m.input_files.length} inputs · {m.elapsed_sec?.toFixed?.(1) ?? "?"}s
      </Caption1>

      <Card>
        <div style={{ display: "flex", padding: 12, alignItems: "center", gap: 24 }}>
          <RiskScoreGauge score={result.risk_score} band={result.risk_band} />
          <div style={{ flex: 1 }}>
            <Body1Strong>Overall fraud indication: {f.overall_fraud_indication ?? "—"}</Body1Strong>
            {f.rationale && (
              <Text style={{ display: "block", marginTop: 6, whiteSpace: "pre-wrap" }}>
                {f.rationale}
              </Text>
            )}
            <Caption1 style={{ display: "block", marginTop: 10 }}>
              Rule signals: <b>{result.rule_signals.length}</b> ·
              CU reasoning signals: <b>{result.cu_signals.length}</b>
            </Caption1>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader header={<Body1Strong>Signals</Body1Strong>} />
        <div style={{ padding: "0 12px 12px 12px" }}>
          <FraudSignalsTable
            ruleSignals={result.rule_signals}
            cuSignals={result.cu_signals}
          />
        </div>
      </Card>
    </div>
  );
};

export default FraudResultView;
