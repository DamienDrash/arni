"use client";

import React, { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Mail,
  MessageSquare,
  Phone,
  Clock,
  GitBranch,
  Tag,
  Pencil,
  ArrowRightCircle,
  Zap,
  Trash2,
  UserCheck,
  X,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

export interface WorkflowGraph {
  nodes: Node[];
  edges: Edge[];
}

interface WorkflowBuilderProps {
  initialGraph?: WorkflowGraph;
  onChange?: (graph: WorkflowGraph) => void;
  readOnly?: boolean;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Node Type Definitions
   ═══════════════════════════════════════════════════════════════════════ */

interface NodeTypeConfig {
  label: string;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  category: "trigger" | "action" | "flow" | "contact";
}

const NODE_TYPES_CONFIG: Record<string, NodeTypeConfig> = {
  trigger: {
    label: "Trigger",
    icon: <Zap size={16} />,
    color: "#f59e0b",
    bgColor: "#fef3c7",
    category: "trigger",
  },
  send_email: {
    label: "E-Mail senden",
    icon: <Mail size={16} />,
    color: "#3b82f6",
    bgColor: "#dbeafe",
    category: "action",
  },
  send_whatsapp: {
    label: "WhatsApp senden",
    icon: <MessageSquare size={16} />,
    color: "#22c55e",
    bgColor: "#dcfce7",
    category: "action",
  },
  send_sms: {
    label: "SMS senden",
    icon: <Phone size={16} />,
    color: "#8b5cf6",
    bgColor: "#ede9fe",
    category: "action",
  },
  wait: {
    label: "Warten",
    icon: <Clock size={16} />,
    color: "#f97316",
    bgColor: "#fff7ed",
    category: "flow",
  },
  condition: {
    label: "Bedingung",
    icon: <GitBranch size={16} />,
    color: "#ec4899",
    bgColor: "#fce7f3",
    category: "flow",
  },
  add_tag: {
    label: "Tag hinzufügen",
    icon: <Tag size={16} />,
    color: "#14b8a6",
    bgColor: "#ccfbf1",
    category: "contact",
  },
  remove_tag: {
    label: "Tag entfernen",
    icon: <Tag size={16} />,
    color: "#ef4444",
    bgColor: "#fee2e2",
    category: "contact",
  },
  set_field: {
    label: "Feld setzen",
    icon: <Pencil size={16} />,
    color: "#6366f1",
    bgColor: "#e0e7ff",
    category: "contact",
  },
  update_lifecycle: {
    label: "Lifecycle ändern",
    icon: <UserCheck size={16} />,
    color: "#0ea5e9",
    bgColor: "#e0f2fe",
    category: "contact",
  },
  end: {
    label: "Ende",
    icon: <ArrowRightCircle size={16} />,
    color: "#6b7280",
    bgColor: "#f3f4f6",
    category: "flow",
  },
};

/* ═══════════════════════════════════════════════════════════════════════════
   Custom Node Component
   ═══════════════════════════════════════════════════════════════════════ */

function CustomNode({ id, data, selected }: NodeProps) {
  const nodeType = (data?.nodeType as string) || "end";
  const config = NODE_TYPES_CONFIG[nodeType] || NODE_TYPES_CONFIG.end;
  const isCondition = nodeType === "condition";
  const isTrigger = nodeType === "trigger";

  return (
    <div
      className={`relative rounded-lg border-2 shadow-sm min-w-[200px] transition-all ${selected ? "ring-2 ring-blue-400 ring-offset-2" : ""}`}
      style={{ borderColor: config.color, backgroundColor: config.bgColor }}
    >
      {/* Input Handle (not for trigger) */}
      {!isTrigger && (
        <Handle
          type="target"
          position={Position.Top}
          className="!w-3 !h-3 !border-2 !border-white"
          style={{ backgroundColor: config.color }}
        />
      )}

      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-md text-white text-sm font-medium"
        style={{ backgroundColor: config.color }}
      >
        {config.icon}
        <span>{config.label}</span>
      </div>

      {/* Body */}
      <div className="px-3 py-2 text-xs text-gray-700 space-y-1">
        {nodeType === "trigger" && (
          <p className="font-medium">{(data?.triggerLabel as string) || "Trigger konfigurieren"}</p>
        )}
        {nodeType === "send_email" && (
          <>
            <p><strong>Betreff:</strong> {(data?.subject as string) || "–"}</p>
          </>
        )}
        {nodeType === "send_whatsapp" && (
          <p><strong>Nachricht:</strong> {((data?.message as string) || "–").slice(0, 60)}</p>
        )}
        {nodeType === "send_sms" && (
          <p><strong>Nachricht:</strong> {((data?.message as string) || "–").slice(0, 60)}</p>
        )}
        {nodeType === "wait" && (
          <p><strong>Dauer:</strong> {(data?.duration as number) || 1} {(data?.unit as string) || "days"}</p>
        )}
        {nodeType === "condition" && (
          <p><strong>Typ:</strong> {(data?.condition_type as string) || "has_tag"}</p>
        )}
        {nodeType === "add_tag" && (
          <p><strong>Tag:</strong> {(data?.tag_name as string) || "–"}</p>
        )}
        {nodeType === "remove_tag" && (
          <p><strong>Tag:</strong> {(data?.tag_name as string) || "–"}</p>
        )}
        {nodeType === "set_field" && (
          <p><strong>Feld:</strong> {(data?.field_name as string) || "–"} = {(data?.field_value as string) || "–"}</p>
        )}
        {nodeType === "update_lifecycle" && (
          <p><strong>Stage:</strong> {(data?.lifecycle_stage as string) || "–"}</p>
        )}
      </div>

      {/* Output Handles */}
      {isCondition ? (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id="yes"
            className="!w-3 !h-3 !border-2 !border-white !left-[30%]"
            style={{ backgroundColor: "#22c55e" }}
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="no"
            className="!w-3 !h-3 !border-2 !border-white !left-[70%]"
            style={{ backgroundColor: "#ef4444" }}
          />
          <div className="absolute -bottom-5 left-[25%] text-[10px] text-green-600 font-bold">JA</div>
          <div className="absolute -bottom-5 left-[65%] text-[10px] text-red-600 font-bold">NEIN</div>
        </>
      ) : nodeType !== "end" ? (
        <Handle
          type="source"
          position={Position.Bottom}
          className="!w-3 !h-3 !border-2 !border-white"
          style={{ backgroundColor: config.color }}
        />
      ) : null}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Node Config Panel
   ═══════════════════════════════════════════════════════════════════════ */

interface NodeConfigPanelProps {
  node: Node | null;
  onUpdate: (id: string, data: Record<string, unknown>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

function NodeConfigPanel({ node, onUpdate, onDelete, onClose }: NodeConfigPanelProps) {
  if (!node) return null;
  const nodeType = (node.data?.nodeType as string) || "end";
  const config = NODE_TYPES_CONFIG[nodeType];

  const update = (key: string, value: unknown) => {
    onUpdate(node.id, { ...node.data, [key]: value });
  };

  return (
    <div className="absolute right-0 top-0 bottom-0 w-80 bg-white border-l border-gray-200 shadow-lg z-50 overflow-y-auto">
      <div className="flex items-center justify-between p-4 border-b" style={{ backgroundColor: config?.bgColor }}>
        <div className="flex items-center gap-2">
          {config?.icon}
          <h3 className="font-semibold text-sm">{config?.label} konfigurieren</h3>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-gray-200 rounded"><X size={16} /></button>
      </div>

      <div className="p-4 space-y-4">
        {/* Trigger Config */}
        {nodeType === "trigger" && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Trigger-Beschreibung</label>
            <input
              type="text"
              className="w-full border rounded px-2 py-1.5 text-sm"
              value={(node.data?.triggerLabel as string) || ""}
              onChange={(e) => update("triggerLabel", e.target.value)}
              placeholder="z.B. Kontakt betritt Segment 'Churn Risk'"
            />
          </div>
        )}

        {/* Email Config */}
        {nodeType === "send_email" && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Betreff</label>
              <input
                type="text"
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={(node.data?.subject as string) || ""}
                onChange={(e) => update("subject", e.target.value)}
                placeholder="E-Mail-Betreff"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Inhalt</label>
              <textarea
                className="w-full border rounded px-2 py-1.5 text-sm h-32"
                value={(node.data?.body as string) || ""}
                onChange={(e) => update("body", e.target.value)}
                placeholder="E-Mail-Inhalt (HTML erlaubt). Platzhalter: {{ contact.first_name }}"
              />
            </div>
          </>
        )}

        {/* WhatsApp Config */}
        {nodeType === "send_whatsapp" && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Nachricht</label>
            <textarea
              className="w-full border rounded px-2 py-1.5 text-sm h-32"
              value={(node.data?.message as string) || ""}
              onChange={(e) => update("message", e.target.value)}
              placeholder="WhatsApp-Nachricht. Platzhalter: {{ contact.first_name }}"
            />
          </div>
        )}

        {/* SMS Config */}
        {nodeType === "send_sms" && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Nachricht</label>
            <textarea
              className="w-full border rounded px-2 py-1.5 text-sm h-24"
              value={(node.data?.message as string) || ""}
              onChange={(e) => update("message", e.target.value)}
              placeholder="SMS-Nachricht (max. 160 Zeichen)"
            />
          </div>
        )}

        {/* Wait Config */}
        {nodeType === "wait" && (
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Dauer</label>
              <input
                type="number"
                min={1}
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={(node.data?.duration as number) || 1}
                onChange={(e) => update("duration", parseInt(e.target.value) || 1)}
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 mb-1">Einheit</label>
              <select
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={(node.data?.unit as string) || "days"}
                onChange={(e) => update("unit", e.target.value)}
              >
                <option value="minutes">Minuten</option>
                <option value="hours">Stunden</option>
                <option value="days">Tage</option>
              </select>
            </div>
          </div>
        )}

        {/* Condition Config */}
        {nodeType === "condition" && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Bedingungstyp</label>
              <select
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={(node.data?.condition_type as string) || "has_tag"}
                onChange={(e) => update("condition_type", e.target.value)}
              >
                <option value="has_tag">Hat Tag</option>
                <option value="field_equals">Feld gleich</option>
                <option value="lifecycle_is">Lifecycle ist</option>
                <option value="segment_member">In Segment</option>
                <option value="email_opened">E-Mail geöffnet</option>
              </select>
            </div>
            {(node.data?.condition_type === "has_tag" || !node.data?.condition_type) && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Tag-Name</label>
                <input
                  type="text"
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={(node.data?.tag_name as string) || ""}
                  onChange={(e) => update("tag_name", e.target.value)}
                  placeholder="z.B. vip"
                />
              </div>
            )}
            {node.data?.condition_type === "field_equals" && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Feldname</label>
                  <input
                    type="text"
                    className="w-full border rounded px-2 py-1.5 text-sm"
                    value={(node.data?.field_name as string) || ""}
                    onChange={(e) => update("field_name", e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Erwarteter Wert</label>
                  <input
                    type="text"
                    className="w-full border rounded px-2 py-1.5 text-sm"
                    value={(node.data?.field_value as string) || ""}
                    onChange={(e) => update("field_value", e.target.value)}
                  />
                </div>
              </>
            )}
            {node.data?.condition_type === "lifecycle_is" && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Lifecycle Stage</label>
                <input
                  type="text"
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={(node.data?.lifecycle_stage as string) || ""}
                  onChange={(e) => update("lifecycle_stage", e.target.value)}
                  placeholder="z.B. active, churn_risk"
                />
              </div>
            )}
            {node.data?.condition_type === "segment_member" && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Segment-ID</label>
                <input
                  type="number"
                  className="w-full border rounded px-2 py-1.5 text-sm"
                  value={(node.data?.segment_id as number) || ""}
                  onChange={(e) => update("segment_id", parseInt(e.target.value) || 0)}
                />
              </div>
            )}
          </>
        )}

        {/* Tag Config */}
        {(nodeType === "add_tag" || nodeType === "remove_tag") && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Tag-Name</label>
            <input
              type="text"
              className="w-full border rounded px-2 py-1.5 text-sm"
              value={(node.data?.tag_name as string) || ""}
              onChange={(e) => update("tag_name", e.target.value)}
              placeholder="z.B. newsletter_subscriber"
            />
          </div>
        )}

        {/* Set Field Config */}
        {nodeType === "set_field" && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Feldname</label>
              <input
                type="text"
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={(node.data?.field_name as string) || ""}
                onChange={(e) => update("field_name", e.target.value)}
                placeholder="z.B. preferred_plan"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Wert</label>
              <input
                type="text"
                className="w-full border rounded px-2 py-1.5 text-sm"
                value={(node.data?.field_value as string) || ""}
                onChange={(e) => update("field_value", e.target.value)}
              />
            </div>
          </>
        )}

        {/* Lifecycle Config */}
        {nodeType === "update_lifecycle" && (
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Neuer Lifecycle Stage</label>
            <input
              type="text"
              className="w-full border rounded px-2 py-1.5 text-sm"
              value={(node.data?.lifecycle_stage as string) || ""}
              onChange={(e) => update("lifecycle_stage", e.target.value)}
              placeholder="z.B. active, churn_risk, won_back"
            />
          </div>
        )}

        {/* Delete Button */}
        {nodeType !== "trigger" && (
          <button
            onClick={() => onDelete(node.id)}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-50 text-red-600 rounded border border-red-200 hover:bg-red-100 text-sm mt-4"
          >
            <Trash2 size={14} />
            Knoten löschen
          </button>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   Node Palette (Sidebar)
   ═══════════════════════════════════════════════════════════════════════ */

interface NodePaletteProps {
  onAddNode: (type: string) => void;
}

function NodePalette({ onAddNode }: NodePaletteProps) {
  const categories: { key: string; label: string; types: string[] }[] = [
    { key: "action", label: "Aktionen", types: ["send_email", "send_whatsapp", "send_sms"] },
    { key: "flow", label: "Ablauf", types: ["wait", "condition", "end"] },
    { key: "contact", label: "Kontakt", types: ["add_tag", "remove_tag", "set_field", "update_lifecycle"] },
  ];

  return (
    <div className="absolute left-0 top-0 bottom-0 w-56 bg-white border-r border-gray-200 shadow-sm z-40 overflow-y-auto">
      <div className="p-3 border-b">
        <h3 className="font-semibold text-sm text-gray-700">Knoten hinzufügen</h3>
      </div>
      {categories.map((cat) => (
        <div key={cat.key} className="p-3 border-b">
          <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">{cat.label}</h4>
          <div className="space-y-1">
            {cat.types.map((type) => {
              const cfg = NODE_TYPES_CONFIG[type];
              return (
                <button
                  key={type}
                  onClick={() => onAddNode(type)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm hover:bg-gray-100 transition-colors text-left"
                >
                  <span style={{ color: cfg.color }}>{cfg.icon}</span>
                  <span className="text-gray-700">{cfg.label}</span>
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
  style: { strokeWidth: 2, stroke: "#94a3b8" },
};

export default function WorkflowBuilder({ initialGraph, onChange, readOnly = false }: WorkflowBuilderProps) {
  const defaultNodes: Node[] = initialGraph?.nodes?.length
    ? initialGraph.nodes.map((n) => ({ ...n, type: "custom" }))
    : [
        {
          id: "trigger-1",
          type: "custom",
          position: { x: 250, y: 50 },
          data: { nodeType: "trigger", triggerLabel: "Trigger konfigurieren" },
        },
      ];

  const defaultEdges: Edge[] = initialGraph?.edges || [];

  const [nodes, setNodes, onNodesChange] = useNodesState(defaultNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(defaultEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [showPalette, setShowPalette] = useState(!readOnly);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (readOnly) return;
      setEdges((eds) => addEdge({ ...connection, ...defaultEdgeOptions }, eds));
    },
    [setEdges, readOnly]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (readOnly) return;
      setSelectedNode(node);
    },
    [readOnly]
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Notify parent of changes
  const notifyChange = useCallback(
    (newNodes: Node[], newEdges: Edge[]) => {
      if (onChange) {
        onChange({
          nodes: newNodes.map((n) => ({ ...n, type: n.data?.nodeType as string || "custom" })),
          edges: newEdges,
        });
      }
    },
    [onChange]
  );

  const handleAddNode = useCallback(
    (type: string) => {
      const id = `${type}-${Date.now()}`;
      const lastNode = nodes[nodes.length - 1];
      const newNode: Node = {
        id,
        type: "custom",
        position: {
          x: lastNode ? lastNode.position.x : 250,
          y: lastNode ? lastNode.position.y + 150 : 200,
        },
        data: { nodeType: type },
      };
      const newNodes = [...nodes, newNode];

      // Auto-connect from last node if possible
      let newEdges = [...edges];
      if (lastNode && type !== "trigger") {
        const newEdge: Edge = {
          id: `e-${lastNode.id}-${id}`,
          source: lastNode.id,
          target: id,
          ...defaultEdgeOptions,
        };
        newEdges = [...newEdges, newEdge];
      }

      setNodes(newNodes);
      setEdges(newEdges);
      notifyChange(newNodes, newEdges);
    },
    [nodes, edges, setNodes, setEdges, notifyChange]
  );

  const handleUpdateNode = useCallback(
    (id: string, data: Record<string, unknown>) => {
      const newNodes = nodes.map((n) => (n.id === id ? { ...n, data } : n));
      setNodes(newNodes);
      setSelectedNode((prev) => (prev?.id === id ? { ...prev, data } : prev));
      notifyChange(newNodes, edges);
    },
    [nodes, edges, setNodes, notifyChange]
  );

  const handleDeleteNode = useCallback(
    (id: string) => {
      const newNodes = nodes.filter((n) => n.id !== id);
      const newEdges = edges.filter((e) => e.source !== id && e.target !== id);
      setNodes(newNodes);
      setEdges(newEdges);
      setSelectedNode(null);
      notifyChange(newNodes, newEdges);
    },
    [nodes, edges, setNodes, setEdges, notifyChange]
  );

  return (
    <div className="relative w-full h-full" style={{ minHeight: 600 }}>
      {/* Node Palette */}
      {showPalette && !readOnly && <NodePalette onAddNode={handleAddNode} />}

      {/* React Flow Canvas */}
      <div className={`w-full h-full ${showPalette && !readOnly ? "pl-56" : ""} ${selectedNode && !readOnly ? "pr-80" : ""}`}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={readOnly ? undefined : onNodesChange}
          onEdgesChange={readOnly ? undefined : onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          nodeTypes={nodeTypes}
          defaultEdgeOptions={defaultEdgeOptions}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          deleteKeyCode={readOnly ? null : "Delete"}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} size={1} color="#e2e8f0" />
          <Controls showInteractive={!readOnly} />
          <MiniMap
            nodeColor={(node) => {
              const nt = (node.data?.nodeType as string) || "end";
              return NODE_TYPES_CONFIG[nt]?.color || "#6b7280";
            }}
            maskColor="rgba(0,0,0,0.08)"
            className="!bg-white !border !border-gray-200 !rounded-lg !shadow-sm"
          />
        </ReactFlow>
      </div>

      {/* Node Config Panel */}
      {!readOnly && (
        <NodeConfigPanel
          node={selectedNode}
          onUpdate={handleUpdateNode}
          onDelete={handleDeleteNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
