"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Search, Users, Plus, Download, Upload, Trash2, MoreHorizontal, Settings2, Filter, Database, Store, UserCircle, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useI18n } from "@/lib/i18n/LanguageContext";

type Member = {
  id: number;
  customer_id: number;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone_number?: string | null;
  source: string;
  source_id?: string | null;
  tags?: string[];
  custom_fields?: Record<string, any>;
  member_since?: string;
  is_paused?: boolean;
};

export default function MembersPage() {
  const { t } = useI18n();
  const [members, setMembers] = useState<Member[]>([]);
  const [columns, setColumns] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  async function fetchData() {
    setIsLoading(true);
    try {
      const [mRes, cRes] = await Promise.all([
        apiFetch("/admin/members"),
        apiFetch("/admin/members/columns")
      ]);
      if (mRes.ok) setMembers(await mRes.json());
      if (cRes.ok) setColumns(await cRes.json());
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  const filteredMembers = useMemo(() => {
    return members.filter(m => 
      `${m.first_name} ${m.last_name}`.toLowerCase().includes(query.toLowerCase()) ||
      m.email?.toLowerCase().includes(query.toLowerCase())
    );
  }, [members, query]);

  async function bulkDelete() {
    if (!confirm(t("members.confirmDelete", { count: selectedIds.size }))) return;
    const res = await apiFetch("/admin/members/bulk", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: Array.from(selectedIds) })
    });
    if (res.ok) {
      setSelectedIds(new Set());
      fetchData();
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader 
        title={t("members.title")} 
        subtitle={t("members.subtitle")}
        action={
          <div className="flex gap-2">
            <button onClick={() => setIsImportModalOpen(true)} className="px-4 py-2 border border-slate-200 rounded-lg text-sm font-semibold flex items-center gap-2 hover:bg-slate-50">
              <Upload size={16} /> {t("members.import")}
            </button>
            <button onClick={() => setIsAddModalOpen(true)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold flex items-center gap-2 hover:bg-indigo-700">
              <Plus size={16} /> {t("members.add")}
            </button>
          </div>
        }
      />

      {/* Stats & Search */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4 bg-white border-slate-200">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{t("members.stats.total")}</div>
          <div className="text-2xl font-black text-slate-900">{members.length}</div>
        </Card>
        <Card className="p-4 bg-white border-slate-200">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{t("members.stats.manual")}</div>
          <div className="text-2xl font-black text-slate-900">{members.filter(m => m.source === 'manual').length}</div>
        </Card>
        <Card className="p-4 bg-white border-slate-200">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{t("members.stats.external")}</div>
          <div className="text-2xl font-black text-slate-900">{members.filter(m => m.source !== 'manual').length}</div>
        </Card>
        <Card className="p-4 bg-white border-slate-200">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{t("members.stats.selected")}</div>
          <div className="flex items-center justify-between">
            <div className="text-2xl font-black text-indigo-600">{selectedIds.size}</div>
            {selectedIds.size > 0 && (
              <button onClick={bulkDelete} className="p-1.5 text-red-500 hover:bg-red-50 rounded-md transition-colors">
                <Trash2 size={18} />
              </button>
            )}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden border-slate-200 shadow-sm">
        <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input 
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500/20 outline-none"
              placeholder={t("members.search")}
            />
          </div>
          <button className="p-2 border border-slate-200 rounded-lg hover:bg-white text-slate-600"><Filter size={18} /></button>
          <button className="p-2 border border-slate-200 rounded-lg hover:bg-white text-slate-600"><Settings2 size={18} /></button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-100">
                <th className="p-4 w-10">
                  <input 
                    type="checkbox" 
                    onChange={e => setSelectedIds(e.target.checked ? new Set(filteredMembers.map(m => m.id)) : new Set())}
                    className="w-4 h-4 rounded border-slate-300 text-indigo-600"
                  />
                </th>
                <th className="p-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t("members.table.member")}</th>
                <th className="p-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t("members.table.source")}</th>
                <th className="p-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t("members.table.status")}</th>
                {columns.filter(c => c.is_visible).map(col => (
                  <th key={col.slug} className="p-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{col.name}</th>
                ))}
                <th className="p-4 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                <tr><td colSpan={10} className="p-12 text-center text-slate-400"><Loader2 className="animate-spin mx-auto mb-2" /> {t("common.loading")}</td></tr>
              ) : filteredMembers.length === 0 ? (
                <tr><td colSpan={10} className="p-12 text-center text-slate-400">{t("members.noMembers")}</td></tr>
              ) : filteredMembers.map(m => (
                <tr key={m.id} className="hover:bg-slate-50/50 transition-colors group">
                  <td className="p-4">
                    <input 
                      type="checkbox" 
                      checked={selectedIds.has(m.id)}
                      onChange={() => toggleSelect(m.id)}
                      className="w-4 h-4 rounded border-slate-300 text-indigo-600"
                    />
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-indigo-50 rounded-full flex items-center justify-center text-indigo-600 font-bold text-sm">
                        {m.first_name[0]}{m.last_name[0]}
                      </div>
                      <div>
                        <div className="font-bold text-slate-900">{m.first_name} {m.last_name}</div>
                        <div className="text-xs text-slate-500">{m.email || m.phone_number || t("members.noContact")}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      {m.source === 'manual' ? <UserCircle size={14} className="text-slate-400" /> : <Database size={14} className="text-indigo-400" />}
                      <span className="text-xs font-medium text-slate-600 capitalize">{m.source}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    {m.is_paused ? (
                      <Badge variant="warning">{t("members.status.paused")}</Badge>
                    ) : (
                      <Badge variant="success">{t("members.status.active")}</Badge>
                    )}
                  </td>
                  {columns.filter(c => c.is_visible).map(col => (
                    <td key={col.slug} className="p-4 text-sm text-slate-600">
                      {m.custom_fields?.[col.slug] || '-'}
                    </td>
                  ))}
                  <td className="p-4">
                    <button className="p-1 text-slate-400 hover:text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity">
                      <MoreHorizontal size={18} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Add Member Modal */}
      <Modal open={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} title={t("members.add")}>
        <div className="p-4 flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-bold text-slate-500">{t("members.form.firstName")}</label>
              <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Max" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-bold text-slate-500">{t("members.form.lastName")}</label>
              <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Mustermann" />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-slate-500">{t("members.form.email")}</label>
            <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="max@beispiel.de" />
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button onClick={() => setIsAddModalOpen(false)} className="px-4 py-2 text-sm font-bold text-slate-500 hover:bg-slate-50 rounded-lg">{t("common.cancel")}</button>
            <button className="px-4 py-2 text-sm font-bold bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">{t("common.save")}</button>
          </div>
        </div>
      </Modal>

      {/* CSV Import Modal */}
      <Modal open={isImportModalOpen} onClose={() => setIsImportModalOpen(false)} title={t("members.importTitle")}>
        <div className="p-8 flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50 gap-4">
          <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-sm text-slate-400">
            <Upload size={24} />
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-slate-900">{t("members.import.clickOrDrop")}</div>
            <div className="text-xs text-slate-500 mt-1">{t("members.import.hint")}</div>
          </div>
          <input type="file" className="hidden" id="csv-upload" accept=".csv" />
          <label htmlFor="csv-upload" className="mt-2 px-4 py-2 bg-white border border-slate-200 rounded-lg text-sm font-bold cursor-pointer hover:bg-slate-50 transition-colors">
            {t("members.import.selectFile")}
          </label>
        </div>
      </Modal>
    </div>
  );
}
