import React, { useEffect, useRef, useState } from "react";
import {
  Badge, Button, Field, Spinner, Textarea,
} from "@fluentui/react-components";
import {
  AddRegular, ArrowClockwiseRegular, ArrowUpRegular, ChatRegular,
  CheckmarkCircleRegular, CodeRegular, DatabaseRegular, DismissRegular, DocumentRegular, SparkleRegular,
} from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AgentCitation, AgentConversation, AgentTurn, ClaimsAgentStatus, CloudTraceEvidence,
  createAgentConversation, fetchAgentConversation, fetchClaimsAgentStatus,
  listAgentConversations, registerClaimsAgent, sendAgentMessage, verifyAgentTrace,
} from "../../services/claimsAgentService";
import { ClaimSummary, claimsError } from "../../services/claimsService";
import "../../Styles/ClaimsAgentChat.css";

interface Props {
  claims: ClaimSummary[];
  initialClaim?: string;
}

const starters = [
  "What are we still waiting on to move this claim forward?",
  "How much have we actually paid, and what is still reserved?",
  "Compare the repair proposals with the latest claim notes. What needs follow-up?",
];

export default function ClaimsAgentChat({ claims, initialClaim }: Props) {
  const [claimId, setClaimId] = useState(initialClaim || claims[0]?.claim_id || "");
  const [status, setStatus] = useState<ClaimsAgentStatus | null>(null);
  const [history, setHistory] = useState<AgentConversation[]>([]);
  const [conversation, setConversation] = useState<AgentConversation | null>(null);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [traceTurn, setTraceTurn] = useState<AgentTurn | null>(null);
  const [source, setSource] = useState<AgentCitation | null>(null);
  const [cloudTrace, setCloudTrace] = useState<CloudTraceEvidence | null>(null);
  const [checking, setChecking] = useState(false);
  const scope = useRef(claimId);
  scope.current = claimId;
  const mounted = useRef(true);
  const end = useRef<HTMLDivElement>(null);
  const pending = sending || conversation?.turns.some(turn => turn.status === "running");
  const conversationId = conversation?.id;

  useEffect(() => {
    mounted.current = true;
    fetchClaimsAgentStatus().then(data => { if (mounted.current) setStatus(data); })
      .catch(reason => { if (mounted.current) setError(claimsError(reason)); });
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let disposed = false;
    setConversation(null);
    setTraceTurn(null);
    setSource(null);
    setCloudTrace(null);
    setHistory([]);
    setError("");
    if (claimId) {
      listAgentConversations(claimId).then(data => { if (!disposed) setHistory(data); })
        .catch(reason => { if (!disposed) setError(claimsError(reason)); });
    }
    return () => { disposed = true; };
  }, [claimId]);

  useEffect(() => {
    end.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [conversation?.turns.length, sending]);

  useEffect(() => {
    if (!pending || !conversationId) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const data = await fetchAgentConversation(conversationId);
        if (disposed) return;
        setConversation(data);
        if (data.turns.some(turn => turn.status === "running")) timer = setTimeout(poll, 1500);
      } catch (reason) { if (!disposed) setError(claimsError(reason)); }
    };
    timer = setTimeout(poll, 1500);
    return () => { disposed = true; clearTimeout(timer); };
  }, [pending, conversationId]);

  const register = async () => {
    setPreparing(true);
    setError("");
    try { setStatus(await registerClaimsAgent()); }
    catch (reason) { setError(claimsError(reason)); }
    finally { setPreparing(false); }
  };
  const newConversation = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await createAgentConversation(claimId);
      if (scope.current !== claimId) return;
      setConversation(data);
      setHistory(previous => [data, ...previous]);
      setTraceTurn(null); setSource(null); setCloudTrace(null);
    } catch (reason) { setError(claimsError(reason)); }
    finally { setLoading(false); }
  };
  const chooseConversation = async (id: string) => {
    const selectedClaim = claimId;
    setLoading(true); setError("");
    try {
      const data = await fetchAgentConversation(id);
      if (scope.current === selectedClaim) {
        setConversation(data);
        setTraceTurn(null); setSource(null); setCloudTrace(null);
      }
    } catch (reason) { setError(claimsError(reason)); }
    finally { setLoading(false); }
  };
  const send = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!conversation || pending || !question.trim()) return;
    const id = conversation.id;
    const text = question.trim();
    setSending(true); setQuestion(""); setError("");
    try {
      const data = await sendAgentMessage(id, text);
      if (!mounted.current) return;
      setConversation(data);
      setHistory(await listAgentConversations(data.claim_id));
      const latest = data.turns[data.turns.length - 1];
      setTraceTurn(latest); setSource(null); setCloudTrace(null);
    } catch (reason) {
      if (!mounted.current) return;
      setError(`${claimsError(reason)} The server may have retained this turn; reopen the conversation before retrying.`);
      try { setConversation(await fetchAgentConversation(id)); }
      catch (reloadError) { setError(`${claimsError(reason)} Conversation refresh also failed: ${claimsError(reloadError)}`); }
    } finally { if (mounted.current) setSending(false); }
  };
  const verify = async () => {
    if (!conversation || !traceTurn) return;
    setChecking(true); setError("");
    try { setCloudTrace(await verifyAgentTrace(conversation.id, traceTurn.id)); }
    catch (reason) { setError(`Cloud trace verification failed: ${claimsError(reason)}`); }
    finally { setChecking(false); }
  };
  const openTrace = (turn: AgentTurn) => { setTraceTurn(turn); setSource(null); setCloudTrace(null); };
  const foundryUrl = status?.project_portal_url;
  const sourceCard = (citation: AgentCitation) => <button key={citation.id} className="ca-source-card"
    onClick={() => { setSource(citation); setTraceTurn(null); }}>
    {citation.kind === "document" ? <DocumentRegular /> : <DatabaseRegular />}
    <span><strong>[{citation.id}] {citation.title}</strong><small>{citation.kind === "structured" ? "Simulated Genie · operational snapshot" : "AI Search · retrieved evidence"}</small></span>
  </button>;

  return <section className="ca-workspace" aria-label="Local claims agent chat">
    <aside className="ca-sidebar">
      <div className="ce-eyebrow"><ChatRegular /> CLAIMS ASSISTANT</div>
      <h2>One claim.<br />Two evidence sources.</h2>
      <label className="ca-claim-picker">Conversation scope<select aria-label="Chat claim scope" value={claimId} disabled={pending || loading}
        onChange={event => setClaimId(event.target.value)}>{claims.map(claim =>
        <option value={claim.claim_id} key={claim.claim_id}>{claim.claim_id.replace("claim-", "Claim ")}</option>)}</select></label>
      <Button appearance="primary" icon={<AddRegular />} disabled={!status?.registered || preparing || pending || loading}
        onClick={() => void newConversation()}>New conversation</Button>
      <div className="ca-history-label">CONVERSATIONS</div>
      <nav className="ca-history" aria-label="Claim conversation history">{history.map(item =>
        <button key={item.id} className={conversation?.id === item.id ? "is-selected" : ""} disabled={pending || loading}
          onClick={() => void chooseConversation(item.id)}><ChatRegular /><span>{item.title}<small>{new Date(item.updated_at).toLocaleString()}</small></span></button>)}
        {!history.length && <p className="ce-muted">No conversations for this claim yet.</p>}</nav>
      <div className="ca-tool-list"><strong>Read-only tools</strong><span><DocumentRegular /> Semantic hybrid Search</span><span><DatabaseRegular /> Local structured-data API</span></div>
      <div className="ca-runtime"><Badge appearance="tint">Runs locally</Badge><p>Models and tracing use your Foundry account. This is not a Foundry-hosted runtime.</p></div>
    </aside>
    <div className="ca-main">
      <div className="ca-chat-header"><div><strong>{status?.name || "Claims assistant"}</strong>
        <small>{status?.model || "Loading configuration"}{status?.version ? ` · registered v${status.version}` : " · not registered"}</small></div>
        <Badge appearance="tint" color={status?.registered ? "success" : "warning"}>{status?.registered ? "Registered for tracing" : "Registration needed"}</Badge></div>
      {error && <div role="alert" className="ce-error ca-error">{error}</div>}
      {!status?.registered && <div className="ca-registration"><SparkleRegular /><div><strong>Connect this local agent to Foundry observability</strong>
        <p>Register a metadata-only external-agent version in the selected project. It does not deploy compute. Chat later invokes models/tools and exports synthetic conversation traces.</p></div>
        <Button appearance="primary" disabled={!status || preparing} onClick={() => void register()}>{preparing ? "Registering…" : "Register agent"}</Button></div>}
      <div className="ca-messages" role="log" aria-label="Claim conversation">
        {!conversation && <div className="ca-welcome"><div className="ca-welcome-icon"><SparkleRegular /></div><h2>What would you like to understand?</h2>
          <p>Combine the claim's original evidence with its operational records.<br />Start a conversation, then ask a question in your own words.</p>
          <div className="ca-starters">{starters.map(text => <button key={text} onClick={() => setQuestion(text)}>{text}<ArrowUpRegular /></button>)}</div>
          <p className="ce-muted">Synthetic demonstration only. No payments, record changes or automated claims decisions.</p></div>}
        {loading && <Spinner label="Opening conversation" />}
        {conversation && !conversation.turns.length && <div className="ca-welcome"><SparkleRegular /><h2>Ready for {claimId.replace("claim-", "Claim ")}.</h2><p>Ask about progress, payments, missing evidence or conflicting repair scopes.</p>
          <div className="ca-starters">{starters.map(text => <button key={text} onClick={() => setQuestion(text)}>{text}<ArrowUpRegular /></button>)}</div></div>}
        {conversation?.turns.map(turn => <article className="ca-turn" key={turn.id}>
          <div className="ca-user-message">{turn.question}</div>
          <div className="ca-assistant-message"><div className="ca-message-label"><SparkleRegular /> CLAIMS ASSISTANT</div>
            {turn.status === "complete" && turn.answer ? <div className="ce-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml
              components={{ img: () => null, a: ({ children }) => <span>{children}</span> }}>{turn.answer}</ReactMarkdown></div>
              : turn.status === "failed" ? <div role="alert" className="ce-error"><strong>This turn did not complete.</strong><p>{turn.error}</p><small>No failed invocation is displayed as an assistant answer.</small></div>
                : <Spinner size="small" label="Consulting claim tools…" />}
            {turn.status === "complete" && <div className="ca-sources"><small>RETRIEVED SOURCES</small>{turn.citations.map(sourceCard)}</div>}
            <div className="ca-turn-footer"><Button size="small" appearance="subtle" icon={<CodeRegular />} onClick={() => openTrace(turn)}>Show trace</Button>
              <span>{turn.steps.filter(step => step.kind === "tool").length} tool calls · {turn.elapsed_ms === null ? "Timing not reported" : `${(turn.elapsed_ms / 1000).toFixed(1)}s`}</span></div>
          </div>
        </article>)}
        {sending && !conversation?.turns.some(turn => turn.status === "running") && <Spinner size="small" label="Agent is working with the selected claim…" />}
        <div ref={end} />
      </div>
      <form className="ca-composer" onSubmit={event => void send(event)}>
        <Field label={`Message ${claimId.replace("claim-", "Claim ")}`}>
          <Textarea resize="vertical" value={question} onChange={(_, data) => setQuestion(data.value)} placeholder="Ask a claims question…" maxLength={16000}
            disabled={!!pending || loading} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} /></Field>
        <Button type="submit" appearance="primary" icon={<ArrowUpRegular />} disabled={!conversation || !!pending || !question.trim() || loading}>Send</Button>
        <small>Enter to send · Shift+Enter for a new line. Responses are AI-generated; review the cited sources.</small>
      </form>
    </div>
    {(traceTurn || source) && <aside className="ca-trace" aria-label={source ? "Citation details" : "Agent execution trace"}>
      <div className="ca-trace-heading"><strong>{source ? "Source evidence" : "Actual execution trace"}</strong><Button size="small" appearance="subtle" aria-label="Close trace panel" icon={<DismissRegular />} onClick={() => { setTraceTurn(null); setSource(null); }} /></div>
      {source && <><Badge appearance="tint">{source.kind === "document" ? "AI Search evidence" : "Synthetic system record"}</Badge>
        <h3>[{source.id}] {source.title}</h3>{source.as_of && <p className="ce-muted">Snapshot: {source.as_of}</p>}
        <div className="ca-source-excerpt">{source.excerpt}</div>
        {source.source_files?.map(file => <p className="ca-code" key={file}>{file}</p>)}
        <p className="ce-muted">Claim: {source.claim_id}. Original documents and structured records remain distinct evidence sources.</p></>}
      {traceTurn && <>
        <Badge appearance="tint" color={traceTurn.status === "failed" ? "danger" : "brand"}>{traceTurn.status}</Badge>
        <p className="ca-trace-question">{traceTurn.question}</p>
        <p className="ce-muted">Agent: {conversation?.agent_name} v{conversation?.agent_version}</p>
        <p className="ca-code">Trace ID: {traceTurn.trace_id || "Not recorded"}</p>
        <p className="ce-muted">{traceTurn.telemetry_status}</p>
        {foundryUrl && <a className="ca-foundry-link" href={foundryUrl} target="_blank" rel="noreferrer">Open Foundry project</a>}
        <Button size="small" icon={<ArrowClockwiseRegular />} disabled={checking || !traceTurn.trace_id} onClick={() => void verify()}>{checking ? "Checking cloud…" : "Verify cloud trace"}</Button>
        {cloudTrace && <div className="ca-cloud-evidence" role="status"><CheckmarkCircleRegular /><strong>{cloudTrace.verified ? `${cloudTrace.span_count} cloud spans observed` : "Ingestion not yet observed"}</strong><p>{cloudTrace.message}</p>
          <details><summary>Exact KQL query and observed rows</summary><pre>{cloudTrace.query}</pre><pre>{JSON.stringify(cloudTrace.spans, null, 2)}</pre></details></div>}
        <div className="ca-step-list">{traceTurn.steps.map((step, index) => <details className={`ca-step ${step.status === "failed" ? "ca-step-failed" : ""}`} key={step.id}>
          <summary><span className="ca-step-number">{index + 1}</span><span><strong>{step.name}</strong><small>{step.kind} · {step.status} · {(step.elapsed_ms / 1000).toFixed(2)}s</small></span></summary>
          {step.input_tokens !== undefined && <p className="ce-muted">Input: {step.input_tokens ?? "not reported"} · Output: {step.output_tokens ?? "not reported"} tokens</p>}
          {step.arguments && <><h4>Actual arguments</h4><pre>{JSON.stringify(step.arguments, null, 2)}</pre></>}
          {step.result !== undefined && <><h4>Actual result</h4><pre>{JSON.stringify(step.result, null, 2)}</pre></>}
          {step.error && <div role="alert" className="ce-error">{step.error}</div>}
        </details>)}</div>
        <p className="ce-muted">Execution evidence, not hidden model reasoning. A local trace or flushed exporter is not proof of cloud ingestion; use Verify cloud trace.</p>
      </>}
    </aside>}
  </section>;
}
