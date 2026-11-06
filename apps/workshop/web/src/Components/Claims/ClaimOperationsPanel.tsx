import React, { useEffect, useState } from "react";
import { Badge, Button, Spinner, Tab, TabList } from "@fluentui/react-components";
import { ArrowClockwiseRegular, DocumentRegular } from "@fluentui/react-icons";
import { claimsError } from "../../services/claimsService";
import {
  fetchStructuredClaim, OperationalSnapshot, structuredClaimUrl, usd,
} from "../../services/claimOperationsService";

interface Props {
  claimId: string;
  onOpenEvidence: (reference: string) => void;
}

const readable = (value: string) => value.replace(/_/g, " ");
const recordedTime = (value: string) => new Date(value).toLocaleString(undefined, {
  timeZone: "UTC", timeZoneName: "short", year: "numeric", month: "short", day: "numeric",
  hour: "2-digit", minute: "2-digit",
});

export default function ClaimOperationsPanel({ claimId, onOpenEvidence }: Props) {
  const [snapshot, setSnapshot] = useState<OperationalSnapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [view, setView] = useState("activities");

  useEffect(() => {
    let disposed = false;
    setSnapshot(null);
    setError("");
    setLoading(true);
    fetchStructuredClaim(claimId)
      .then(data => { if (!disposed) setSnapshot(data); })
      .catch(reason => { if (!disposed) setError(claimsError(reason)); })
      .finally(() => { if (!disposed) setLoading(false); });
    return () => { disposed = true; };
  }, [claimId, revision]);

  if (loading) return <div className="ce-empty"><Spinner label="Reading the local structured-data tool" /></div>;
  if (error || !snapshot) return <div role="alert" className="ce-error">
    {error || "No structured snapshot was returned."}
    <Button onClick={() => setRevision(previous => previous + 1)}>Retry</Button>
  </div>;
  const data = snapshot.data;
  const financials = data.financials;
  const blocking = data.activities.filter(activity => activity.currently_blocking).length;
  const sources = (refs: string[]) => <div className="co-source-links">{refs.map(reference =>
    <Button size="small" appearance="subtle" icon={<DocumentRegular />} key={reference}
      onClick={() => onOpenEvidence(reference)}>{reference.split("/").pop()}</Button>)}</div>;

  return <section className="co-panel" aria-label="Structured claims system records">
    <div className="co-header"><div><div className="ce-eyebrow">STRUCTURED DATA TOOL</div>
      <h2>{data.claim_number} <Badge appearance="tint">Simulated Genie</Badge></h2>
      <p className="ce-muted">{data.insured_name} · {readable(data.line_of_business)} · {data.loss_date}</p></div>
      <div className="ce-actions"><Button appearance="subtle" icon={<ArrowClockwiseRegular />}
        onClick={() => setRevision(previous => previous + 1)}>Refresh records</Button>
        <a href={structuredClaimUrl(claimId)} target="_blank" rel="noreferrer">Open tool response</a></div>
    </div>
    <div className="co-provenance"><strong>Synthetic operational snapshot · {recordedTime(snapshot.metadata.as_of)}</strong>
      <span>{snapshot.metadata.caveat} This data is read from the local API, not the document Search index.</span></div>
    <div className="co-assignment"><Badge appearance="tint">{data.status}</Badge><span>{readable(data.phase)}</span>
      <span>{data.assigned_adjuster} / {data.assigned_team}</span><span>Coverage: {readable(data.coverage_decision)}</span></div>
    <div className="co-metrics">
      <div><small>Outstanding reserve</small><strong>{usd(financials.outstanding_reserve_total)}</strong><span>Loss + expense; not an estimate or settlement</span></div>
      <div><small>Actually paid</small><strong>{usd(financials.paid_total)}</strong><span>Posted payments only; excludes pending and voided</span></div>
      <div><small>Open blockers</small><strong>{blocking}</strong><span>From the activity records at the snapshot date</span></div>
    </div>
    <div className="co-policy"><strong>Specimen policy {data.policy.policy_number}</strong>
      <span>{data.policy.effective_from} to {data.policy.effective_to}</span>
      <span>Limit {usd(data.policy.specimen_limit)} · deductible {usd(data.policy.specimen_deductible)}</span>
      <p className="ce-muted">Schedule values do not determine coverage or an automatic net payment. Approved settlement amount: {financials.approved_settlement_amount === null ? "none recorded (not zero)" : usd(financials.approved_settlement_amount)}.</p>
      {sources([data.policy.source_ref])}</div>
    <TabList selectedValue={view} onTabSelect={(_, tab) => setView(String(tab.value))}>
      <Tab value="activities">Activities ({data.activities.length})</Tab>
      <Tab value="ledger">Financial ledger ({financials.payments.length})</Tab>
      <Tab value="notes">Log notes ({data.log_notes.length})</Tab>
    </TabList>
    {view === "activities" && <div className="co-record-list">{data.activities.map(activity =>
      <article className="co-record" key={activity.activity_id}>
        <div className="ce-card-top"><span className="ce-eyebrow">{activity.activity_id}</span><div className="co-badges">
          <Badge appearance="tint" color={activity.status === "completed" ? "success" : "informative"}>{readable(activity.status)}</Badge>
          {activity.currently_blocking && <Badge appearance="tint" color="warning">Blocking</Badge>}
          {activity.overdue_as_of_snapshot && <Badge appearance="tint" color="danger">Overdue at snapshot</Badge>}</div></div>
        <h3>{activity.title}</h3><p className="ce-muted">{activity.owner_team} · {activity.priority} priority · due {activity.due_date}
          {activity.completed_at ? ` · completed ${recordedTime(activity.completed_at)}` : ""}</p>{sources(activity.source_refs)}
      </article>)}</div>}
    {view === "ledger" && <>
      <div className="co-financial-detail"><span>Paid indemnity: {usd(financials.paid_indemnity_total)}</span>
        <span>Paid expenses: {usd(financials.paid_expense_total)}</span>
        <span>Pending requests: {usd(financials.pending_payment_total)}</span>
        <span>Voided requests: {usd(financials.voided_request_total)}</span>
        <span>Incurred (reserve + paid): {usd(financials.incurred_total)}</span></div>
      {financials.payments.length ? <div className="co-table-scroll"><table className="co-table"><thead><tr>
        <th>Payment</th><th>Kind / status</th><th>Amount</th><th>Payee and purpose</th><th>Posted</th>
      </tr></thead><tbody>{financials.payments.map(payment => <tr key={payment.payment_id}>
        <td>{payment.payment_id}</td><td>{payment.kind}<br /><Badge appearance="tint">{payment.status}</Badge></td>
        <td>{usd(payment.amount)}</td><td><strong>{payment.payee}</strong><p>{payment.purpose}</p></td>
        <td>{payment.posted_at ? recordedTime(payment.posted_at) : "Not posted"}</td>
      </tr>)}</tbody></table></div> : <p className="ce-section-note">No payment requests or posted payments are recorded for this claim.</p>}
      <details className="co-definitions"><summary>Financial definitions</summary>{Object.entries(financials.definitions).map(([name, text]) =>
        <p key={name}><strong>{readable(name)}:</strong> {text}</p>)}</details>
    </>}
    {view === "notes" && <div className="co-record-list">{[...data.log_notes].reverse().map(note =>
      <article className="co-record" key={note.note_id}><div className="ce-card-top"><span className="ce-eyebrow">{note.note_id}</span>
        <Badge appearance="tint">{readable(note.category)}</Badge></div><p className="ce-muted">{recordedTime(note.recorded_at)} · {note.author_role}</p>
        <p className="co-note-text">{note.text}</p>{note.activity_id && <p className="ce-muted">Related activity: {note.activity_id}</p>}{sources(note.source_refs)}
      </article>)}</div>}
  </section>;
}
