import React from "react";
import { Caption1, Spinner } from "@fluentui/react-components";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import "react-pdf/dist/esm/Page/TextLayer.css";

// Match SecPage's pdf.js worker setup.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.js",
  import.meta.url,
).toString();

interface Props {
  /** Full URL to the PDF. */
  url: string;
}

const ProPdfViewer: React.FC<Props> = ({ url }) => {
  const [numPages, setNumPages] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [width, setWidth] = React.useState(560);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  const file = React.useMemo(() => ({ url }), [url]);

  React.useEffect(() => {
    setPage(1);
  }, [url]);

  React.useEffect(() => {
    if (!containerRef.current || typeof ResizeObserver === "undefined") return;
    const el = containerRef.current;
    const ro = new ResizeObserver(() => {
      setWidth(Math.max(320, el.clientWidth - 16));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 500,
        border: "1px solid var(--colorNeutralStroke2)",
        borderRadius: 6,
        background: "var(--colorNeutralBackground2)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px",
          borderBottom: "1px solid var(--colorNeutralStroke2)",
          background: "var(--colorNeutralBackground1)",
        }}
      >
        <button
          type="button"
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          style={{ cursor: page <= 1 ? "default" : "pointer" }}
        >
          ‹
        </button>
        <Caption1>
          Page {page} / {numPages || "?"}
        </Caption1>
        <button
          type="button"
          onClick={() => setPage((p) => Math.min(numPages || p, p + 1))}
          disabled={!numPages || page >= numPages}
          style={{ cursor: !numPages || page >= numPages ? "default" : "pointer" }}
        >
          ›
        </button>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
        <Document
          file={file}
          onLoadSuccess={(d) => setNumPages(d.numPages)}
          loading={<Spinner size="small" label="Loading PDF…" />}
          error={<Caption1>Couldn't load the PDF.</Caption1>}
        >
          <Page
            pageNumber={page}
            width={width}
            renderTextLayer={false}
            renderAnnotationLayer={false}
          />
        </Document>
      </div>
    </div>
  );
};

export default ProPdfViewer;
