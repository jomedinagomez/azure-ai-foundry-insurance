import React from "react";
import { Button, Caption1, Dropdown, Option, Tab, TabList } from "@fluentui/react-components";
import { ArrowDownloadRegular, CopyRegular, DocumentPdfRegular, ImageRegular } from "@fluentui/react-icons";
import { toast } from "react-toastify";

import type { ProSampleFile, ProSampleManifest } from "../../services/proService";
import { sampleFileUrl } from "../../services/proService";
import ProPdfViewer from "./ProPdfViewer";

type RefTab = "preview" | "raw";

interface Props {
  sample: ProSampleManifest | null;
  rawResponse: Record<string, unknown> | null;
}

const REFERENCE_FILE_LABEL = "Reference policy (auto_policy.pdf)";

const ProReferencePane: React.FC<Props> = ({ sample, rawResponse }) => {
  const [tab, setTab] = React.useState<RefTab>("preview");
  const [selectedFile, setSelectedFile] = React.useState<string>("");

  React.useEffect(() => {
    if (!sample) {
      setSelectedFile("");
      return;
    }
    // Default to the FNOL/claim form so the user immediately sees the
    // most informative document.
    const fnol = sample.files.find((f) => f.kind === "fnol");
    setSelectedFile((fnol ?? sample.files[0])?.name ?? "");
  }, [sample?.id]);

  const fileByName = React.useMemo(() => {
    const map = new Map<string, ProSampleFile>();
    for (const f of sample?.files ?? []) map.set(f.name, f);
    return map;
  }, [sample?.id]);

  const activeFile = fileByName.get(selectedFile) ?? null;
  const activeUrl = sample && selectedFile ? sampleFileUrl(sample.id, selectedFile) : "";

  const copyRaw = async () => {
    if (!rawResponse) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(rawResponse, null, 2));
      toast.success("Copied raw CU response to clipboard");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  const downloadRaw = () => {
    if (!rawResponse) return;
    const blob = new Blob([JSON.stringify(rawResponse, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${sample?.id ?? "pro"}__raw.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const rawSize = rawResponse
    ? new Blob([JSON.stringify(rawResponse)]).size
    : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 520 }}>
      <TabList
        selectedValue={tab}
        onTabSelect={(_, d) => setTab(d.value as RefTab)}
        size="small"
      >
        <Tab value="preview" icon={<DocumentPdfRegular />}>
          Source documents
        </Tab>
        <Tab value="raw" disabled={!rawResponse}>
          Raw JSON
        </Tab>
      </TabList>

      <div style={{ flex: 1, overflow: "auto", paddingTop: 8 }}>
        {tab === "preview" && !sample && (
          <Caption1>Pick a sample to preview the source documents.</Caption1>
        )}
        {tab === "preview" && sample && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, height: "100%" }}>
            <Dropdown
              size="small"
              value={selectedFile}
              selectedOptions={[selectedFile]}
              onOptionSelect={(_, d) => d.optionValue && setSelectedFile(d.optionValue)}
            >
              {sample.files.map((f) => (
                <Option key={f.name} value={f.name} text={f.name}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    {f.media_type.startsWith("image/") ? (
                      <ImageRegular />
                    ) : (
                      <DocumentPdfRegular />
                    )}
                    {f.name}
                    {f.tampered ? " ⚠ tampered" : ""}
                  </span>
                </Option>
              ))}
            </Dropdown>

            {activeFile && activeUrl && (
              <div style={{ flex: 1, minHeight: 480 }}>
                {activeFile.media_type.startsWith("image/") ? (
                  <div
                    style={{
                      height: "100%",
                      minHeight: 480,
                      border: "1px solid var(--colorNeutralStroke2)",
                      borderRadius: 6,
                      background: "var(--colorNeutralBackground2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: 8,
                    }}
                  >
                    <img
                      src={activeUrl}
                      alt={activeFile.name}
                      style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
                    />
                  </div>
                ) : (
                  <ProPdfViewer url={activeUrl} />
                )}
              </div>
            )}

            <Caption1 style={{ opacity: 0.7 }}>
              Reference policy is baked into the analyzer at deploy time and
              isn't part of the per-claim file list — analyzers reason against
              it implicitly.
            </Caption1>
          </div>
        )}

        {tab === "raw" && rawResponse && (
          <div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
              <Button size="small" icon={<CopyRegular />} onClick={copyRaw}>
                Copy
              </Button>
              <Button size="small" icon={<ArrowDownloadRegular />} onClick={downloadRaw}>
                Download .json
              </Button>
              <Caption1 style={{ marginLeft: 8 }}>{(rawSize / 1024).toFixed(1)} KB</Caption1>
            </div>
            <pre
              style={{
                maxHeight: "calc(100vh - 280px)",
                overflow: "auto",
                background: "var(--colorNeutralBackground3)",
                color: "var(--colorNeutralForeground1)",
                padding: 12,
                borderRadius: 4,
                fontSize: 12,
                lineHeight: 1.45,
                margin: 0,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              }}
            >
              {JSON.stringify(rawResponse, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export { REFERENCE_FILE_LABEL };
export default ProReferencePane;
