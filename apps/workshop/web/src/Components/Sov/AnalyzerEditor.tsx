import React, { useEffect, useState } from "react";
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
  Badge,
  Body1,
  Button,
  Dropdown,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Option,
  Switch,
  Textarea,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { AddRegular, DeleteRegular } from "@fluentui/react-icons";

interface SchemaField {
  type: string;
  method?: string;
  description?: string;
  enum?: string[];
  items?: SchemaField;
  properties?: Record<string, SchemaField>;
}

interface AnalyzerTemplate {
  description?: string;
  baseAnalyzerId: string;
  config?: Record<string, unknown>;
  fieldSchema?: {
    name?: string;
    description?: string;
    fields?: Record<string, SchemaField>;
  };
  [k: string]: unknown;
}

const TYPES = ["string", "number", "integer", "boolean", "date", "array", "object"];
const METHODS = ["extract", "generate", "classify"];

const useStyles = makeStyles({
  root: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    columnGap: "12px",
    height: "70vh",
    minHeight: "500px",
  },
  pane: {
    overflow: "auto",
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke2),
    ...shorthands.borderRadius("4px"),
    ...shorthands.padding("12px"),
  },
  paneHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "8px",
  },
  fieldRow: {
    display: "flex",
    flexDirection: "column",
    rowGap: "6px",
    ...shorthands.padding("8px"),
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke3),
    ...shorthands.borderRadius("4px"),
    marginBottom: "8px",
  },
  twoCol: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    columnGap: "8px",
  },
  nestedHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "8px",
    marginBottom: "4px",
  },
  nested: {
    ...shorthands.borderLeft("2px", "solid", tokens.colorBrandStroke2),
    paddingLeft: "10px",
    marginTop: "4px",
  },
});

export interface AnalyzerEditorProps {
  initialJson: string;
  onChange: (json: string, parsed: AnalyzerTemplate | null) => void;
}

export default function AnalyzerEditor({ initialJson, onChange }: AnalyzerEditorProps) {
  const styles = useStyles();
  const [template, setTemplate] = useState<AnalyzerTemplate | null>(() => safeParse(initialJson));
  const [rawJson, setRawJson] = useState(initialJson);
  const [jsonEditMode, setJsonEditMode] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    if (!template) return;
    const next = JSON.stringify(template, null, 2);
    setRawJson(next);
    onChange(next, template);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template]);

  const onJsonChange = (v: string) => {
    setRawJson(v);
    try {
      const parsed = JSON.parse(v) as AnalyzerTemplate;
      setJsonError(null);
      setTemplate(parsed);
      onChange(v, parsed);
    } catch (e: any) {
      setJsonError(e.message);
      onChange(v, null);
    }
  };

  // path resolves to a SchemaField under fieldSchema.fields. e.g. ["Locations","items","properties","Street"]
  const updateAtPath = (path: string[], mutator: (f: SchemaField) => SchemaField) => {
    setTemplate((t) => {
      if (!t) return t;
      const cloned = JSON.parse(JSON.stringify(t)) as AnalyzerTemplate;
      const root: any = cloned.fieldSchema?.fields;
      if (!root) return t;
      let parent: any = root;
      for (let i = 0; i < path.length - 1; i++) parent = parent[path[i]];
      const last = path[path.length - 1];
      parent[last] = mutator(parent[last]);
      return cloned;
    });
  };

  const renameAtPath = (containerPath: string[], oldName: string, newName: string) => {
    if (!newName || newName === oldName) return;
    setTemplate((t) => {
      if (!t) return t;
      const cloned = JSON.parse(JSON.stringify(t)) as AnalyzerTemplate;
      const container = getContainer(cloned, containerPath);
      if (!container || container[newName]) return t;
      const next: Record<string, SchemaField> = {};
      for (const k of Object.keys(container)) {
        next[k === oldName ? newName : k] = container[k];
      }
      replaceContainer(cloned, containerPath, next);
      return cloned;
    });
  };

  const removeAtPath = (containerPath: string[], name: string) => {
    setTemplate((t) => {
      if (!t) return t;
      const cloned = JSON.parse(JSON.stringify(t)) as AnalyzerTemplate;
      const container = getContainer(cloned, containerPath);
      if (!container) return t;
      delete container[name];
      return cloned;
    });
  };

  const addAtPath = (containerPath: string[]) => {
    setTemplate((t) => {
      if (!t) return t;
      const cloned = JSON.parse(JSON.stringify(t)) as AnalyzerTemplate;
      const container = getContainer(cloned, containerPath) ?? {};
      const base = "NewField";
      let name = base;
      let i = 1;
      while (container[name]) name = `${base}${i++}`;
      container[name] = { type: "string", method: "extract", description: "" };
      replaceContainer(cloned, containerPath, container);
      return cloned;
    });
  };

  const fields = template?.fieldSchema?.fields ?? {};
  const fieldNames = Object.keys(fields);

  return (
    <div className={styles.root}>
      <div className={styles.pane}>
        <div className={styles.paneHeader}>
          <Body1>Schema editor</Body1>
          <Button icon={<AddRegular />} size="small" onClick={() => addAtPath([])}>
            Add field
          </Button>
        </div>

        <div className={styles.fieldRow}>
          <Field label="Analyzer description" size="small">
            <Textarea
              value={(template?.description as string) ?? ""}
              onChange={(_, d) =>
                setTemplate((t) => (t ? { ...t, description: d.value } : t))
              }
              resize="vertical"
              rows={2}
            />
          </Field>
          <div className={styles.twoCol}>
            <Field label="baseAnalyzerId" size="small">
              <Input
                value={template?.baseAnalyzerId ?? ""}
                onChange={(_, d) =>
                  setTemplate((t) => (t ? { ...t, baseAnalyzerId: d.value } : t))
                }
              />
            </Field>
            <Field label="Schema name" size="small">
              <Input
                value={template?.fieldSchema?.name ?? ""}
                onChange={(_, d) =>
                  setTemplate((t) =>
                    t
                      ? {
                          ...t,
                          fieldSchema: { ...(t.fieldSchema ?? {}), name: d.value },
                        }
                      : t
                  )
                }
              />
            </Field>
          </div>
        </div>

        <FieldList
          containerPath={[]}
          names={fieldNames}
          getField={(n) => fields[n]}
          onUpdate={updateAtPath}
          onRename={renameAtPath}
          onRemove={removeAtPath}
          onAdd={addAtPath}
        />
      </div>

      <div className={styles.pane}>
        <div className={styles.paneHeader}>
          <Body1>JSON</Body1>
          <Switch
            label={jsonEditMode ? "Editable" : "Read-only"}
            checked={jsonEditMode}
            onChange={(_, d) => setJsonEditMode(d.checked)}
          />
        </div>
        {jsonError && (
          <MessageBar intent="error" style={{ marginBottom: 8 }}>
            <MessageBarBody>Invalid JSON: {jsonError}</MessageBarBody>
          </MessageBar>
        )}
        <Textarea
          value={rawJson}
          onChange={(_, d) => onJsonChange(d.value)}
          disabled={!jsonEditMode}
          resize="vertical"
          textarea={{ style: { fontFamily: "Consolas, monospace", fontSize: "12px" } }}
          style={{ width: "100%" }}
          rows={28}
        />
      </div>
    </div>
  );
}

interface FieldListProps {
  containerPath: string[];
  names: string[];
  getField: (name: string) => SchemaField;
  onUpdate: (fieldPath: string[], mutator: (f: SchemaField) => SchemaField) => void;
  onRename: (containerPath: string[], oldName: string, newName: string) => void;
  onRemove: (containerPath: string[], name: string) => void;
  onAdd: (containerPath: string[]) => void;
}

function FieldList({ containerPath, names, getField, onUpdate, onRename, onRemove, onAdd }: FieldListProps) {
  const styles = useStyles();
  return (
    <Accordion multiple collapsible>
      {names.map((name) => {
        const f = getField(name);
        const fieldPath = [...containerPath, name];
        return (
          <AccordionItem key={name} value={fieldPath.join("/")}>
            <AccordionHeader>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <strong>{name}</strong>
                <Badge size="small" appearance="outline">{f.type}</Badge>
                {f.method && <Badge size="small" appearance="tint">{f.method}</Badge>}
                {childCount(f) > 0 && (
                  <Badge size="small" appearance="ghost">{childCount(f)} child fields</Badge>
                )}
              </span>
            </AccordionHeader>
            <AccordionPanel>
              <div className={styles.fieldRow}>
                <div className={styles.twoCol}>
                  <Field label="Field name" size="small">
                    <Input
                      defaultValue={name}
                      onBlur={(e) =>
                        onRename(containerPath, name, (e.target as HTMLInputElement).value.trim())
                      }
                    />
                  </Field>
                  <Field label="Type" size="small">
                    <Dropdown
                      value={f.type ?? "string"}
                      selectedOptions={[f.type ?? "string"]}
                      onOptionSelect={(_, d) =>
                        d.optionValue && onUpdate(fieldPath, (cur) => coerceType(cur, d.optionValue!))
                      }
                    >
                      {TYPES.map((t) => (
                        <Option key={t} value={t}>{t}</Option>
                      ))}
                    </Dropdown>
                  </Field>
                </div>
                <Field label="Method" size="small">
                  <Dropdown
                    value={f.method ?? ""}
                    selectedOptions={f.method ? [f.method] : []}
                    onOptionSelect={(_, d) =>
                      d.optionValue && onUpdate(fieldPath, (cur) => ({ ...cur, method: d.optionValue }))
                    }
                  >
                    {METHODS.map((m) => (
                      <Option key={m} value={m}>{m}</Option>
                    ))}
                  </Dropdown>
                </Field>
                <Field label="Description (prompt)" size="small">
                  <Textarea
                    value={f.description ?? ""}
                    onChange={(_, d) =>
                      onUpdate(fieldPath, (cur) => ({ ...cur, description: d.value }))
                    }
                    resize="vertical"
                    rows={3}
                  />
                </Field>
                {f.type === "string" && (
                  <Field label="Enum (one per line, leave empty for free text)" size="small">
                    <Textarea
                      value={(f.enum ?? []).join("\n")}
                      onChange={(_, d) =>
                        onUpdate(fieldPath, (cur) => ({
                          ...cur,
                          enum: d.value.split("\n").map((s) => s.trim()).filter(Boolean),
                        }))
                      }
                      rows={3}
                    />
                  </Field>
                )}

                {f.type === "array" && (
                  <NestedSection
                    label="Item fields"
                    containerPath={[...fieldPath, "items", "properties"]}
                    container={f.items?.properties ?? {}}
                    onUpdate={onUpdate}
                    onRename={onRename}
                    onRemove={onRemove}
                    onAdd={onAdd}
                  />
                )}
                {f.type === "object" && (
                  <NestedSection
                    label="Properties"
                    containerPath={[...fieldPath, "properties"]}
                    container={f.properties ?? {}}
                    onUpdate={onUpdate}
                    onRename={onRename}
                    onRemove={onRemove}
                    onAdd={onAdd}
                  />
                )}

                <Button
                  icon={<DeleteRegular />}
                  size="small"
                  appearance="subtle"
                  onClick={() => onRemove(containerPath, name)}
                >
                  Remove field
                </Button>
              </div>
            </AccordionPanel>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}

interface NestedSectionProps {
  label: string;
  containerPath: string[];
  container: Record<string, SchemaField>;
  onUpdate: FieldListProps["onUpdate"];
  onRename: FieldListProps["onRename"];
  onRemove: FieldListProps["onRemove"];
  onAdd: FieldListProps["onAdd"];
}

function NestedSection(props: NestedSectionProps) {
  const styles = useStyles();
  const names = Object.keys(props.container);
  return (
    <div className={styles.nested}>
      <div className={styles.nestedHeader}>
        <Body1>{props.label} ({names.length})</Body1>
        <Button icon={<AddRegular />} size="small" onClick={() => props.onAdd(props.containerPath)}>
          Add child
        </Button>
      </div>
      <FieldList
        containerPath={props.containerPath}
        names={names}
        getField={(n) => props.container[n]}
        onUpdate={props.onUpdate}
        onRename={props.onRename}
        onRemove={props.onRemove}
        onAdd={props.onAdd}
      />
    </div>
  );
}

// ── helpers ────────────────────────────────────────────────────────────────
function childCount(f: SchemaField): number {
  if (f.type === "array") return Object.keys(f.items?.properties ?? {}).length;
  if (f.type === "object") return Object.keys(f.properties ?? {}).length;
  return 0;
}

function coerceType(cur: SchemaField, newType: string): SchemaField {
  const next: SchemaField = { ...cur, type: newType };
  if (newType === "array") {
    next.items = next.items ?? { type: "object", properties: {} };
    if (next.items.type === "object" && !next.items.properties) {
      next.items.properties = {};
    }
    delete next.properties;
  } else if (newType === "object") {
    next.properties = next.properties ?? {};
    delete next.items;
  } else {
    delete next.items;
    delete next.properties;
  }
  return next;
}

// containerPath resolves to a Record<string, SchemaField>. Empty = top-level
// fieldSchema.fields. e.g. ["Locations","items","properties"].
function getContainer(t: AnalyzerTemplate, path: string[]): Record<string, SchemaField> | null {
  let node: any = t.fieldSchema?.fields ?? {};
  for (const seg of path) {
    if (!node || typeof node !== "object") return null;
    node = node[seg];
  }
  return node && typeof node === "object" ? (node as Record<string, SchemaField>) : null;
}

function replaceContainer(t: AnalyzerTemplate, path: string[], next: Record<string, SchemaField>): void {
  if (!t.fieldSchema) t.fieldSchema = { fields: {} };
  if (!path.length) {
    t.fieldSchema.fields = next;
    return;
  }
  let node: any = t.fieldSchema.fields!;
  for (let i = 0; i < path.length - 1; i++) {
    const seg = path[i];
    if (!node[seg] || typeof node[seg] !== "object") node[seg] = {};
    node = node[seg];
  }
  node[path[path.length - 1]] = next;
}

function safeParse(s: string): AnalyzerTemplate | null {
  try {
    return JSON.parse(s) as AnalyzerTemplate;
  } catch {
    return null;
  }
}
