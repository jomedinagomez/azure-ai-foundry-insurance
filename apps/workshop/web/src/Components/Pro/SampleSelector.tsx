import React from "react";
import { Card, CardHeader, Body1Strong, Caption1, Badge, Button } from "@fluentui/react-components";
import { DocumentPdfRegular, ImageRegular } from "@fluentui/react-icons";
import type { ProSampleManifest, Scenario } from "../../services/proService";
import { sampleFileUrl } from "../../services/proService";

interface Props {
  samples: ProSampleManifest[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  filterScenario?: Scenario;
}

const SampleSelector: React.FC<Props> = ({ samples, selectedId, onSelect, filterScenario }) => {
  const visible = filterScenario
    ? samples.filter((s) => s.scenario === filterScenario)
    : samples;

  if (visible.length === 0) {
    return <Caption1>No samples available for this scenario.</Caption1>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", rowGap: 8 }}>
      {visible.map((s) => {
        const selected = s.id === selectedId;
        const badgeColor: "danger" | "success" = s.scenario === "fraud" ? "danger" : "success";
        return (
          <Card
            key={s.id}
            onClick={() => onSelect(s.id)}
            style={{
              cursor: "pointer",
              padding: "10px 12px",
              borderLeft: selected ? "3px solid #0a3b66" : "3px solid transparent",
              background: selected ? "var(--colorNeutralBackground2)" : undefined,
            }}
          >
            <CardHeader
              header={<Body1Strong>{s.title}</Body1Strong>}
              description={
                <Caption1>
                  <Badge appearance="tint" color={badgeColor} style={{ marginRight: 6 }}>
                    {s.scenario}
                  </Badge>
                  {s.loss_type}
                </Caption1>
              }
            />
            <Caption1 style={{ display: "block", marginTop: 4 }}>{s.description}</Caption1>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
              {s.files.map((f) => (
                <Button
                  key={f.name}
                  appearance="subtle"
                  size="small"
                  icon={f.media_type.startsWith("image/") ? <ImageRegular /> : <DocumentPdfRegular />}
                  as="a"
                  href={sampleFileUrl(s.id, f.name)}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e: React.MouseEvent) => e.stopPropagation()}
                >
                  {f.name}
                  {f.tampered ? " ⚠" : ""}
                </Button>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
};

export default SampleSelector;
