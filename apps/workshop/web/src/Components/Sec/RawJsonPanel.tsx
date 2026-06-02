import React from "react";
import { Button, Caption1 } from "@fluentui/react-components";
import { CopyRegular, ArrowDownloadRegular } from "@fluentui/react-icons";
import { toast } from "react-toastify";

interface Props {
  data: unknown;
  /** Label used in download filename, e.g. "10K-GOOG-01-31-2024__raw". */
  filenameStem?: string;
  maxHeight?: number | string;
}

const RawJsonPanel: React.FC<Props> = ({ data, filenameStem = "raw", maxHeight = 520 }) => {
  const text = React.useMemo(() => JSON.stringify(data, null, 2), [data]);
  const size = new Blob([text]).size;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied JSON to clipboard");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  const download = () => {
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filenameStem}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
        <Button size="small" icon={<CopyRegular />} onClick={copy}>
          Copy
        </Button>
        <Button size="small" icon={<ArrowDownloadRegular />} onClick={download}>
          Download .json
        </Button>
        <Caption1 style={{ color: "var(--colorNeutralForeground3)", marginLeft: 8 }}>
          {(size / 1024).toFixed(1)} KB
        </Caption1>
      </div>
      <pre
        style={{
          maxHeight,
          overflow: "auto",
          background: "var(--colorNeutralBackground3)",
          color: "var(--colorNeutralForeground1)",
          padding: 12,
          borderRadius: 4,
          fontSize: 12,
          lineHeight: 1.45,
          margin: 0,
          fontFamily:
            "'Cascadia Code', 'JetBrains Mono', Consolas, 'Courier New', monospace",
        }}
      >
        {text}
      </pre>
    </div>
  );
};

export default RawJsonPanel;
