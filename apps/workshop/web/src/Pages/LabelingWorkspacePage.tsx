import React, { useEffect, useRef, useState } from "react";
import {
  Badge,
  Body1,
  Body1Strong,
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Dropdown,
  Field,
  Input,
  Option,
  Spinner,
  Tab,
  TabList,
  Text,
  Title3,
  Tooltip,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import {
  AddRegular,
  ArrowDownloadRegular,
  ArrowUploadRegular,
  CheckmarkRegular,
  DatabaseRegular,
  DocumentEditRegular,
  PlayRegular,
  SaveRegular,
  SparkleRegular,
} from "@fluentui/react-icons";
import { toast } from "react-toastify";

import SourcePdfViewer from "../Components/Sec/SourcePdfViewer";
import {
  EditableLabel,
  LabelFieldDefinition,
  LabelingDocument,
  LabelingDocumentRole,
  LabelingEvaluationReport,
  LabelingProject,
  LabelingProjectSummary,
  LabelingWorkspaceStatus,
  autoLabelDocument,
  buildLearnedAnalyzer,
  createBaseAnalyzer,
  createLabelingProject,
  exportLabelingProject,
  fetchLabelingDocument,
  fetchLabelingProject,
  fetchLabelingProjects,
  fetchLabelingWorkspaceStatus,
  labelingDocumentUrl,
  prepareLabelingDocument,
  saveLabelingDocument,
  scoreLabelingProject,
  uploadLabelingDocuments,
} from "../services/labeledAnalyzerService";

type WorkspaceView = "label" | "compare";
type OcrSelection = { offset: number; length: number; text: string };

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    height: "calc(100vh - 56px)",
    minWidth: "1080px",
    overflow: "hidden",
    backgroundColor: tokens.colorNeutralBackground1,
  },
  toolbar: {
    display: "flex",
    alignItems: "center",
    columnGap: "8px",
    minHeight: "62px",
    padding: "8px 14px",
    boxSizing: "border-box",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  title: { minWidth: "205px", display: "flex", flexDirection: "column" },
  spacer: { flex: 1 },
  error: {
    padding: "8px 14px",
    color: tokens.colorPaletteRedForeground1,
    backgroundColor: tokens.colorPaletteRedBackground1,
    borderBottom: `1px solid ${tokens.colorPaletteRedBorder1}`,
  },
  viewBar: {
    display: "flex",
    alignItems: "center",
    minHeight: "43px",
    padding: "0 14px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  workspace: {
    flex: 1,
    minHeight: 0,
    display: "grid",
    gridTemplateColumns: "245px minmax(380px, 0.9fr) minmax(455px, 1.1fr)",
  },
  queue: {
    minHeight: 0,
    overflow: "auto",
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  queueHeader: {
    display: "flex",
    alignItems: "center",
    padding: "10px 12px 6px",
  },
  queueGroup: { paddingBottom: "8px" },
  groupLabel: {
    display: "flex",
    alignItems: "center",
    padding: "8px 12px 4px",
    color: tokens.colorNeutralForeground3,
  },
  documentButton: {
    width: "100%",
    minHeight: "54px",
    display: "grid",
    gridTemplateColumns: "1fr auto",
    alignItems: "center",
    columnGap: "8px",
    padding: "7px 12px",
    border: 0,
    borderLeft: "3px solid transparent",
    textAlign: "left",
    color: tokens.colorNeutralForeground1,
    backgroundColor: "transparent",
    cursor: "pointer",
    "&:hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  documentSelected: {
    borderLeftColor: tokens.colorBrandStroke1,
    backgroundColor: tokens.colorNeutralBackground1Selected,
  },
  documentName: {
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  documentMeta: { display: "flex", alignItems: "center", columnGap: "6px" },
  center: {
    minWidth: 0,
    minHeight: 0,
    display: "grid",
    gridTemplateRows: "minmax(470px, 3fr) minmax(170px, 1fr)",
    padding: "10px",
    rowGap: "8px",
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    overflow: "hidden",
  },
  ocrPanel: {
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  ocrHeader: {
    display: "flex",
    alignItems: "center",
    minHeight: "34px",
    padding: "4px 2px",
  },
  ocrText: {
    flex: 1,
    minHeight: 0,
    margin: 0,
    padding: "9px",
    overflow: "auto",
    whiteSpace: "pre-wrap",
    fontFamily: "Cascadia Code, Consolas, monospace",
    fontSize: "11px",
    lineHeight: "17px",
    userSelect: "text",
    backgroundColor: tokens.colorNeutralBackground3,
    ...shorthands.borderRadius("4px"),
  },
  editor: { minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column" },
  editorHeader: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    minHeight: "58px",
    padding: "8px 12px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  editorBody: { flex: 1, minHeight: 0, overflow: "auto" },
  fieldRow: {
    display: "grid",
    gridTemplateColumns: "minmax(150px, 0.75fr) minmax(190px, 1.25fr) 34px",
    alignItems: "center",
    gap: "8px",
    minHeight: "58px",
    padding: "7px 12px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  fieldName: { minWidth: 0, display: "flex", flexDirection: "column", rowGap: "2px" },
  fieldInput: { width: "100%" },
  editorFooter: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    minHeight: "54px",
    padding: "8px 12px",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  empty: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    textAlign: "center",
    color: tokens.colorNeutralForeground3,
    ...shorthands.padding("28px"),
  },
  compare: { flex: 1, minHeight: 0, overflow: "auto" },
  metrics: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(220px, 1fr))",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  metric: { padding: "14px 18px", borderRight: `1px solid ${tokens.colorNeutralStroke2}` },
  metricValue: { fontSize: "25px", lineHeight: "31px", fontWeight: 600 },
  compareBody: { padding: "12px 16px 24px" },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    tableLayout: "fixed",
    fontSize: "12px",
    "& th": {
      position: "sticky",
      top: 0,
      padding: "8px",
      textAlign: "left",
      backgroundColor: tokens.colorNeutralBackground3,
      borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    },
    "& td": {
      padding: "8px",
      verticalAlign: "top",
      overflowWrap: "anywhere",
      borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    },
  },
  correct: { boxShadow: `inset 3px 0 0 ${tokens.colorPaletteGreenBorderActive}` },
  incorrect: { boxShadow: `inset 3px 0 0 ${tokens.colorPaletteRedBorderActive}` },
  dialogFields: { display: "flex", flexDirection: "column", gap: "14px", minWidth: "420px" },
});

const fieldTitle = (value: string) => value.replace(/([a-z])([A-Z])/g, "$1 $2");
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const errorMessage = (reason: unknown) => {
  const response = (reason as { response?: { data?: { detail?: string } } })?.response;
  return response?.data?.detail || (reason instanceof Error ? reason.message : String(reason));
};

const LabelingWorkspacePage: React.FC = () => {
  const styles = useStyles();
  const [capabilities, setCapabilities] = useState<LabelingWorkspaceStatus | null>(null);
  const [projects, setProjects] = useState<LabelingProjectSummary[]>([]);
  const [projectId, setProjectId] = useState("");
  const [project, setProject] = useState<LabelingProject | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState("");
  const [currentDocument, setCurrentDocument] = useState<LabelingDocument | null>(null);
  const [draft, setDraft] = useState<Record<string, EditableLabel>>({});
  const [ocrSelection, setOcrSelection] = useState<OcrSelection | null>(null);
  const [view, setView] = useState<WorkspaceView>("label");
  const [report, setReport] = useState<LabelingEvaluationReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("Property claim forms");
  const [newAnalyzerId, setNewAnalyzerId] = useState("propertyClaimFormsV1");
  const [autoAnalyzerId, setAutoAnalyzerId] = useState("");
  const trainingInput = useRef<HTMLInputElement | null>(null);
  const evaluationInput = useRef<HTMLInputElement | null>(null);
  const ocrRef = useRef<HTMLPreElement | null>(null);
  const isDirty = Boolean(
    currentDocument && JSON.stringify(draft) !== JSON.stringify(currentDocument.labels)
  );

  useEffect(() => {
    let active = true;
    Promise.all([fetchLabelingWorkspaceStatus(), fetchLabelingProjects()])
      .then(([nextCapabilities, nextProjects]) => {
        if (!active) return;
        setCapabilities(nextCapabilities);
        setProjects(nextProjects);
        if (nextProjects.length) setProjectId(nextProjects[0].project_id);
        else setCreateOpen(true);
      })
      .catch((reason) => active && setError(errorMessage(reason)));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (!projectId) {
      setProject(null);
      return () => { active = false; };
    }
    fetchLabelingProject(projectId)
      .then((nextProject) => {
        if (!active) return;
        setProject(nextProject);
        setReport(nextProject.evaluation || null);
        setAutoAnalyzerId(nextProject.base_analyzer_id);
        setSelectedDocumentId((current) =>
          nextProject.documents.some((item) => item.document_id === current)
            ? current
            : nextProject.documents[0]?.document_id || ""
        );
      })
      .catch((reason) => active && setError(errorMessage(reason)));
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    if (!projectId || !selectedDocumentId) {
      setCurrentDocument(null);
      setDraft({});
      return () => { active = false; };
    }
    setCurrentDocument(null);
    setDraft({});
    fetchLabelingDocument(projectId, selectedDocumentId)
      .then((nextDocument) => {
        if (!active) return;
        setCurrentDocument(nextDocument);
        setDraft(structuredClone(nextDocument.labels));
        setOcrSelection(null);
      })
      .catch((reason) => active && setError(errorMessage(reason)));
    return () => { active = false; };
  }, [projectId, selectedDocumentId]);

  useEffect(() => {
    if (!isDirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [isDirty]);

  const reloadProject = async () => {
    if (!projectId) return null;
    const [nextProject, nextProjects] = await Promise.all([
      fetchLabelingProject(projectId),
      fetchLabelingProjects(),
    ]);
    setProject(nextProject);
    setProjects(nextProjects);
    return nextProject;
  };

  const run = async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    try {
      await action();
    } catch (reason) {
      const message = errorMessage(reason);
      setError(message);
      toast.error(message);
    } finally {
      setBusy(null);
    }
  };

  const createProject = () => run("create-project", async () => {
    const created = await createLabelingProject(newName, newAnalyzerId);
    const nextProjects = await fetchLabelingProjects();
    setProjects(nextProjects);
    setProjectId(created.project_id);
    setCreateOpen(false);
    toast.success("Forms project created");
  });

  const confirmDiscard = () =>
    !isDirty || window.confirm("Discard unsaved label edits?");

  const selectProject = (nextProjectId: string) => {
    if (nextProjectId && nextProjectId !== projectId && confirmDiscard()) {
      setProjectId(nextProjectId);
    }
  };

  const selectDocument = (documentId: string) => {
    if (documentId !== selectedDocumentId && confirmDiscard()) {
      setSelectedDocumentId(documentId);
    }
  };

  const upload = (files: FileList | null, role: LabelingDocumentRole) => {
    if (!projectId || !files?.length) return;
    void run(`upload-${role}`, async () => {
      const created = await uploadLabelingDocuments(projectId, Array.from(files), role);
      await reloadProject();
      if (created[0]) setSelectedDocumentId(created[0].document_id);
      toast.success(`${created.length} ${role} document${created.length === 1 ? "" : "s"} added`);
    });
  };

  const setDocument = (nextDocument: LabelingDocument) => {
    setCurrentDocument(nextDocument);
    setDraft(structuredClone(nextDocument.labels));
    setOcrSelection(null);
  };

  const prepareManual = () => {
    if (!projectId || !currentDocument) return;
    void run("prepare", async () => {
      setDocument(await prepareLabelingDocument(projectId, currentDocument.document_id));
      await reloadProject();
      toast.success("Document ready for manual labeling");
    });
  };

  const autoLabel = () => {
    if (!projectId || !currentDocument) return;
    void run("autolabel", async () => {
      setDocument(await autoLabelDocument(projectId, currentDocument.document_id, autoAnalyzerId));
      await reloadProject();
      toast.success("Auto-labeling complete");
    });
  };

  const save = (reviewed: boolean) => {
    if (!projectId || !currentDocument) return;
    void run(reviewed ? "review" : "save", async () => {
      const payload = Object.fromEntries(
        Object.entries(draft).map(([name, label]) => [
          name,
          { value: label.value, source: label.source, spans: label.spans },
        ])
      );
      setDocument(
        await saveLabelingDocument(projectId, currentDocument.document_id, payload, reviewed)
      );
      const nextProject = await reloadProject();
      if (reviewed && nextProject) {
        const currentIndex = nextProject.documents.findIndex(
          (item) => item.document_id === currentDocument.document_id
        );
        const ordered = [
          ...nextProject.documents.slice(currentIndex + 1),
          ...nextProject.documents.slice(0, currentIndex),
        ];
        const next = ordered.find((item) => !item.reviewed);
        if (next) setSelectedDocumentId(next.document_id);
      }
      toast.success(reviewed ? "Reviewed" : "Draft saved");
    });
  };

  const captureOcrSelection = () => {
    const selection = window.getSelection();
    const container = ocrRef.current;
    if (!selection || selection.rangeCount === 0 || !container) return;
    const range = selection.getRangeAt(0);
    if (!container.contains(range.commonAncestorContainer)) return;
    const rawText = selection.toString();
    const text = rawText.trim();
    if (!text) return;
    const prefix = window.document.createRange();
    prefix.selectNodeContents(container);
    prefix.setEnd(range.startContainer, range.startOffset);
    const leadingWhitespace = rawText.length - rawText.trimStart().length;
    setOcrSelection({
      offset: prefix.toString().length + leadingWhitespace,
      length: text.length,
      text,
    });
  };

  const applyOcrSelection = (fieldName: string) => {
    if (!ocrSelection) return;
    setDraft((current) => ({
      ...current,
      [fieldName]: {
        ...current[fieldName],
        value: ocrSelection.text,
        source: null,
        spans: [{ offset: ocrSelection.offset, length: ocrSelection.length }],
      },
    }));
  };

  const updateValue = (fieldName: string, value: string) => {
    setDraft((current) => ({
      ...current,
      [fieldName]: { ...current[fieldName], value },
    }));
  };

  const selectedSummary = project?.documents.find(
    (item) => item.document_id === selectedDocumentId
  );
  const reviewedTraining = project?.documents.filter(
    (item) => item.role === "training" && item.reviewed
  ).length || 0;
  const reviewedEvaluation = project?.documents.filter(
    (item) => item.role === "evaluation" && item.reviewed
  ).length || 0;

  return (
    <div className={styles.root}>
      <div className={styles.toolbar}>
        <div className={styles.title}>
          <Title3>Analyzer Workshop</Title3>
          <Caption1>Forms · GPT-5.2 · local review</Caption1>
        </div>
        <Dropdown
          aria-label="Labeling project"
          value={project?.name || "Select project"}
          selectedOptions={projectId ? [projectId] : []}
          onOptionSelect={(_, data) => selectProject(String(data.optionValue || ""))}
          style={{ minWidth: 210 }}
        >
          {projects.map((item) => (
            <Option key={item.project_id} value={item.project_id} text={item.name}>
              {item.name}
            </Option>
          ))}
        </Dropdown>
        <Tooltip content="Create another forms project" relationship="label">
          <Button
            appearance="subtle"
            icon={<AddRegular />}
            onClick={() => confirmDiscard() && setCreateOpen(true)}
          />
        </Tooltip>
        <div className={styles.spacer} />
        <Button
          icon={<DatabaseRegular />}
          disabled={!project || !capabilities?.content_understanding_configured || !!busy}
          onClick={() => void run("base", async () => {
            await createBaseAnalyzer(projectId);
            await reloadProject();
            toast.success("Zero-shot analyzer ready");
          })}
        >
          Create analyzer
        </Button>
        <Button
          icon={<ArrowDownloadRegular />}
          disabled={!project || !project.summary.reviewed_count || !!busy}
          onClick={() => void run("export", async () => exportLabelingProject(projectId))}
        >
          Export labels
        </Button>
        <Tooltip
          content="Uses host-managed temporary Blob staging, deleted when preview training completes"
          relationship="description"
        >
          <Button
            icon={<SparkleRegular />}
            disabled={
              !project ||
              !reviewedTraining ||
              project.analyzers.base.status !== "ready" ||
              !capabilities?.content_understanding_configured ||
              !capabilities?.host_storage_configured ||
              !!busy
            }
            onClick={() => void run("build", async () => {
              await buildLearnedAnalyzer(projectId);
              await reloadProject();
              toast.success("Learned analyzer ready");
            })}
          >
            Build learned
          </Button>
        </Tooltip>
        <Button
          appearance="primary"
          icon={<PlayRegular />}
          disabled={
            !project ||
            !reviewedEvaluation ||
            project.analyzers.base.status !== "ready" ||
            project.analyzers.trained.status !== "ready" ||
            !!busy
          }
          onClick={() => void run("score", async () => {
            const nextReport = await scoreLabelingProject(projectId);
            setReport(nextReport);
            setView("compare");
            await reloadProject();
          })}
        >
          Score
        </Button>
        {busy && <Spinner size="tiny" />}
      </div>

      <div className={styles.viewBar}>
        <TabList selectedValue={view} onTabSelect={(_, data) => setView(data.value as WorkspaceView)}>
          <Tab value="label">Label documents</Tab>
          <Tab value="compare">Compare analyzers</Tab>
        </TabList>
        <div className={styles.spacer} />
        <Badge appearance="outline" color="informative">Local labels</Badge>
        <Badge
          appearance="outline"
          color={capabilities?.host_storage_configured ? "success" : "warning"}
        >
          {capabilities?.host_storage_configured ? "Temporary staging ready" : "Build staging unavailable"}
        </Badge>
        <Badge appearance="outline">{capabilities?.api_version || "Loading API"}</Badge>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {!project ? (
        <div className={styles.empty}>
          <Body1Strong>No forms project selected</Body1Strong>
          <Button appearance="primary" icon={<AddRegular />} onClick={() => setCreateOpen(true)}>
            Create forms project
          </Button>
        </div>
      ) : view === "label" ? (
        <div className={styles.workspace}>
          <DocumentQueue
            project={project}
            selectedId={selectedDocumentId}
            onSelect={selectDocument}
            onAddTraining={() => confirmDiscard() && trainingInput.current?.click()}
            onAddEvaluation={() => confirmDiscard() && evaluationInput.current?.click()}
            styles={styles}
          />
          <input
            ref={trainingInput}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            hidden
            onChange={(event) => {
              upload(event.target.files, "training");
              event.target.value = "";
            }}
          />
          <input
            ref={evaluationInput}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            hidden
            onChange={(event) => {
              upload(event.target.files, "evaluation");
              event.target.value = "";
            }}
          />
          <div className={styles.center}>
            {currentDocument ? (
              <>
                <SourcePdfViewer
                  url={labelingDocumentUrl(projectId, currentDocument.document_id)}
                />
                <div className={styles.ocrPanel}>
                  <div className={styles.ocrHeader}>
                    <Body1Strong>OCR text</Body1Strong>
                    <div className={styles.spacer} />
                    <Caption1>
                      {ocrSelection ? `Selected: ${ocrSelection.text}` : "Select text to ground a field"}
                    </Caption1>
                  </div>
                  <pre ref={ocrRef} className={styles.ocrText} onMouseUp={captureOcrSelection}>
                    {currentDocument.markdown || "Prepare or auto-label this document to load OCR text."}
                  </pre>
                </div>
              </>
            ) : (
              <div className={styles.empty}><Body1>Select a document</Body1></div>
            )}
          </div>
          <div className={styles.editor}>
            {currentDocument && selectedSummary ? (
              <>
                <div className={styles.editorHeader}>
                  <div style={{ minWidth: 0 }}>
                    <Body1Strong>{currentDocument.file_name}</Body1Strong>
                    <div>
                      <Caption1>
                        {selectedSummary.role}
                        {selectedSummary.role === "evaluation" ? " · independent truth" : ""}
                        {` · ${selectedSummary.status.replaceAll("_", " ")}`}
                      </Caption1>
                    </div>
                  </div>
                  <div className={styles.spacer} />
                  <Input
                    aria-label="Auto-label analyzer ID"
                    size="small"
                    value={autoAnalyzerId}
                    onChange={(_, data) => setAutoAnalyzerId(data.value)}
                    style={{ width: 180 }}
                  />
                  <Tooltip content="Prepare OCR and label manually" relationship="label">
                    <Button
                      icon={<DocumentEditRegular />}
                      disabled={
                        !capabilities?.content_understanding_configured ||
                        selectedSummary.status !== "uploaded" ||
                        !!busy
                      }
                      onClick={prepareManual}
                    />
                  </Tooltip>
                  <Button
                    icon={<SparkleRegular />}
                    disabled={
                      selectedSummary.role === "evaluation" ||
                      selectedSummary.status !== "uploaded" ||
                      !capabilities?.content_understanding_configured ||
                      !autoAnalyzerId ||
                      !!busy
                    }
                    onClick={autoLabel}
                  >
                    Auto label
                  </Button>
                </div>
                <div className={styles.editorBody}>
                  {Object.entries(project.field_schema.fields).map(([fieldName, definition]) => (
                    <LabelRow
                      key={fieldName}
                      fieldName={fieldName}
                      definition={definition}
                      label={draft[fieldName]}
                      selectionReady={Boolean(ocrSelection)}
                      onChange={(value) => updateValue(fieldName, value)}
                      onUseSelection={() => applyOcrSelection(fieldName)}
                      styles={styles}
                    />
                  ))}
                </div>
                <div className={styles.editorFooter}>
                  <Caption1>{selectedSummary.labeled_fields} / {selectedSummary.total_fields} labeled</Caption1>
                  <div className={styles.spacer} />
                  <Button icon={<SaveRegular />} disabled={!!busy} onClick={() => save(false)}>
                    Save draft
                  </Button>
                  <Button
                    appearance="primary"
                    icon={<CheckmarkRegular />}
                    disabled={!!busy || !currentDocument.markdown}
                    onClick={() => save(true)}
                  >
                    Reviewed and next
                  </Button>
                </div>
              </>
            ) : (
              <div className={styles.empty}><Body1>Select a document to label</Body1></div>
            )}
          </div>
        </div>
      ) : (
        <Comparison report={report} project={project} styles={styles} />
      )}

      <Dialog open={createOpen} onOpenChange={(_, data) => setCreateOpen(data.open)}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>New forms project</DialogTitle>
            <DialogContent className={styles.dialogFields}>
              <Field label="Project name">
                <Input value={newName} onChange={(_, data) => setNewName(data.value)} />
              </Field>
              <Field label="Analyzer ID">
                <Input value={newAnalyzerId} onChange={(_, data) => setNewAnalyzerId(data.value)} />
              </Field>
              <Caption1>Preset: Property claim form · GPT-5.2</Caption1>
            </DialogContent>
            <DialogActions>
              <Button appearance="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button>
              <Button appearance="primary" disabled={busy === "create-project"} onClick={createProject}>
                Create project
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
};

const DocumentQueue: React.FC<{
  project: LabelingProject;
  selectedId: string;
  onSelect: (documentId: string) => void;
  onAddTraining: () => void;
  onAddEvaluation: () => void;
  styles: ReturnType<typeof useStyles>;
}> = ({ project, selectedId, onSelect, onAddTraining, onAddEvaluation, styles }) => (
  <aside className={styles.queue}>
    <div className={styles.queueHeader}>
      <Body1Strong>Documents</Body1Strong>
      <div className={styles.spacer} />
      <Caption1>{project.summary.reviewed_count} / {project.summary.document_count}</Caption1>
    </div>
    <QueueGroup
      role="training"
      documents={project.documents.filter((item) => item.role === "training")}
      selectedId={selectedId}
      onSelect={onSelect}
      onAdd={onAddTraining}
      styles={styles}
    />
    <QueueGroup
      role="evaluation"
      documents={project.documents.filter((item) => item.role === "evaluation")}
      selectedId={selectedId}
      onSelect={onSelect}
      onAdd={onAddEvaluation}
      styles={styles}
    />
  </aside>
);

const QueueGroup: React.FC<{
  role: LabelingDocumentRole;
  documents: LabelingProject["documents"];
  selectedId: string;
  onSelect: (documentId: string) => void;
  onAdd: () => void;
  styles: ReturnType<typeof useStyles>;
}> = ({ role, documents, selectedId, onSelect, onAdd, styles }) => (
  <div className={styles.queueGroup}>
    <div className={styles.groupLabel}>
      <Caption1>{role === "training" ? "TRAINING" : "EVALUATION"}</Caption1>
      <div className={styles.spacer} />
      <Tooltip content={`Add ${role} PDFs`} relationship="label">
        <Button size="small" appearance="subtle" icon={<ArrowUploadRegular />} onClick={onAdd} />
      </Tooltip>
    </div>
    {documents.map((item) => (
      <button
        key={item.document_id}
        type="button"
        className={`${styles.documentButton} ${item.document_id === selectedId ? styles.documentSelected : ""}`}
        onClick={() => onSelect(item.document_id)}
      >
        <span className={styles.documentName}>
          <Text size={200} weight="semibold">{item.file_name}</Text>
          <span className={styles.documentMeta}>
            <Caption1>{item.labeled_fields}/{item.total_fields} fields</Caption1>
          </span>
        </span>
        <Badge
          size="small"
          appearance="outline"
          color={item.reviewed ? "success" : item.status === "uploaded" ? "informative" : "warning"}
        >
          {item.reviewed ? "Reviewed" : item.status === "uploaded" ? "New" : "Draft"}
        </Badge>
      </button>
    ))}
  </div>
);

const LabelRow: React.FC<{
  fieldName: string;
  definition: LabelFieldDefinition;
  label?: EditableLabel;
  selectionReady: boolean;
  onChange: (value: string) => void;
  onUseSelection: () => void;
  styles: ReturnType<typeof useStyles>;
}> = ({ fieldName, definition, label, selectionReady, onChange, onUseSelection, styles }) => {
  const inputType = definition.type === "date" || definition.type === "time" || definition.type === "number"
    ? definition.type
    : "text";
  const page = label?.source?.match(/^D\((\d+)/)?.[1];
  return (
    <div className={styles.fieldRow}>
      <div className={styles.fieldName}>
        <Tooltip content={definition.description} relationship="description">
          <Text size={200} weight="semibold">{fieldTitle(fieldName)}</Text>
        </Tooltip>
        <Caption1>
          {label?.confidence == null ? definition.type : `${(label.confidence * 100).toFixed(0)}% · p.${page || "?"}`}
        </Caption1>
      </div>
      <Input
        className={styles.fieldInput}
        size="small"
        type={inputType}
        value={label?.value == null ? "" : String(label.value)}
        onChange={(_, data) => onChange(data.value)}
      />
      <Tooltip content="Use selected OCR text" relationship="label">
        <Button
          appearance="subtle"
          size="small"
          icon={<AddRegular />}
          disabled={!selectionReady}
          onClick={onUseSelection}
        />
      </Tooltip>
    </div>
  );
};

const Comparison: React.FC<{
  report: LabelingEvaluationReport | null;
  project: LabelingProject;
  styles: ReturnType<typeof useStyles>;
}> = ({ report, project, styles }) => {
  const [selected, setSelected] = useState("");
  const entries = report ? Object.entries(report.documents) : [];
  const selectedId = entries.some(([id]) => id === selected) ? selected : entries[0]?.[0] || "";
  const document = report?.documents[selectedId];
  if (!report) {
    return (
      <div className={styles.empty}>
        <Body1Strong>No score report yet</Body1Strong>
        <Body1>{project.summary.evaluation_count} evaluation documents · {project.analyzers.trained.status === "ready" ? "learned analyzer ready" : "learned analyzer not built"}</Body1>
      </div>
    );
  }
  return (
    <div className={styles.compare}>
      <div className={styles.metrics}>
        <Metric label="Zero-shot accuracy" value={percent(report.summary.zero_shot_accuracy)} styles={styles} />
        <Metric label="Learned accuracy" value={percent(report.summary.labeled_accuracy)} styles={styles} />
        <Metric
          label="Accuracy delta"
          value={`${report.summary.accuracy_delta_points >= 0 ? "+" : ""}${report.summary.accuracy_delta_points.toFixed(1)} pp`}
          styles={styles}
        />
      </div>
      <div className={styles.compareBody}>
        <Dropdown
          aria-label="Scored document"
          value={document?.file_name || "Select evaluation document"}
          selectedOptions={selectedId ? [selectedId] : []}
          onOptionSelect={(_, data) => setSelected(String(data.optionValue || ""))}
          style={{ minWidth: 260, marginBottom: 12 }}
        >
          {entries.map(([id, item]) => (
            <Option key={id} value={id} text={item.file_name}>{item.file_name}</Option>
          ))}
        </Dropdown>
        {document && (
          <table className={styles.table}>
            <thead>
              <tr><th>Field</th><th>Reviewed value</th><th>Zero-shot</th><th>Learned</th></tr>
            </thead>
            <tbody>
              {document.fields.map((field) => (
                <tr key={field.field_name}>
                  <td><Body1Strong>{fieldTitle(field.field_name)}</Body1Strong></td>
                  <td>{String(field.expected)}</td>
                  <ScoreCell value={field.zero_shot} styles={styles} />
                  <ScoreCell value={field.labeled} styles={styles} />
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

const Metric: React.FC<{ label: string; value: string; styles: ReturnType<typeof useStyles> }> = ({ label, value, styles }) => (
  <div className={styles.metric}>
    <Caption1>{label}</Caption1>
    <div className={styles.metricValue}>{value}</div>
  </div>
);

const ScoreCell: React.FC<{
  value: { actual: unknown; confidence: number | null; correct: boolean };
  styles: ReturnType<typeof useStyles>;
}> = ({ value, styles }) => (
  <td className={value.correct ? styles.correct : styles.incorrect}>
    <Body1>{value.actual == null ? "Missing" : String(value.actual)}</Body1>
    <div><Caption1>{value.confidence == null ? "No confidence" : `${(value.confidence * 100).toFixed(1)}%`}</Caption1></div>
  </td>
);

export default LabelingWorkspacePage;