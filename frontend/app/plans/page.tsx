"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { T } from "@/lib/tokens";
import { CreditCard, Layers3, RefreshCw, Plus, Save, Trash2, Edit3, Puzzle, AlertCircle, Loader2, Sparkles, Wand2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

type Plan = {
  id: number;
  slug: string;
  name: string;
  price_monthly_cents: number;
  stripe_price_id?: string;
  is_active: boolean;
};

type Addon = {
  id: string;
  name: string;
  price: number;
  stripe_price_id: string;
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: `1px solid ${T.border}`,
  background: T.surfaceAlt,
  color: T.text,
  fontSize: 13,
  padding: "10px 12px",
  outline: "none",
};

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  
  // Modals
  const [isNewModal, setIsNewModal] = useState(false);
  const [isAddonModal, setIsAddonModal] = useState(false);
  const [editPlan, setEditPlan] = useState<Plan | null>(null);

  // Form States
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newPrice, setNewPrice] = useState(99);
  
  const [addonName, setAddonName] = useState("");
  const [addonPrice, setAddonPrice] = useState(29);

  async function loadData() {
    setLoading(true);
    try {
      const [pRes, aRes] = await Promise.all([
        apiFetch("/admin/plans"),
        apiFetch("/admin/plans/addons")
      ]);
      if (pRes.ok) setPlans(await pRes.json());
      if (aRes.ok) setAddons(await aRes.json());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadData(); }, []);

  async function triggerSync() {
    setIsSyncing(true);
    await apiFetch("/admin/plans/sync-now", { method: "POST" });
    await loadData();
    setIsSyncing(false);
  }

  async function triggerCleanup() {
    if (!confirm("Alle Pläne ohne Stripe-Anbindung (Leichen) löschen?")) return;
    await apiFetch("/admin/plans/cleanup", { method: "POST" });
    await loadData();
  }

  async function handleDeletePlan(id: number) {
    if (!confirm("Diesen Plan wirklich unwiderruflich löschen?")) return;
    const res = await apiFetch(`/admin/plans/${id}`, { method: "DELETE" });
    if (res.ok) loadData();
  }

  async function handleSaveNew() {
    const res = await apiFetch("/admin/plans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName, slug: newSlug, price: newPrice * 100 })
    });
    if (res.ok) { setIsNewModal(false); loadData(); }
  }

  async function handleSaveAddon() {
    const res = await apiFetch("/admin/plans/addons", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: addonName, price: addonPrice * 100 })
    });
    if (res.ok) { setIsAddonModal(false); loadData(); }
  }

  async function handleUpdate() {
    if (!editPlan) return;
    const res = await apiFetch(`/admin/plans/${editPlan.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(editPlan)
    });
    if (res.ok) { setEditPlan(null); loadData(); }
  }

  if (loading) return <div className="p-20 text-center text-slate-500 font-bold uppercase tracking-widest text-xs flex flex-col items-center gap-4"><Loader2 className="animate-spin" size={32} /> Lade Infrastruktur...</div>;

  return (
    <div className="flex flex-col gap-8 pb-20">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-2xl font-black text-white uppercase tracking-tighter">Billing Infrastructure</h1>
          <p className="text-sm text-slate-500">Zentrale Kontrolle über Abonnements und Add-ons.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={triggerCleanup} className="px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-xl text-xs font-bold border border-red-500/20 transition-all flex items-center gap-2">
            <Wand2 size={14} /> Cleanup DB
          </button>
          <button onClick={triggerSync} disabled={isSyncing} className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold border border-slate-700 transition-all">
            <RefreshCw size={14} className={isSyncing ? "animate-spin" : ""} /> Sync Stripe
          </button>
          <button onClick={() => setIsNewModal(true)} className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-500/20 transition-all">
            <Plus size={16} /> New Plan
          </button>
        </div>
      </div>

      {/* Plans Section */}
      <section className="flex flex-col gap-4">
        <h2 className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2 px-1">
          <Layers3 size={14} /> Subscription Plans
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.map(p => (
            <Card key={p.id} className={`p-6 flex flex-col gap-5 border transition-all ${p.is_active ? 'border-slate-800' : 'border-red-500/20 opacity-50 bg-red-500/[0.01]'}`}>
              <div className="flex justify-between items-start">
                <div className="flex flex-col">
                  <h3 className="font-bold text-white text-lg">{p.name}</h3>
                  <code className="text-[9px] text-slate-500 uppercase tracking-widest mt-1">{p.slug}</code>
                </div>
                <Badge variant={p.is_active ? "success" : "danger"} size="xs">{p.is_active ? "Live" : "Inactive"}</Badge>
              </div>

              <div className="flex flex-col">
                <span className="text-3xl font-black text-white">{p.price_monthly_cents / 100}€<span className="text-xs text-slate-500 ml-1">/mo</span></span>
                <span className={`text-[9px] font-mono truncate mt-2 p-1.5 rounded bg-white/5 ${!p.stripe_price_id ? 'text-red-400 border border-red-500/20' : 'text-slate-500'}`}>
                  {p.stripe_price_id || "FEHLENDE STRIPE-ID"}
                </span>
              </div>

              <div className="flex gap-2 mt-2">
                <button onClick={() => setEditPlan(p)} className="flex-1 py-2.5 bg-white/5 hover:bg-white/10 text-white rounded-xl text-[10px] font-black uppercase tracking-widest border border-white/5 transition-all">
                  Edit
                </button>
                <button onClick={() => handleDeletePlan(p.id)} className="p-2.5 bg-red-500/5 hover:bg-red-500/10 text-red-500 rounded-xl border border-red-500/10 transition-all">
                  <Trash2 size={14} />
                </button>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Addons Section */}
      <section className="flex flex-col gap-4">
        <div className="flex justify-between items-center px-1">
          <h2 className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
            <Puzzle size={14} /> Global Add-ons (via Stripe)
          </h2>
          <button onClick={() => setIsAddonModal(true)} className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 rounded-lg text-[10px] font-black uppercase tracking-widest border border-indigo-500/20 transition-all">
            <Plus size={12} /> Add Extension
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {addons.map(a => (
            <Card key={a.id} className="p-5 bg-slate-900/40 border-slate-800 flex items-center justify-between group hover:border-slate-700 transition-all">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-indigo-500/10 rounded-2xl flex items-center justify-center text-indigo-400 group-hover:bg-indigo-500/20 transition-all">
                  <Sparkles size={24} />
                </div>
                <div>
                  <h4 className="text-sm font-black text-white uppercase tracking-tight">{a.name}</h4>
                  <code className="text-[9px] text-slate-500 font-mono">{a.stripe_price_id}</code>
                </div>
              </div>
              <div className="text-right">
                <div className="text-lg font-black text-white">{a.price / 100}€</div>
                <div className="text-[8px] text-slate-500 uppercase font-black">monthly</div>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* Modals */}
      <Modal open={isNewModal} onClose={() => setIsNewModal(false)} title="New Subscription Plan">
        <div className="p-4 flex flex-col gap-4">
          <input style={inputStyle} value={newName} onChange={e => setNewName(e.target.value)} placeholder="Name (e.g. Professional)" />
          <input style={inputStyle} value={newSlug} onChange={e => setNewSlug(e.target.value)} placeholder="Slug (e.g. professional)" />
          <input style={inputStyle} type="number" value={newPrice} onChange={e => setNewPrice(Number(e.target.value))} placeholder="Price in EUR" />
          <button onClick={handleSaveNew} className="mt-4 py-4 bg-indigo-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs shadow-xl transition-all">Create & Provision Stripe</button>
        </div>
      </Modal>

      <Modal open={isAddonModal} onClose={() => setIsAddonModal(false)} title="New Stripe Add-on">
        <div className="p-4 flex flex-col gap-4">
          <input style={inputStyle} value={addonName} onChange={e => setAddonName(e.target.value)} placeholder="Add-on Name (e.g. Voice Pipeline)" />
          <input style={inputStyle} type="number" value={addonPrice} onChange={e => setAddonPrice(Number(e.target.value))} placeholder="Monthly Price in EUR" />
          <button onClick={handleSaveAddon} className="mt-4 py-4 bg-indigo-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs shadow-xl transition-all">Create Product in Stripe</button>
        </div>
      </Modal>

      <Modal open={!!editPlan} onClose={() => setEditPlan(null)} title="Edit Plan">
        {editPlan && (
          <div className="p-4 flex flex-col gap-4">
            <input style={inputStyle} value={editPlan.name} onChange={e => setEditPlan({...editPlan, name: e.target.value})} />
            <input style={inputStyle} type="number" value={editPlan.price_monthly_cents} onChange={e => setEditPlan({...editPlan, price_monthly_cents: Number(e.target.value)})} />
            <div className="flex items-center gap-3 p-3 bg-white/5 rounded-xl border border-white/5 cursor-pointer" onClick={() => setEditPlan({...editPlan, is_active: !editPlan.is_active})}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${editPlan.is_active ? 'bg-emerald-500' : 'bg-red-500'}`}>{editPlan.is_active ? <Check size={14} /> : <X size={14} />}</div>
              <span className="text-xs font-bold text-white uppercase tracking-wider">Plan Active</span>
            </div>
            <button onClick={handleUpdate} className="mt-4 py-4 bg-indigo-600 text-white rounded-2xl font-black uppercase tracking-widest text-xs shadow-xl transition-all">Save & Sync</button>
          </div>
        )}
      </Modal>
    </div>
  );
}

const X = ({ size }: { size: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
);
const Check = ({ size }: { size: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
);
