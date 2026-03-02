"use client";

import React, { useCallback, useState } from "react";
import {
  ReactFlow, Background, Controls, MiniMap, addEdge,
  useNodesState, useEdgesState, MarkerType, Handle, Position,
  type Node, type Edge, type Connection, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Mail, MessageSquare, Phone, Clock, GitBranch, Tag, Pencil,
  ArrowRightCircle, Zap, Trash2, UserCheck, X,
} from "lucide-react";
import { T } from "@/lib/tokens";

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

export interface WorkflowGraph { nodes: Node[]; edges: Edge[]; }
interface WorkflowBuilderProps { initialGraph?: WorkflowGraph; onChange?: (graph: WorkflowGraph) => void; readOnly?: boolean; }

/* ═══════════════════════════════════════════════════════════════════════════
   Node Type Definitions (Dark Theme)
   ═══════════════════════════════════════════════════════════════════════ */

interface NodeTypeConfig {
  label: string; icon: React.ReactNode; color: string; bgColor: string; category: "trigger" | "action" | "flow" | "contact";
}

const NODE_TYPES_CONFIG: Record<string, NodeTypeConfig> = {
  trigger:          { label: "Trigger",           icon: <Zap size={16} />,              color: T.warning,   bgColor: T.warningDim,  category: "trigger" },
  send_email:       { label: "E-Mail senden",     icon: <Mail size={16} />,             color: T.email,     bgColor: "rgba(234,67,53,0.12)",  category: "action" },
  send_whatsapp:    { label: "WhatsApp senden",   icon: <MessageSquare size={16} />,    color: T.whatsapp,  bgColor: "rgba(37,211,102,0.12)", category: "action" },
  send_sms:         { label: "SMS senden",        icon: <Phone size={16} />,            color: T.phone,     bgColor: "rgba(162,155,254,0.12)", category: "action" },
  wait:             { label: "Warten",            icon: <Clock size={16} />,            color: T.warning,   bgColor: T.warningDim,  category: "flow" },
  condition:        { label: "Bedingung",         icon: <GitBranch size={16} />,        color: "#ec4899",   bgColor: "rgba(236,72,153,0.12)", category: "flow" },
  add_tag:          { label: "Tag hinzufügen",    icon: <Tag size={16} />,              color: T.success,   bgColor: T.successDim,  category: "contact" },
  remove_tag:       { label: "Tag entfernen",     icon: <Tag size={16} />,              color: T.danger,    bgColor: T.dangerDim,   category: "contact" },
  set_field:        { label: "Feld setzen",       icon: <Pencil size={16} />,           color: T.accent,    bgColor: T.accentDim,   category: "contact" },
  update_lifecycle: { label: "Lifecycle ändern",  icon: <UserCheck size={16} />,        color: T.info,      bgColor: T.infoDim,     category: "contact" },
  end:              { label: "Ende",              icon: <ArrowRightCircle size={16} />, color: T.textDim,   bgColor: T.surfaceAlt,  category: "flow" },
};

/* ═══════════════════════════════════════════════════════════════════════════
   Custom Node Component (Dark Theme)
   ═══════════════════════════════════════════════════════════════════════ */

function CustomNode({ id, data, selected }: NodeProps) {
  const nodeType = (data?.nodeType as string) || "end";
  const config = NODE_TYPES_CONFIG[nodeType] || NODE_TYPES_CONFIG.end;
  const isCondition = nodeType === "condition";
  const isTrigger = nodeType === "trigger";

  return (
    <div style={{
      position: "relative", borderRadius: 10, border: `2px solid ${config.color}`,
      background: T.surface, minWidth: 200, transition: "all 0.2s",
      boxShadow: selected ? `0 0 0 2px ${T.accent}` : `0 4px 12px rgba(0,0,0,0.3)`,
    }}>
      {!isTrigger && (
        <Handle type="target" position={Position.Top}
          style={{ width: 12, height: 12, border: `2px solid ${T.surface}`, backgroundColor: config.color }} />
      )}

      <div style={{
        display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
        borderRadius: "8px 8px 0 0", background: config.color, color: "#fff", fontSize: 12, fontWeight: 600,
      }}>
        {config.icon} <span>{config.label}</span>
      </div>

      <div style={{ padding: "8px 12px", fontSize: 11, color: T.textMuted }}>
        {nodeType === "trigger" && <p style={{ fontWeight: 600, color: T.text }}>{(data?.triggerLabel as string) || "Trigger konfigurieren"}</p>}
        {nodeType === "send_email" && <p><strong style={{ color: T.text }}>Betreff:</strong> {(data?.subject as string) || "–"}</p>}
        {(nodeType === "send_whatsapp" || nodeType === "send_sms") && <p><strong style={{ color: T.text }}>Nachricht:</strong> {((data?.message as string) || "–").slice(0, 60)}</p>}
        {nodeType === "wait" && <p><strong style={{ color: T.text }}>Dauer:</strong> {(data?.duration as number) || 1} {(data?.unit as string) || "days"}</p>}
        {nodeType === "condition" && <p><strong style={{ color: T.text }}>Typ:</strong> {(data?.condition_type as string) || "has_tag"}</p>}
        {(nodeType === "add_tag" || nodeType === "remove_tag") && <p><strong style={{ color: T.text }}>Tag:</strong> {(data?.tag_name as string) || "–"}</p>}
        {nodeType === "set_field" && <p><strong style={{ color: T.text }}>Feld:</strong> {(data?.field_name as string) || "–"} = {(data?.field_value as string) || "–"}</p>}
        {nodeType === "update_lifecycle" && <p><strong style={{ color: T.text }}>Stage:</strong> {(data?.lifecycle_stage as string) || "–"}</p>}
      </div>

      {isCondition ? (
        <>
          <Handle type="source" position={Position.Bottom} id="yes" style={{ width: 12, height: 12, border: `2px solid ${T.surface}`, backgroundColor: T.success, left: "30%" }} />
          <Handle type="source" position={Position.Bottom} id="no" style={{ width: 12, height: 12, border: `2px solid ${T.surface}`, backgroundColor: T.danger, left: "70%" }} />
          <div style={{ position: "absolute", bottom: -18, left: "25%", fontSize: 10, color: T.success, fontWeight: 800 }}>JA</div>
          <div style={{ position: "absolute", bottom: -18, left: "65%", fontSize: 10, color: T.danger, fontWeight: 800 }}>NEIN</div>
        </>
      ) : nodeType !== "end" ? (
        <Handle type="source" position={Position.Bottom} style={{ width: 12, height: 12, border: `2px solid ${T.surface}`, backgroundColor: config.color }} />
      ) : null}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Node Config Panel (Dark Theme)
   ═══════════════════════════════════════════════════════════════════════ */

interface NodeConfigPanelProps { node: Node | null; onUpdate: (id: string, data: Record<string, unknown>) => void; onDelete: (id: string) => void; onClose: () => void; }

const panelLabel: React.CSSProperties = { display: "block", fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 5, textTransform: "uppercase", letterSpacing: "0.04em" };
const panelInput: React.CSSProperties = { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", boxSizing: "border-box" };
const panelSelect: React.CSSProperties = { ...panelInput };

function NodeConfigPanel({ node, onUpdate, onDelete, onClose }: NodeConfigPanelProps) {
  if (!node) return null;
  const nodeType = (node.data?.nodeType as string) || "end";
  const config = NODE_TYPES_CONFIG[nodeType];
  const update = (key: string, value: unknown) => { onUpdate(node.id, { ...node.data, [key]: value }); };

  return (
    <div style={{
      position: "absolute", right: 0, top: 0, bottom: 0, width: 320,
      background: T.surface, borderLeft: `1px solid ${T.border}`, boxShadow: "-8px 0 30px rgba(0,0,0,.3)", zIndex: 50, overflowY: "auto",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderBottom: `1px solid ${T.border}`, background: config?.bgColor }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: config?.color }}>{config?.icon}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{config?.label} konfigurieren</span>
        </div>
        <button onClick={onClose} style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 6, padding: "4px 6px", cursor: "pointer", color: T.textDim }}>
          <X size={14} />
        </button>
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
        {nodeType === "trigger" && (
          <div><label style={panelLabel}>Trigger-Beschreibung</label><input style={panelInput} type="text" value={(node.data?.triggerLabel as string) || ""} onChange={(e) => update("triggerLabel", e.target.value)} placeholder="z.B. Kontakt betritt Segment 'Churn Risk'" /></div>
        )}
        {nodeType === "send_email" && (
          <>
            <div><label style={panelLabel}>Betreff</label><input style={panelInput} type="text" value={(node.data?.subject as string) || ""} onChange={(e) => update("subject", e.target.value)} placeholder="E-Mail-Betreff" /></div>
            <div><label style={panelLabel}>Inhalt</label><textarea style={{ ...panelInput, height: 120, resize: "vertical" }} value={(node.data?.body as string) || ""} onChange={(e) => update("body", e.target.value)} placeholder="E-Mail-Inhalt (HTML). Platzhalter: {{ contact.first_name }}" /></div>
          </>
        )}
        {nodeType === "send_whatsapp" && (
          <div><label style={panelLabel}>Nachricht</label><textarea style={{ ...panelInput, height: 120, resize: "vertical" }} value={(node.data?.message as string) || ""} onChange={(e) => update("message", e.target.value)} placeholder="WhatsApp-Nachricht" /></div>
        )}
        {nodeType === "send_sms" && (
          <div><label style={panelLabel}>Nachricht</label><textarea style={{ ...panelInput, height: 90, resize: "vertical" }} value={(node.data?.message as string) || ""} onChange={(e) => update("message", e.target.value)} placeholder="SMS-Nachricht (max. 160 Zeichen)" /></div>
        )}
        {nodeType === "wait" && (
          <div style={{ display: "flex", gap: 10 }}>
            <div style={{ flex: 1 }}><label style={panelLabel}>Dauer</label><input style={panelInput} type="number" min={1} value={(node.data?.duration as number) || 1} onChange={(e) => update("duration", parseInt(e.target.value) || 1)} /></div>
            <div style={{ flex: 1 }}><label style={panelLabel}>Einheit</label><select style={panelSelect} value={(node.data?.unit as string) || "days"} onChange={(e) => update("unit", e.target.value)}><option value="minutes">Minuten</option><option value="hours">Stunden</option><option value="days">Tage</option></select></div>
          </div>
        )}
        {nodeType === "condition" && (
          <>
            <div><label style={panelLabel}>Bedingungstyp</label><select style={panelSelect} value={(node.data?.condition_type as string) || "has_tag"} onChange={(e) => update("condition_type", e.target.value)}><option value="has_tag">Hat Tag</option><option value="field_equals">Feld gleich</option><option value="lifecycle_is">Lifecycle ist</option><option value="segment_member">In Segment</option><option value="email_opened">E-Mail geöffnet</option></select></div>
            {(node.data?.condition_type === "has_tag" || !node.data?.condition_type) && (
              <div><label style={panelLabel}>Tag-Name</label><input style={panelInput} type="text" value={(node.data?.tag_name as string) || ""} onChange={(e) => update("tag_name", e.target.value)} placeholder="z.B. vip" /></div>
            )}
            {node.data?.condition_type === "field_equals" && (
              <><div><label style={panelLabel}>Feldname</label><input style={panelInput} type="text" value={(node.data?.field_name as string) || ""} onChange={(e) => update("field_name", e.target.value)} /></div><div><label style={panelLabel}>Erwarteter Wert</label><input style={panelInput} type="text" value={(node.data?.field_value as string) || ""} onChange={(e) => update("field_value", e.target.value)} /></div></>
            )}
            {node.data?.condition_type === "lifecycle_is" && (
              <div><label style={panelLabel}>Lifecycle Stage</label><input style={panelInput} type="text" value={(node.data?.lifecycle_stage as string) || ""} onChange={(e) => update("lifecycle_stage", e.target.value)} placeholder="z.B. active, churn_risk" /></div>
            )}
            {node.data?.condition_type === "segment_member" && (
              <div><label style={panelLabel}>Segment-ID</label><input style={panelInput} type="number" value={(node.data?.segment_id as number) || ""} onChange={(e) => update("segment_id", parseInt(e.target.value) || 0)} /></div>
            )}
          </>
        )}
        {(nodeType === "add_tag" || nodeType === "remove_tag") && (
          <div><label style={panelLabel}>Tag-Name</label><input style={panelInput} type="text" value={(node.data?.tag_name as string) || ""} onChange={(e) => update("tag_name", e.target.value)} placeholder="z.B. newsletter_subscriber" /></div>
        )}
        {nodeType === "set_field" && (
          <><div><label style={panelLabel}>Feldname</label><input style={panelInput} type="text" value={(node.data?.field_name as string) || ""} onChange={(e) => update("field_name", e.target.value)} placeholder="z.B. preferred_plan" /></div><div><label style={panelLabel}>Wert</label><input style={panelInput} type="text" value={(node.data?.field_value as string) || ""} onChange={(e) => update("field_value", e.target.value)} /></div></>
        )}
        {nodeType === "update_lifecycle" && (
          <div><label style={panelLabel}>Neuer Lifecycle Stage</label><input style={panelInput} type="text" value={(node.data?.lifecycle_stage as string) || ""} onChange={(e) => update("lifecycle_stage", e.target.value)} placeholder="z.B. active, churn_risk, won_back" /></div>
        )}
        {nodeType !== "trigger" && (
          <button onClick={() => onDelete(node.id)} style={{
            width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            padding: "9px 12px", background: T.dangerDim, color: T.danger, borderRadius: 8,
            border: `1px solid ${T.danger}30`, fontSize: 13, fontWeight: 600, cursor: "pointer", marginTop: 8,
          }}>
            <Trash2 size={14} /> Knoten löschen
          </button>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Node Palette (Dark Theme)
   ═══════════════════════════════════════════════════════════════════════ */

interface NodePaletteProps { onAddNode: (type: string) => void; }

function NodePalette({ onAddNode }: NodePaletteProps) {
  const categories: { key: string; label: string; types: string[] }[] = [
    { key: "action", label: "Aktionen", types: ["send_email", "send_whatsapp", "send_sms"] },
    { key: "flow", label: "Ablauf", types: ["wait", "condition", "end"] },
    { key: "contact", label: "Kontakt", types: ["add_tag", "remove_tag", "set_field", "update_lifecycle"] },
  ];

  return (
    <div style={{
      position: "absolute", left: 0, top: 0, bottom: 0, width: 220,
      background: T.surface, borderRight: `1px solid ${T.border}`, boxShadow: "4px 0 12px rgba(0,0,0,.2)", zIndex: 40, overflowY: "auto",
    }}>
      <div style={{ padding: "12px 14px", borderBottom: `1px solid ${T.border}` }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Knoten hinzufügen</span>
      </div>
      {categories.map((cat) => (
        <div key={cat.key} style={{ padding: "10px 14px", borderBottom: `1px solid ${T.border}` }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>{cat.label}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {cat.types.map((type) => {
              const cfg = NODE_TYPES_CONFIG[type];
              return (
                <button key={type} onClick={() => onAddNode(type)} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", borderRadius: 8,
                  border: "none", background: "transparent", cursor: "pointer", transition: "background .15s",
                  fontSize: 12, color: T.text, textAlign: "left", width: "100%",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <span style={{ color: cfg.color }}>{cfg.icon}</span>
                  <span>{cfg.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Main Workflow Builder
   ═══════════════════════════════════════════════════════════════════════ */

const nodeTypes = { custom: CustomNode };

const defaultEdgeOptions = {
  type: "smoothstep",
  markerEnd: { type: MarkerType.ArrowClosed },
  style: { strokeWidth: 2, stroke: T.textDim },
};

export default function WorkflowBuilder({ initialGraph, onChange, readOnly = false }: WorkflowBuilderProps) {
  const defaultNodes: Node[] = initialGraph?.nodes?.length
    ? initialGraph.nodes.map((n) => ({ ...n, type: "custom" }))
    : [{ id: "trigger-1", type: "custom", position: { x: 250, y: 50 }, data: { nodeType: "trigger", triggerLabel: "Trigger konfigurieren" } }];

  const defaultEdges: Edge[] = initialGraph?.edges || [];

  const [nodes, setNodes, onNodesChange] = useNodesState(defaultNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(defaultEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [showPalette] = useState(!readOnly);

  const onConnect = useCallback((connection: Connection) => {
    if (readOnly) return;
    setEdges((eds) => addEdge({ ...connection, ...defaultEdgeOptions }, eds));
  }, [setEdges, readOnly]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => { if (!readOnly) setSelectedNode(node); }, [readOnly]);
  const onPaneClick = useCallback(() => { setSelectedNode(null); }, []);

  const notifyChange = useCallback((newNodes: Node[], newEdges: Edge[]) => {
    if (onChange) onChange({ nodes: newNodes.map((n) => ({ ...n, type: n.data?.nodeType as string || "custom" })), edges: newEdges });
  }, [onChange]);

  const handleAddNode = useCallback((type: string) => {
    const id = `${type}-${Date.now()}`;
    const lastNode = nodes[nodes.length - 1];
    const newNode: Node = { id, type: "custom", position: { x: lastNode ? lastNode.position.x : 250, y: lastNode ? lastNode.position.y + 150 : 200 }, data: { nodeType: type } };
    const newNodes = [...nodes, newNode];
    let newEdges = [...edges];
    if (lastNode && type !== "trigger") {
      newEdges = [...newEdges, { id: `e-${lastNode.id}-${id}`, source: lastNode.id, target: id, ...defaultEdgeOptions }];
    }
    setNodes(newNodes); setEdges(newEdges); notifyChange(newNodes, newEdges);
  }, [nodes, edges, setNodes, setEdges, notifyChange]);

  const handleUpdateNode = useCallback((id: string, data: Record<string, unknown>) => {
    const newNodes = nodes.map((n) => (n.id === id ? { ...n, data } : n));
    setNodes(newNodes); setSelectedNode((prev) => (prev?.id === id ? { ...prev, data } : prev)); notifyChange(newNodes, edges);
  }, [nodes, edges, setNodes, notifyChange]);

  const handleDeleteNode = useCallback((id: string) => {
    const newNodes = nodes.filter((n) => n.id !== id);
    const newEdges = edges.filter((e) => e.source !== id && e.target !== id);
    setNodes(newNodes); setEdges(newEdges); setSelectedNode(null); notifyChange(newNodes, newEdges);
  }, [nodes, edges, setNodes, setEdges, notifyChange]);

  const paletteWidth = showPalette && !readOnly ? 220 : 0;
  const configWidth = selectedNode && !readOnly ? 320 : 0;

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: 600, background: T.bg }}>
      {showPalette && !readOnly && <NodePalette onAddNode={handleAddNode} />}

      <div style={{ position: "absolute", left: paletteWidth, right: configWidth, top: 0, bottom: 0 }}>
        <ReactFlow
          nodes={nodes} edges={edges}
          onNodesChange={readOnly ? undefined : onNodesChange}
          onEdgesChange={readOnly ? undefined : onEdgesChange}
          onConnect={onConnect} onNodeClick={onNodeClick} onPaneClick={onPaneClick}
          nodeTypes={nodeTypes} defaultEdgeOptions={defaultEdgeOptions}
          fitView fitViewOptions={{ padding: 0.2 }} deleteKeyCode={readOnly ? null : "Delete"}
          proOptions={{ hideAttribution: true }}
          style={{ background: T.bg }}
        >
          <Background gap={20} size={1} color={T.border} />
          <Controls showInteractive={!readOnly} style={{ background: T.surface, borderRadius: 10, border: `1px solid ${T.border}` }} />
          <MiniMap
            nodeColor={(node) => { const nt = (node.data?.nodeType as string) || "end"; return NODE_TYPES_CONFIG[nt]?.color || T.textDim; }}
            maskColor="rgba(0,0,0,0.4)"
            style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}
          />
        </ReactFlow>
      </div>

      {!readOnly && (
        <NodeConfigPanel node={selectedNode} onUpdate={handleUpdateNode} onDelete={handleDeleteNode} onClose={() => setSelectedNode(null)} />
      )}
    </div>
  );
}
