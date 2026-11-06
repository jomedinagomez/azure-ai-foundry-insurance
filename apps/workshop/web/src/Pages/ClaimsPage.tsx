import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Badge, Button, Checkbox, Dialog, DialogActions, DialogBody, DialogContent,
  DialogSurface, DialogTitle, Field, Input, Spinner, Tab, TabList,
} from "@fluentui/react-components";
import {
  ArrowClockwiseRegular, ArrowLeftRegular, CheckmarkCircleRegular,
  ChevronRightRegular, DatabaseRegular, DismissRegular, DocumentRegular,
  ChatRegular, ErrorCircleRegular, FolderRegular, FlowRegular, ImageRegular, MailRegular, PlayRegular, SearchRegular, SparkleRegular,
} from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "react-toastify";
import SourcePdfViewer from "../Components/Sec/SourcePdfViewer";
import ClaimsExecutionTree, { ExecutionTreeView } from "../Components/Claims/ClaimsExecutionTree";
import ClaimOperationsPanel from "../Components/Claims/ClaimOperationsPanel";
import ClaimsAgentChat from "../Components/Claims/ClaimsAgentChat";
import { FileView } from "../Components/Claims/executionTreeModel";
import {
  ClaimDetail, ClaimRun, ClaimsOverview, EvidenceChunk, EvidenceFile, FileDetail,
  Stage, claimFileUrl, claimsError, fetchClaim, fetchClaimFile, fetchClaimRun,
  fetchClaims, runClaims, searchClaim, stages,
} from "../services/claimsService";
import "../Styles/ClaimsPage.css";
import "../Styles/ClaimOperations.css";

const stageInfo: Record<Stage, { title: string; description: string }> = {
  files: { title: "Gather evidence", description: "Original files, nested emails and attachments. Exact duplicates share one evidence identity, without losing their source links." },
  extract: { title: "Understand", description: "Native document Markdown and figure descriptions, image observations, and locally parsed email text. Saved CU results are reused." },
  chunks: { title: "Shape the story", description: "Document sections, image observations and email text become individually traceable chunks. Conflicting accounts remain distinct." },
  embed: { title: "Make searchable", description: "Title, section, evidence kind and content are embedded together. Full vectors stay on the server; only dimensions are shown here." },
  index: { title: "Connect to Search", description: "Upload this claim to the evidence index and verify visibility. Only stale chunks belonging to this claim are removed. A saved receipt is not a live index-health check." },
};
type Popup =
  | { kind: "file"; id: string; claimId: string; tab?: FileView; fromTree?: boolean }
  | { kind: "chunk"; chunk: EvidenceChunk; fromTree?: boolean }
  | { kind: "tree" }
  | { kind: "chat"; claimId?: string }
  | { kind: "stage"; stage: Stage }
  | { kind: "run"; ids: string[] }
  | null;

const FileIcon = ({ type }: { type: string }) =>
  type === "image" ? <ImageRegular /> : type === "email" ? <MailRegular /> : <DocumentRegular />;
const kindLabel = (kind: string) => kind.replace(/_/g, " ");
const shortName = (id: string) => id.replace("claim-", "Claim ");

function Markdown({ text }: { text: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml
    components={{
      img: ({ alt }) => <span className="ce-inline-figure">[Embedded figure{alt ? `: ${alt}` : ""}]</span>,
      a: ({ children }) => <span>{children}</span>,
    }}>{text}</ReactMarkdown>;
}

function ChunkCards({ chunks, open }: { chunks: EvidenceChunk[]; open: (chunk: EvidenceChunk) => void }) {
  return <div className="ce-chunk-grid">{chunks.map((chunk, index) =>
    <button className="ce-chunk" key={chunk.id} onClick={() => open(chunk)}>
      <div className="ce-card-top"><span className="ce-eyebrow">CHUNK {chunk.chunk_id}</span>
        <Badge appearance="tint" color={chunk.source_type === "image" ? "informative" : "brand"}>{kindLabel(chunk.content_kind)}</Badge></div>
      <h3>{chunk.title}</h3>
      <p className="ce-chunk-excerpt">{chunk.caption || chunk.content}</p>
      <div className="ce-card-bottom"><span><FileIcon type={chunk.source_type} /> {chunk.filename}</span>
        {chunk.semantic_score !== undefined
          ? <span>#{index + 1} · {chunk.semantic_score.toFixed(2)} semantic</span>
          : <ChevronRightRegular />}</div>
    </button>)}</div>;
}

const ClaimsPage: React.FC = () => {
  const [overview, setOverview] = useState<ClaimsOverview | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClaimDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [job, setJob] = useState<ClaimRun | null>(null);
  const [view, setView] = useState("files");
  const [filter, setFilter] = useState("");
  const [popup, setPopup] = useState<Popup>(null);
  const [treeView, setTreeView] = useState<ExecutionTreeView>({ expandedFiles: [], expandedChunks: [], focusId: "" });
  const [file, setFile] = useState<FileDetail | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState("");
  const [fileView, setFileView] = useState("original");
  const [indexData, setIndexData] = useState(false);
  const [scanNames, setScanNames] = useState<string[]>([]);
  const [starting, setStarting] = useState(false);
  const [question, setQuestion] = useState("What are we still waiting on to move this claim forward?");
  const [results, setResults] = useState<EvidenceChunk[] | null>(null);
  const [searching, setSearching] = useState(false);
  const selection = useRef(selected);
  selection.current = selected;
  const latestJob = useRef(job);
  latestJob.current = job;
  const active = job?.status === "running";

  const refresh = useCallback(async () => {
    setError("");
    try {
      const data = await fetchClaims();
      setOverview(data);
      setJob(data.job);
      const selectedId = selection.current;
      if (selectedId) {
        const nextDetail = await fetchClaim(selectedId);
        if (selection.current === selectedId) setDetail(nextDetail);
      }
    } catch (reason) { setError(claimsError(reason)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    let disposed = false;
    setDetail(null);
    setResults(null);
    setFilter("");
    setScanNames([]);
    setTreeView({ expandedFiles: [], expandedChunks: [], focusId: "" });
    fetchClaim(selected).then(data => { if (!disposed) setDetail(data); })
      .catch(reason => { if (!disposed) setError(claimsError(reason)); });
    return () => { disposed = true; };
  }, [selected]);

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (disposed || inFlight) return;
      inFlight = true;
      clearTimeout(timer);
      let delay = 5000;
      try {
        const next = await fetchClaimRun();
        if (disposed) return;
        const previous = latestJob.current;
        setJob(next);
        setError(message => message.startsWith("Progress connection lost:") ? "" : message);
        delay = next?.status === "running" ? 1200 : 5000;
        const finished = previous?.status === "running" && next?.status !== "running";
        if (finished && next) {
          if (next.status === "failed") toast.error(next.message);
          else toast.success("Claim processing completed");
        }
        if (previous?.id !== next?.id || finished) {
          await refresh();
        } else if (previous?.stage !== next?.stage && next?.claim_id === selection.current) {
          const claimId = next.claim_id;
          const nextDetail = await fetchClaim(claimId);
          if (!disposed && selection.current === claimId) setDetail(nextDetail);
        }
      } catch (reason) {
        if (!disposed) {
          setError(`Progress connection lost: ${claimsError(reason)}. The server may still be processing. Reconnecting automatically.`);
        }
      } finally {
        inFlight = false;
        if (!disposed) timer = setTimeout(poll, delay);
      }
    };
    const onFocus = () => { void poll(); };
    const onVisibilityChange = () => { if (!document.hidden) void poll(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibilityChange);
    timer = setTimeout(poll, 500);
    return () => {
      disposed = true;
      clearTimeout(timer);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [refresh]);

  useEffect(() => {
    if (popup?.kind !== "file") return;
    let disposed = false;
    setFile(null);
    setFileError("");
    setFileView(popup.tab || "original");
    setFileLoading(true);
    fetchClaimFile(popup.claimId, popup.id)
      .then(data => { if (!disposed) setFile(data); })
      .catch(reason => { if (!disposed) setFileError(claimsError(reason)); })
      .finally(() => { if (!disposed) setFileLoading(false); });
    return () => { disposed = true; };
  }, [popup]);

  const start = async () => {
    if (popup?.kind !== "run") return;
    setStarting(true);
    setError("");
    try {
      setJob(await runClaims(popup.ids, indexData, popup.ids.length === 1 ? scanNames : []));
      setPopup(null);
    } catch (reason) { setError(claimsError(reason)); setPopup(null); }
    finally { setStarting(false); }
  };
  const search = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    const claimId = selected;
    setSearching(true);
    setResults(null);
    setError("");
    try {
      const matches = await searchClaim(claimId, question);
      if (selection.current === claimId) setResults(matches);
    } catch (reason) { setError(claimsError(reason)); }
    finally { setSearching(false); }
  };
  const chooseFile = (item: EvidenceFile) => {
    const fromTree = popup?.kind === "file" && popup.fromTree;
    if (selected) setPopup({ kind: "file", id: item.id, claimId: selected, fromTree });
  };
  const openChunk = (chunk: EvidenceChunk) => setPopup({ kind: "chunk", chunk,
    fromTree: popup?.kind === "file" && popup.fromTree });
  const files = detail?.files.filter(item => `${item.filename} ${item.source_type} ${item.source_files.join(" ")}`.toLowerCase().includes(filter.toLowerCase())) || [];
  const chunks = detail?.chunks.filter(item => `${item.filename} ${item.title} ${item.content} ${item.content_kind}`.toLowerCase().includes(filter.toLowerCase())) || [];
  const totalChunks = overview?.claims.reduce((sum, item) => sum + item.chunks, 0) || 0;
  const jobForClaim = job?.claim_id === selected;

  return <section className="ce-page" aria-label="Claims Explorer">
    <div className="ce-heading">
      <div><div className="ce-eyebrow"><SparkleRegular /> CLAIMS EXPLORER</div>
        <h1>Every file. One connected story.</h1>
        <p>Follow the evidence from the original folder to the moments that matter.</p></div>
      <div className="ce-actions">
        <Button appearance="primary" icon={<ChatRegular />} disabled={!overview?.claims.length}
          onClick={() => setPopup({ kind: "chat", claimId: selected || undefined })}>Chat with claims</Button>
        <Button appearance="subtle" icon={<ArrowClockwiseRegular />} onClick={() => void refresh()}>Refresh</Button>
        <Button appearance="primary" icon={<PlayRegular />} disabled={active || !overview?.claims.length}
          onClick={() => { setIndexData(false); setScanNames([]); setPopup({ kind: "run", ids: overview?.claims.map(item => item.claim_id) || [] }); }}>Process all folders</Button>
      </div>
    </div>
    {error && <div role="alert" className="ce-error">{error}</div>}
    {job && <div className={`ce-run-strip ${job.status === "failed" ? "ce-run-failed" : ""}`} role="status" aria-live="polite">
      {active ? <Spinner size="tiny" /> : job.status === "failed" ? <ErrorCircleRegular /> : <CheckmarkCircleRegular />}
      <strong>{job.status === "running" ? "Processing" : job.status === "failed" ? "Last run stopped" : "Last run complete"}</strong>
      <span>{shortName(job.claim_id)} / {stageInfo[job.stage].title}</span>
      <span className="ce-run-message">{job.message}</span>
    </div>}
    {loading && !overview ? <div className="ce-empty"><Spinner label="Opening the claim folders" /></div> : !selected ?
      <>
        <div className="ce-overview-bar"><span><FolderRegular /> {overview?.claims.length || 0} claim folders</span>
          <span><DocumentRegular /> {overview?.claims.reduce((sum, item) => sum + item.original_files, 0) || 0} original files</span>
          <span><DatabaseRegular /> {totalChunks} prepared chunks</span><span className="ce-muted">Real evidence · no simulated progress</span></div>
        <div className="ce-folder-grid">{overview?.claims.map((claim, index) =>
          <button className="ce-folder" key={claim.claim_id} onClick={() => { setView("files"); setSelected(claim.claim_id); }}>
            <div className="ce-folder-cover">
              {claim.cover_id ? <img src={claimFileUrl(claim.claim_id, claim.cover_id)} alt={`Evidence in ${shortName(claim.claim_id)}`} loading="lazy" /> : <FolderRegular />}
              <span className="ce-folder-number">{String(index + 1).padStart(2, "0")}</span>
              <span className="ce-cover-badge">{claim.stages.index ? "Upload receipt saved" : claim.stages.embed ? "Prepared" : "Ready to explore"}</span>
            </div>
            <div className="ce-folder-body"><div className="ce-card-top"><h2>{shortName(claim.claim_id)}</h2><ChevronRightRegular /></div>
              <p>{claim.original_files} originals · {claim.evidence_files} unique evidence files</p>
              <div className="ce-mini-track" aria-label="Saved processing stages">{stages.map(stage =>
                <span key={stage} className={claim.stages[stage] ? "is-done" : ""} title={`${stageInfo[stage].title}: ${claim.stages[stage] ? "saved" : "pending"}`} />)}</div>
              <div className="ce-card-bottom"><span>{claim.chunks ? `${claim.chunks} chunks to explore` : "Open to discover the evidence"}</span><span>Explore folder</span></div>
            </div>
          </button>)}</div>
        {!overview?.claims.length && !error && <div className="ce-empty">No claim folders were found in the configured data directory.</div>}
      </> :
      <>
        <div className="ce-claim-bar"><Button appearance="subtle" icon={<ArrowLeftRegular />} onClick={() => setSelected(null)}>All folders</Button>
          <h2>{shortName(selected)}</h2><span className="ce-muted">{detail?.original_files || 0} originals · {detail?.duplicate_occurrences || 0} duplicate occurrences linked</span>
          <Button icon={<FlowRegular />} disabled={!detail} onClick={() => setPopup({ kind: "tree" })}>Execution tree</Button>
          <Button appearance="primary" icon={<PlayRegular />} disabled={active || !detail}
            onClick={() => { setIndexData(false); setScanNames([]); setPopup({ kind: "run", ids: [selected] }); }}>Process this folder</Button></div>
        {!detail ? <div className="ce-empty"><Spinner label="Reading evidence relationships" /></div> : <>
          <div className="ce-timeline">{stages.map((stage, index) => {
            const running = active && jobForClaim && job?.stage === stage;
            return <button key={stage} className={`ce-stage ${detail.stages[stage] ? "is-done" : ""} ${running ? "is-running" : ""}`}
              onClick={() => setPopup({ kind: "stage", stage })}>
              <span className="ce-stage-mark">{running ? <Spinner size="tiny" /> : detail.stages[stage] ? <CheckmarkCircleRegular /> : index + 1}</span>
              <strong>{stageInfo[stage].title}</strong><small>{running ? "In progress" : detail.stages[stage] ? stage === "index" ? "Saved receipt" : "Available" : "Not yet saved"}</small>
            </button>;
          })}</div>
          {detail.stale_chunks > 0 && <div role="alert" className="ce-error">{detail.stale_chunks} saved chunks no longer match current inputs. Process this folder before relying on its index.</div>}
          <div className="ce-workspace-bar"><TabList selectedValue={view} onTabSelect={(_, data) => setView(String(data.value))}>
            <Tab value="files">Evidence files ({detail.files.length})</Tab>
            <Tab value="chunks">Chunks ({detail.chunks.length})</Tab>
            <Tab value="operations">System records</Tab>
            <Tab value="search">Ask this claim</Tab>
          </TabList>{view !== "search" && view !== "operations" && <Input aria-label="Filter evidence" contentBefore={<SearchRegular />} placeholder="Find a file, phrase or evidence kind"
            value={filter} onChange={(_, data) => setFilter(data.value)} />}</div>
          {view === "files" && <div className="ce-file-grid">{files.map(item =>
            <button className="ce-file" key={item.id} onClick={() => chooseFile(item)}>
              <div className={`ce-file-icon ce-type-${item.source_type}`}><FileIcon type={item.source_type} /></div>
              <div className="ce-file-info"><h3>{item.filename}</h3><p>{item.attachment_only ? "Email attachment" : kindLabel(item.source_type)} · {Math.ceil(item.bytes / 1024)} KB</p>
                <div className="ce-file-tags"><span>{item.analyzer_id.replace("prebuilt-", "")}</span>
                  {item.source_files.length > 1 && <span>{item.source_files.length} source links</span>}</div></div>
              <div className="ce-file-count"><strong>{item.chunks}</strong><small>chunks</small></div>
              <ChevronRightRegular />
            </button>)}</div>}
          {view === "chunks" && <><p className="ce-section-note">A quiet view of every evidence fragment. Open a card for its full content and source trail. Vectors are never expanded here.</p>
            <ChunkCards chunks={chunks} open={openChunk} />
            {!chunks.length && <div className="ce-empty">{detail.chunks.length ? "No chunks match your filter." : "This folder has no prepared chunks yet. Process the folder to create them."}</div>}</>}
          {view === "operations" && <ClaimOperationsPanel key={selected} claimId={selected} onOpenEvidence={reference => {
            const source = detail.files.find(item => item.source_files.includes(reference));
            if (source) chooseFile(source);
            else setError(`No local evidence file matches ${reference}.`);
          }} />}
          {view === "search" && <div className="ce-search-space">
            <div className="ce-search-intro"><SparkleRegular /><h2>A question, grounded in this folder.</h2><p>Keyword + vector retrieval, followed by semantic reranking. Source excerpts, not a generated answer.</p></div>
            <form className="ce-search-form" onSubmit={search}><Field label="Your claim question"><Input value={question} onChange={(_, data) => setQuestion(data.value)} /></Field>
              <Button type="submit" appearance="primary" icon={<SearchRegular />} disabled={searching || !question.trim()}>Search evidence</Button></form>
            {searching && <Spinner label="Finding and reranking claim evidence" />}
            {results && <><p className="ce-section-note">{results.length} results · filtered to {selected} · scores are ranking signals, not confidence</p><ChunkCards chunks={results} open={openChunk} />{!results.length && <div className="ce-empty">No matching evidence in this claim.</div>}</>}
          </div>}
        </>}
      </>}
    <div className="ce-footer">Synthetic demonstration evidence · Visual observations do not establish cause, timing, liability or coverage.</div>
    <Dialog open={popup !== null} onOpenChange={(_, data) => { if (!data.open && !starting) setPopup(null); }}>
      <DialogSurface className={`ce-dialog ${popup?.kind === "file" ? "ce-dialog-wide" : ""} ${popup?.kind === "tree" ? "cet-dialog" : ""} ${popup?.kind === "chat" ? "ca-dialog" : ""}`}><DialogBody>
        <DialogTitle action={<Button appearance="subtle" aria-label="Close detail" icon={<DismissRegular />} disabled={starting} onClick={() => setPopup(null)} />}>
          {popup?.kind === "file" ? file?.file.filename || "Evidence detail" : popup?.kind === "chunk" ? "Inside the chunk" : popup?.kind === "chat" ? "Chat with claims" : popup?.kind === "tree" ? `Execution tree · ${shortName(selected || "")}` : popup?.kind === "run" ? "Bring the evidence to life" : popup?.kind === "stage" ? stageInfo[popup.stage].title : ""}
        </DialogTitle>
        <DialogContent>
          {popup?.kind === "chat" && overview && <ClaimsAgentChat claims={overview.claims} initialClaim={popup.claimId} />}
          {(popup?.kind === "file" || popup?.kind === "chunk") && popup.fromTree &&
            <Button appearance="subtle" icon={<ArrowLeftRegular />} onClick={() => setPopup({ kind: "tree" })}>Back to execution tree</Button>}
          {popup?.kind === "tree" && detail && <ClaimsExecutionTree detail={detail} job={job}
            view={treeView} onChange={setTreeView}
            onOpenFile={(id, tab) => setPopup({ kind: "file", id, claimId: detail.claim_id, tab, fromTree: true })}
            onOpenChunk={chunk => setPopup({ kind: "chunk", chunk, fromTree: true })} />}
          {popup?.kind === "run" && <div className="ce-run-confirm"><p>Process {popup.ids.length === 1 ? shortName(popup.ids[0]) : `${popup.ids.length} claim folders`} using the configured Foundry account. Saved CU results and unchanged vectors are reused. New analysis and embeddings incur Azure usage.</p>
            <div className="ce-run-flow">Files <ChevronRightRegular /> CU <ChevronRightRegular /> Chunks <ChevronRightRegular /> Vectors</div>
            <Checkbox label={`Also create/check ${overview?.index_name} and synchronize these claims to Search`} checked={indexData} onChange={(_, data) => setIndexData(data.checked === true)} />
            <p className="ce-muted">Other claims and agent-managed indexes are not deleted. Without this option, processing stops at the prepared records.</p>
            {popup.ids.length === 1 && detail && <details><summary>Advanced: image-format document scans ({scanNames.length} overrides)</summary><p className="ce-muted">Photos and diagrams are already included with imageSearch; leave these unchecked. Override only a scanned document that needs document/OCR analysis.</p>
              {detail.files.filter(item => item.source_type === "image").map(item => <Checkbox key={item.id} label={`Treat ${item.filename} as a scanned document (OCR)`} checked={scanNames.includes(item.filename)}
                onChange={(_, data) => setScanNames(previous => data.checked ? [...previous, item.filename] : previous.filter(name => name !== item.filename))} />)}</details>}
          </div>}
          {popup?.kind === "stage" && <div className="ce-stage-detail"><p>{stageInfo[popup.stage].description}</p>
            <Badge appearance="tint">{detail?.stages[popup.stage] ? "Saved evidence available" : "Not yet saved"}</Badge>
            <p>Files: {detail?.files.length || 0} · Chunks: {detail?.chunks.length || 0}</p>
            {jobForClaim && job?.events.filter(event => event.stage === popup.stage).slice(-8).map((event, index) => <p key={index} className="ce-event">{event.message}</p>)}</div>}
          {popup?.kind === "chunk" && <div className="ce-chunk-detail">
            <div className="ce-detail-meta"><Badge appearance="tint">{kindLabel(popup.chunk.content_kind)}</Badge><span>{popup.chunk.filename} · chunk {popup.chunk.chunk_id}</span>
              {popup.chunk.vector_dimensions && <span>{popup.chunk.vector_dimensions} vector dimensions</span>}</div>
            <h2>{popup.chunk.title}</h2><div className="ce-markdown"><Markdown text={popup.chunk.content} /></div>
            <div className="ce-source-trail"><strong>Source trail</strong>{popup.chunk.source_files.map(source => <p key={source}>{source}</p>)}
              <p>{popup.chunk.analyzer_id}{popup.chunk.analyzer_api_version ? ` · ${popup.chunk.analyzer_api_version}` : ""}</p>
              {popup.chunk.figure_id && <p>Figure {popup.chunk.figure_id} · {popup.chunk.source_region}</p>}
              {!!popup.chunk.parent_emails.length && <p>{popup.chunk.parent_emails.length} parent email relationship(s)</p>}
              <Button onClick={() => setPopup({ kind: "file", id: popup.chunk.document_hash, claimId: popup.chunk.claim_id, fromTree: popup.fromTree })} icon={<DocumentRegular />}>Open source evidence</Button></div>
          </div>}
          {popup?.kind === "file" && <>{fileLoading ? <Spinner label="Opening the file" /> : fileError ? <div role="alert" className="ce-error">{fileError}</div> : file && <>
            <div className="ce-detail-meta"><Badge appearance="tint">{file.file.source_type}</Badge><span>{file.file.chunks} chunks</span><span>{file.file.analyzer_id}</span></div>
            <ol className="ce-file-progress" aria-label="File processing stages">{[
              { label: "Gathered", done: true }, { label: "Extracted", done: file.file.extracted },
              { label: "Chunked", done: file.file.chunks > 0 }, { label: "Embedded", done: file.file.embedded },
              { label: "Upload receipt", done: file.file.uploaded },
            ].map(step => <li key={step.label} className={step.done ? "is-done" : ""}>
              {step.done && <CheckmarkCircleRegular />}{step.label}<small>{step.done ? "Saved" : "Pending"}</small></li>)}</ol>
            <TabList selectedValue={fileView} onTabSelect={(_, data) => setFileView(String(data.value))}><Tab value="original">Original</Tab><Tab value="extraction">Native extraction</Tab><Tab value="chunks">Chunks</Tab><Tab value="sources">Source trail</Tab></TabList>
            <div className="ce-file-view">
              {fileView === "original" && (file.file.source_type === "email" ? <div className="ce-markdown"><Markdown text={file.file.text} /></div> :
                file.file.filename.toLowerCase().endsWith(".pdf") ? <SourcePdfViewer url={claimFileUrl(popup.claimId, popup.id)} /> :
                  <img className="ce-original-image" src={claimFileUrl(popup.claimId, popup.id)} alt={file.file.filename} />)}
              {fileView === "extraction" && <div className="ce-markdown">{file.native_text || file.file.text ? <Markdown text={file.native_text || file.file.text} /> : <p>No saved extraction for this file yet.</p>}</div>}
              {fileView === "chunks" && <><ChunkCards chunks={file.chunks} open={openChunk} />{!file.chunks.length && <p>No saved chunks for this file yet.</p>}</>}
              {fileView === "sources" && <div className="ce-source-trail"><strong>All original occurrences</strong>{file.file.source_files.map(source => <p key={source}>{source}</p>)}
                <p>Exact duplicate bytes are analyzed once, while every source link is retained.</p>
                <strong>Related emails</strong>{detail?.files.filter(item => file.file.parent_emails.includes(item.id)).map(item =>
                  <Button key={item.id} onClick={() => chooseFile(item)} icon={<MailRegular />}>{item.filename}</Button>)}
                <strong>Attachments / child evidence</strong>{detail?.files.filter(item => item.parent_emails.includes(file.file.id)).map(item =>
                  <Button key={item.id} onClick={() => chooseFile(item)} icon={<FileIcon type={item.source_type} />}>{item.filename}</Button>)}</div>}
            </div>
          </>}</>}
        </DialogContent>
        {popup?.kind === "run" && <DialogActions><Button onClick={() => setPopup(null)} disabled={starting}>Not now</Button>
          <Button appearance="primary" icon={starting ? <Spinner size="tiny" /> : <PlayRegular />} disabled={starting} onClick={() => void start()}>Start processing</Button></DialogActions>}
      </DialogBody></DialogSurface>
    </Dialog>
  </section>;
};

export default ClaimsPage;
