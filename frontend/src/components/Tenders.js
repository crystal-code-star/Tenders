import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, Globe, Building2,
  ExternalLink, CheckCircle,
  Loader, Zap,
  Download, FileArchive,
  X, Target, Calendar, Clock,
  Monitor,
  Plus, Trash2, Tag, Filter, SlidersHorizontal, FileText, Check,
  ChevronRight, Shield, Users,
  DollarSign, FileCheck, Briefcase, ClipboardList,
  Truck, Wrench, Beaker, PenTool,
  BarChart3, Award, Eye, Laptop,
  Table, ChevronDown, ChevronUp, Star, UserCheck, AlertTriangle,
  RotateCcw,
} from 'lucide-react';
import {
  API_URL, authHeaders, STATUS_MAP, fmtDate, getScore,
} from './tenderUtils';
import ZipViewerModal from './ZipViewerModal';

const CW_THEME_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  .cw-theme { 
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, ui-sans-serif, sans-serif; 
    background-color: #F8FAFC;
  }
  .cw-serif { font-family: 'Inter', serif; }
  .cw-mono { font-family: 'SF Mono', 'Fira Code', 'Fira Mono', 'Roboto Mono', monospace; }
  
  * {
    transition-property: background-color, border-color, color, fill, stroke, opacity, box-shadow, transform;
    transition-duration: 150ms;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }

  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
`;

const HashIcon = (props) => (
  <span {...props} style={{ fontSize: '14px', fontWeight: 'bold', lineHeight: 1 }}>#</span>
);

function truncateTitleBeforeDots(title) {
  if (!title) return 'Untitled';
  const dotsIndex = title.search(/\.\.\.|…/);
  if (dotsIndex > 0) return title.substring(0, dotsIndex).trim();
  return title;
}

function formatPublicationDate(dateString) {
  if (!dateString) return null;
  const date = new Date(dateString);
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
}

function truncateText(text, maxLen = 25) {
  if (!text || text === '—') return '—';
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen) + '...';
}

function QualificationIcon({ status, size = 20 }) {
  const colors = {
    unseen: { bg: '#F1F5F9', fg: '#94A3B8' },
    seen: { bg: '#F1F5F9', fg: '#64748B' },
    preselected: { bg: '#FEF9C3', fg: '#CA8A04' },
    qualified: { bg: '#DCFCE7', fg: '#16A34A' },
  };
  const c = colors[status] || colors.unseen;
  return (
    <div 
      className="relative flex-shrink-0 rounded-full flex items-center justify-center font-bold text-[10px] cw-mono"
      style={{ 
        width: size + 4, 
        height: size + 4, 
        backgroundColor: c.bg, 
        color: c.fg,
        border: `1.5px solid ${c.fg}20`,
        boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.03)'
      }}
    >
      {status === 'preselected' && <Star size={size - 4} style={{ color: c.fg }} />}
      {status === 'qualified' && <UserCheck size={size - 4} style={{ color: c.fg }} />}
      {(status === 'unseen' || status === 'seen') && <Eye size={size - 4} style={{ color: c.fg }} />}
    </div>
  );
}

function GaugeDial({ score, size = 44, thickness = 4 }) {
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const band = score >= 70 ? '#2563EB' : score >= 45 ? '#CA8A04' : '#64748B';
  const cx = size / 2, cy = size / 2;
  const ticks = Array.from({ length: 20 });
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g opacity="0.3">
          {ticks.map((_, i) => {
            const angle = (i / ticks.length) * 2 * Math.PI;
            const x1 = cx + Math.cos(angle) * (r + thickness / 2 + 1);
            const y1 = cy + Math.sin(angle) * (r + thickness / 2 + 1);
            const x2 = cx + Math.cos(angle) * (r + thickness / 2 + 3);
            const y2 = cy + Math.sin(angle) * (r + thickness / 2 + 3);
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#CBD5E1" strokeWidth="0.5" />;
          })}
        </g>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#E2E8F0" strokeWidth={thickness} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={band}
          strokeWidth={thickness} strokeDasharray={`${c * pct} ${c}`} strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="cw-mono font-semibold tracking-tight" style={{ fontSize: size * 0.3, color: band }}>{score}</span>
      </div>
    </div>
  );
}

function StatusBadge({ status, onClick }) {
  if (status === 'new') return null;
  const c = STATUS_MAP[status] || STATUS_MAP.new;
  return (
    <button onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all duration-200 hover:scale-[1.02] active:scale-95 ${c.bg} ${c.text} border ${c.ring}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />{c.label}
    </button>
  );
}

function FilterPill({ active, onClick, children, icon }) {
  return (
    <button onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium transition-all duration-200 whitespace-nowrap active:scale-95 ${
        active
          ? 'bg-[#111827] border-[#111827] text-white shadow-sm'
          : 'bg-white border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC] hover:border-[#94A3B8] hover:shadow-sm'
      }`}>
      {icon}{children}
    </button>
  );
}

function InfoCard({ icon: Icon, label, value, color = '#2563EB' }) {
  return (
    <div className="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${color}10` }}>
          <Icon size={14} style={{ color }} />
        </div>
        <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B] truncate">{label}</span>
      </div>
      <p className="text-sm font-semibold text-[#0F172A] truncate cw-mono">{value || '—'}</p>
    </div>
  );
}

function DetailField({ icon: Icon, label, value }) {
  return (
    <div className="flex items-start justify-between py-3 px-3 hover:bg-[#F8FAFC]/70 transition-colors duration-150 gap-3">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <div className="w-8 h-8 rounded-xl bg-[#F8FAFC] flex items-center justify-center flex-shrink-0">
          <Icon size={14} className="text-[#64748B]" />
        </div>
        <span className="text-xs text-[#475569] truncate font-medium">{label}</span>
      </div>
      <div className="flex-shrink-0 max-w-[50%]">
        {typeof value === 'boolean' ? (
          value ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-[#DCFCE7] text-[11px] font-semibold text-[#16A34A] whitespace-nowrap">
              <CheckCircle size={10} className="text-[#16A34A] flex-shrink-0" /> Yes
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-[#FEE2E2] text-[11px] font-semibold text-[#DC2626] whitespace-nowrap">
              <X size={10} className="text-[#DC2626] flex-shrink-0" /> No
            </span>
          )
        ) : value && value !== '—' ? (
          <span className="text-xs font-semibold text-[#0F172A] text-right block truncate cw-mono" title={value}>{value}</span>
        ) : (
          <span className="text-xs text-[#94A3B8] italic">—</span>
        )}
      </div>
    </div>
  );
}

const QUALIFICATION_OPTIONS = [
  { value: 'preselected', label: 'Présélectionnés', icon: Star, color: '#CA8A04' },
  { value: 'qualified', label: 'Qualifiés', icon: UserCheck, color: '#16A34A' },
];

function QualificationFilterDropdown({ selected, onToggle, onClear }) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setIsOpen(false); };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const activeCount = selected.length;

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setIsOpen(!isOpen)}
        className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium transition-all duration-200 whitespace-nowrap active:scale-95 ${
          activeCount > 0
            ? 'bg-[#111827] border-[#111827] text-white shadow-sm'
            : 'bg-white border-[#E2E8F0] text-[#475569] hover:bg-[#F8FAFC] hover:border-[#94A3B8] hover:shadow-sm'
        }`}>
        <Filter size={11} />
        Statut
        {activeCount > 0 && (
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-white/20 text-white text-[9px] font-semibold">{activeCount}</span>
        )}
        <ChevronDown size={11} className={`transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-56 bg-white rounded-2xl border border-[#E2E8F0] shadow-xl z-30 overflow-hidden">
          <div className="p-2 space-y-1">
            {QUALIFICATION_OPTIONS.map(opt => {
              const Icon = opt.icon;
              const isActive = selected.includes(opt.value);
              return (
                <button key={opt.value} onClick={() => onToggle(opt.value)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-medium transition-all ${
                    isActive ? 'bg-[#F8FAFC] text-[#0F172A]' : 'text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A]'
                  }`}>
                  <Icon size={13} style={{ color: isActive ? opt.color : '#94A3B8' }} />
                  <span className="flex-1 text-left">{opt.label}</span>
                  {isActive && <Check size={13} className="text-[#2563EB]" strokeWidth={3} />}
                </button>
              );
            })}
          </div>
          {activeCount > 0 && (
            <div className="border-t border-[#E2E8F0] p-1.5">
              <button onClick={() => { onClear(); setIsOpen(false); }}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-medium text-[#94A3B8] hover:text-[#DC2626] hover:bg-red-50 transition-all">
                <X size={11} />Effacer les filtres
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function KeywordManager({ isOpen, onClose, keywords, onAdd, onDelete, onToggle }) {
  const [newKeyword, setNewKeyword] = useState('');
  const [error, setError] = useState('');
  const handleAdd = () => { if (!newKeyword.trim()) { setError('Keyword cannot be empty'); return; } onAdd(newKeyword.trim()); setNewKeyword(''); setError(''); };
  if (!isOpen) return null;
  const activeCount = keywords.filter(k => k.is_active).length;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 backdrop-blur-sm">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-[#E2E8F0] transform transition-all duration-200 scale-100">
        <div className="p-6 border-b border-[#E2E8F0]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-[#111827] flex items-center justify-center shadow-sm">
                <Tag size={18} className="text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-[#0F172A] text-base">Filter Keywords</h3>
                <p className="text-xs text-[#64748B]">{activeCount} active · {keywords.length} total</p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] rounded-xl transition-colors">
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="p-6 border-b border-[#E2E8F0] bg-white">
          <div className="flex gap-2">
            <input 
              type="text" 
              value={newKeyword} 
              onChange={(e) => { setNewKeyword(e.target.value); setError(''); }} 
              onKeyPress={(e) => e.key === 'Enter' && handleAdd()} 
              placeholder="Add a keyword..." 
              className="flex-1 px-4 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] placeholder-[#94A3B8] bg-[#F8FAFC]" 
            />
            <button 
              onClick={handleAdd} 
              className="px-5 py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all duration-200 active:scale-95 flex items-center gap-1.5 flex-shrink-0 shadow-sm"
            >
              <Plus size={15} /> Add
            </button>
          </div>
          {error && <p className="flex items-center gap-1.5 mt-2 text-xs text-[#DC2626]"><AlertTriangle size={12} /> {error}</p>}
        </div>
        <div className="max-h-72 overflow-y-auto">
          {keywords.length === 0 ? (
            <div className="p-10 text-center">
              <div className="w-12 h-12 rounded-2xl bg-[#F8FAFC] flex items-center justify-center mx-auto mb-3">
                <Tag size={22} className="text-[#94A3B8]" />
              </div>
              <p className="text-sm font-semibold text-[#475569]">No keywords yet</p>
              <p className="text-xs text-[#94A3B8] mt-1">Add keywords to filter tenders</p>
            </div>
          ) : (
            <div className="divide-y divide-[#E2E8F0]">
              {keywords.map((kw) => (
                <div key={kw.id} className="flex items-center justify-between px-6 py-4 hover:bg-[#F8FAFC] transition-colors duration-150">
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <button 
                      onClick={() => onToggle(kw.id, !kw.is_active)} 
                      className={`flex-shrink-0 w-5 h-5 rounded-lg border-2 transition-all duration-200 flex items-center justify-center ${
                        kw.is_active ? 'bg-[#2563EB] border-[#2563EB]' : 'border-[#CBD5E1] hover:border-[#2563EB]/40'
                      }`}
                    >
                      {kw.is_active && <Check size={12} className="text-white" strokeWidth={3} />}
                    </button>
                    <span className={`text-sm truncate font-medium transition-colors ${kw.is_active ? 'text-[#0F172A]' : 'text-[#94A3B8]'}`}>
                      {kw.keyword}
                    </span>
                  </div>
                  <button 
                    onClick={() => onDelete(kw.id)} 
                    className="p-1.5 text-[#94A3B8] hover:text-[#DC2626] hover:bg-[#FEE2E2] rounded-xl transition-all duration-200 ml-2"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="p-6 border-t border-[#E2E8F0] bg-[#F8FAFC]">
          <button 
            onClick={onClose} 
            className="w-full py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all duration-200 active:scale-[0.98] shadow-sm"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════ BP ITEMS MODAL - CORRIGÉ ═══════════════
function BPItemsModal({ tenderReference, onClose }) {
  const [bpData, setBpData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedItems, setExpandedItems] = useState({});
  const [showAll, setShowAll] = useState(false);
  const fetchBPData = useCallback(async () => {
    try { 
      setLoading(true); 
      // ⚠️ Remplacer / par ___ pour éviter les problèmes de routage FastAPI
      const safeRef = tenderReference.replace(/\//g, '___');
      const response = await fetch(`${API_URL}/tenders/${safeRef}/bp-items`, { headers: authHeaders() }); 
      if (!response.ok) throw new Error('Failed to fetch BP data'); 
      const data = await response.json(); 
      setBpData(data); 
    } catch (err) { 
      setError(err.message); 
    } finally { 
      setLoading(false); 
    }
  }, [tenderReference]);

  useEffect(() => {
    fetchBPData();
  }, [fetchBPData]);

  const toggleItem = (id) => setExpandedItems(prev => ({ ...prev, [id]: !prev[id] }));
  const displayItems = showAll ? (bpData?.items || []) : (bpData?.items || []).slice(0, 20);
  const totalItems = bpData?.total_items || bpData?.items?.length || 0;
  const summary = bpData?.summary || {};

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 backdrop-blur-sm">
        <div className="bg-white rounded-3xl shadow-2xl p-8 flex flex-col items-center gap-4">
          <Loader size={32} className="text-[#2563EB] animate-spin" />
          <p className="text-sm font-medium text-[#475569]">Loading BP items...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 backdrop-blur-sm">
        <div className="bg-white rounded-3xl shadow-2xl p-8 max-w-md mx-4">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-2xl bg-[#FEE2E2] flex items-center justify-center">
              <AlertTriangle size={20} className="text-[#DC2626]" />
            </div>
            <div>
              <h3 className="font-semibold text-[#0F172A]">Error Loading BP Data</h3>
              <p className="text-xs text-[#64748B]">{error}</p>
            </div>
          </div>
          <button onClick={onClose} className="w-full py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all">
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-[#0F172A]/40 backdrop-blur-sm overflow-y-auto py-8">
      <div className="bg-white rounded-3xl shadow-2xl w-full max-w-5xl mx-4 border border-[#E2E8F0]">
        <div className="p-6 border-b border-[#E2E8F0]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-[#111827] flex items-center justify-center shadow-sm">
                <Table size={18} className="text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-[#0F172A] text-lg">Bordereau des Prix</h3>
                <p className="text-xs text-[#64748B]">
                  {totalItems} items • Total HT: {(summary.total_ht || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} DHS
                </p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 text-[#64748B] hover:text-[#0F172A] hover:bg-[#F8FAFC] rounded-xl transition-colors">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="p-6 grid grid-cols-4 gap-4">
          <div className="bg-[#EFF6FF] rounded-2xl p-4 border border-[#BFDBFE]">
            <p className="text-[11px] font-semibold text-[#475569] uppercase mb-1">Total Items</p>
            <p className="text-lg font-semibold text-[#2563EB] cw-mono">{totalItems}</p>
          </div>
          <div className="bg-[#FEF9C3]/50 rounded-2xl p-4 border border-[#FDE68A]">
            <p className="text-[11px] font-semibold text-[#475569] uppercase mb-1">Total HT</p>
            <p className="text-lg font-semibold text-[#CA8A04] cw-mono">
              {(summary.total_ht || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
          <div className="bg-[#F1F5F9] rounded-2xl p-4 border border-[#CBD5E1]">
            <p className="text-[11px] font-semibold text-[#475569] uppercase mb-1">Total Quantité</p>
            <p className="text-lg font-semibold text-[#475569] cw-mono">
              {(summary.total_qty || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
          <div className="bg-[#DCFCE7] rounded-2xl p-4 border border-[#BBF7D0]">
            <p className="text-[11px] font-semibold text-[#475569] uppercase mb-1">Prix Moyen</p>
            <p className="text-lg font-semibold text-[#16A34A] cw-mono">
              {(summary.avg_price || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
        </div>

        {totalItems > 0 ? (
          <div className="overflow-x-auto border-t border-[#E2E8F0]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">N° Prix</th>
                  <th className="text-left px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">Désignation</th>
                  <th className="text-center px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">Unité</th>
                  <th className="text-right px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">Quantité</th>
                  <th className="text-right px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">PU HT</th>
                  <th className="text-right px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">Total HT</th>
                  <th className="text-center px-4 py-3 text-[11px] font-semibold text-[#64748B] uppercase tracking-wide w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {displayItems.map((item, index) => (
                  <React.Fragment key={item.id || index}>
                    <tr className="hover:bg-[#F8FAFC]/50 transition-colors group">
                      <td className="px-4 py-3 cw-mono text-xs font-medium text-[#2563EB]">{item.n_prix || '—'}</td>
                      <td className="px-4 py-3 text-xs text-[#0F172A] max-w-xs">
                        <div className="truncate" title={item.designation}>{item.designation || '—'}</div>
                      </td>
                      <td className="px-4 py-3 text-center text-xs text-[#475569]">{item.unite || '—'}</td>
                      <td className="px-4 py-3 text-right cw-mono text-xs text-[#0F172A]">
                        {item.quantite ? parseFloat(item.quantite).toLocaleString('fr-FR') : '—'}
                      </td>
                      <td className="px-4 py-3 text-right cw-mono text-xs font-medium text-[#2563EB]">
                        {item.prix_unitaire_ht ? parseFloat(item.prix_unitaire_ht).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                      </td>
                      <td className="px-4 py-3 text-right cw-mono text-xs font-semibold text-[#0F172A]">
                        {item.total_ht ? parseFloat(item.total_ht).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button onClick={() => toggleItem(item.id || index)} className="p-1 rounded-xl hover:bg-[#EFF6FF] text-[#94A3B8] hover:text-[#2563EB] transition-all opacity-0 group-hover:opacity-100">
                          {expandedItems[item.id || index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                      </td>
                    </tr>
                    {expandedItems[item.id || index] && (
                      <tr className="bg-[#F8FAFC]">
                        <td colSpan={7} className="px-6 py-4">
                          <div className="grid grid-cols-3 gap-4 text-xs">
                            {item.code_ouvrage_peq && <div><span className="text-[#94A3B8]">Code Ouvrage PEQ:</span><span className="ml-2 font-medium text-[#0F172A]">{item.code_ouvrage_peq}</span></div>}
                            {item.code_serie_peq && <div><span className="text-[#94A3B8]">Code Série PEQ:</span><span className="ml-2 font-medium text-[#0F172A]">{item.code_serie_peq}</span></div>}
                            {item.code_prix_peq && <div><span className="text-[#94A3B8]">Code Prix PEQ:</span><span className="ml-2 font-medium text-[#0F172A]">{item.code_prix_peq}</span></div>}
                            <div className="col-span-3"><span className="text-[#94A3B8]">Désignation complète:</span><p className="mt-1 text-[#0F172A]">{item.designation}</p></div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 text-center">
            <div className="w-12 h-12 rounded-2xl bg-[#F8FAFC] flex items-center justify-center mx-auto mb-3">
              <Table size={22} className="text-[#94A3B8]" />
            </div>
            <p className="text-sm font-semibold text-[#475569]">Aucun item BP trouvé</p>
            <p className="text-xs text-[#94A3B8] mt-1">Les données du bordereau des prix n'ont pas encore été extraites</p>
          </div>
        )}

        {totalItems > 20 && !showAll && (
          <div className="p-6 border-t border-[#E2E8F0] text-center">
            <button onClick={() => setShowAll(true)} className="px-4 py-3 bg-white border border-[#E2E8F0] rounded-2xl text-sm font-medium text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A] transition-all shadow-sm">
              Show all {totalItems} items
            </button>
          </div>
        )}

        <div className="p-6 border-t border-[#E2E8F0] bg-[#F8FAFC] rounded-b-3xl">
          <button onClick={onClose} className="w-full py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all shadow-sm">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function TenderCard({ item, active, onClick, onQualify }) {
  const score = getScore(item);
  const hasDCE = item.dce_resume || item.dce_zip_url;
  const deadline = item.date_limite_remise_plis;
  const publicationDate = item.date_publication;
  const daysLeft = deadline ? Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24)) : null;
  const isUrgent = daysLeft !== null && daysLeft <= 7 && daysLeft >= 0;
  const isExpired = daysLeft !== null && daysLeft < 0;
  const buyer = item.acheteur_public || '—';
  const location = item.lieu_execution || '—';
  const isElectronic = item.reponse_electronique_obligatoire;
  const hasBP = item.bp_extraction_status === 'completed';
  const qStatus = item.qualification_status || 'unseen';

  const truncatedTitle = truncateTitleBeforeDots(item.objet || item.title || 'Untitled');
  const formattedPubDate = formatPublicationDate(publicationDate);
  const truncatedBuyer = truncateText(buyer, 30);
  const truncatedLocation = truncateText(location, 25);

  const handleQualifyClick = (e) => {
    e.stopPropagation();
    const cycle = { unseen: 'preselected', preselected: 'qualified', qualified: 'seen', seen: 'unseen' };
    const next = cycle[qStatus] || 'unseen';
    onQualify(item.reference, next);
  };

  return (
    <button onClick={onClick}
      className={`w-full text-left transition-all duration-200 group relative bg-white rounded-2xl border overflow-hidden hover:shadow-md ${
        active ? 'border-[#2563EB] shadow-lg shadow-[#2563EB]/10 scale-[1.01] z-10 ring-1 ring-[#2563EB]/10'
          : 'border-[#E2E8F0] shadow-sm hover:border-[#CBD5E1]'
      } ${item.status === 'ignored' ? 'opacity-40 hover:opacity-60' : ''}`}>
      {active && <div className="absolute left-0 top-0 bottom-0 w-1 bg-[#2563EB]" />}
      <div className="px-5 py-4">
        <div className="flex items-center gap-4">
          <button onClick={handleQualifyClick} title="Changer le statut" className="flex-shrink-0 hover:scale-105 transition-transform active:scale-95">
            <QualificationIcon status={qStatus} size={24} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5 flex-wrap text-[11px] text-[#64748B]">
                  {item.reference && (
                    <span className="font-medium text-[#2563EB]">{item.reference}</span>
                  )}
                  {item.reference && (buyer !== '—' || location !== '—') && <span>•</span>}
                  {buyer !== '—' && <span title={buyer}>{truncatedBuyer}</span>}
                  {buyer !== '—' && location !== '—' && <span>•</span>}
                  {location !== '—' && <span title={location}>{truncatedLocation}</span>}
                </div>
                <h3 className={`text-[13px] font-semibold leading-snug line-clamp-2 transition-colors duration-200 ${active ? 'text-[#0F172A]' : 'text-[#0F172A] group-hover:text-[#2563EB]'}`}
                    title={item.objet || item.title || 'Untitled'}>
                  {truncatedTitle}
                </h3>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  {item.avis_estimation_ttc && (
                    <span className="cw-mono inline-flex items-center gap-1 text-[11px] font-medium text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded-lg border border-[#BFDBFE]">
                      <DollarSign size={10} />{item.avis_estimation_ttc}
                    </span>
                  )}
                  {hasBP && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#16A34A] bg-[#DCFCE7] px-2 py-0.5 rounded-lg border border-[#BBF7D0]">
                      <Table size={10} />BP
                    </span>
                  )}
                  {item.nombre_references && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#CA8A04] bg-[#FEF9C3]/50 px-2 py-0.5 rounded-lg border border-[#FDE68A]">
                      <FileCheck size={10} />{item.nombre_references} réf.
                    </span>
                  )}
                  {item.classe_qualification && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#475569] bg-[#F1F5F9] px-2 py-0.5 rounded-lg border border-[#CBD5E1]">
                      <Award size={10} />{item.classe_qualification}
                    </span>
                  )}
                  {isElectronic !== null && isElectronic !== undefined && (
                    <span className={`inline-flex items-center justify-center w-6 h-6 rounded-lg border ${
                      isElectronic 
                        ? 'text-[#475569] bg-[#F1F5F9] border-[#CBD5E1]' 
                        : 'text-[#475569] bg-[#F8FAFC] border-[#E2E8F0]'
                    }`} title={isElectronic ? 'Soumission électronique' : 'Soumission physique'}>
                      {isElectronic ? <Laptop size={12} /> : <Building2 size={12} />}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <GaugeDial score={score} size={42} thickness={3.5} />
                  <div className="bg-[#F8FAFC] rounded-xl px-3 py-1.5 min-w-[85px]">
                    {formattedPubDate && (
                      <div className="flex items-center gap-1 mb-1">
                        <Calendar size={10} className="text-[#94A3B8] flex-shrink-0" />
                        <span className="text-[10px] font-medium text-[#94A3B8] truncate">{formattedPubDate}</span>
                      </div>
                    )}
                    {deadline && (
                      <div className={`flex items-center gap-1 ${isExpired ? 'opacity-50' : ''}`}>
                        <Clock size={10} className={`flex-shrink-0 ${isUrgent ? 'text-[#DC2626]' : 'text-[#94A3B8]'}`} />
                        <span className={`cw-mono text-[11px] font-semibold ${isUrgent ? 'text-[#DC2626]' : isExpired ? 'text-[#94A3B8] line-through' : 'text-[#475569]'}`}>
                          {isExpired ? 'Expiré' : fmtDate(deadline)}
                        </span>
                      </div>
                    )}
                    {!deadline && !formattedPubDate && <span className="text-[10px] text-[#94A3B8] italic">—</span>}
                  </div>
                  {deadline && daysLeft !== null && !isExpired && (
                    <div className={`rounded-xl px-3 py-1.5 min-w-[55px] text-center ${isUrgent ? 'bg-[#FEE2E2]' : daysLeft <= 3 ? 'bg-[#FEF9C3]/50' : 'bg-[#F8FAFC]'}`}>
                      <div className={`cw-mono text-[15px] font-bold leading-tight ${isUrgent ? 'text-[#DC2626]' : daysLeft <= 3 ? 'text-[#CA8A04]' : 'text-[#475569]'}`}>{daysLeft}</div>
                      <div className={`text-[9px] font-medium uppercase tracking-wide ${isUrgent ? 'text-[#DC2626]' : daysLeft <= 3 ? 'text-[#CA8A04]' : 'text-[#94A3B8]'}`}>jour{daysLeft > 1 ? 's' : ''}</div>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={item.status} onClick={(e) => { e.stopPropagation(); }} />
                  {hasDCE && (
                    <span className="p-1.5 rounded-xl bg-[#DCFCE7]" title="DCE Available">
                      <FileText size={13} className="text-[#16A34A]" />
                    </span>
                  )}
                </div>
                <ChevronRight size={18} className={`transition-all duration-200 ${active ? 'text-[#2563EB] translate-x-1' : 'text-[#CBD5E1] group-hover:text-[#2563EB] group-hover:translate-x-1'}`} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}

function TenderSidePanelContent({ item, onClose, onStatusChange, onQualify, itemType }) {
  const score = getScore(item);
  const tenderId = item.reference || item.id;
  const [showZipModal, setShowZipModal] = useState(false);
  const [showBPModal, setShowBPModal] = useState(false);
  const deadline = item.date_limite_remise_plis;
  const daysLeft = deadline ? Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24)) : null;
  const isUrgent = daysLeft !== null && daysLeft <= 7 && daysLeft >= 0;
  const isExpired = daysLeft !== null && daysLeft < 0;
  const hasBP = item.bp_extraction_status === 'completed';
  const qStatus = item.qualification_status || 'unseen';

  const cycleStatus = async () => {
    const cycle = { new: 'contacted', contacted: 'ignored', ignored: 'new' };
    const next = cycle[item.status] || 'new';
    try {
      const ep = itemType === 'supplier' ? 'suppliers' : itemType === 'sector' ? 'sectors' : 'tenders';
      const id = item.reference || item.id;
      await fetch(`${API_URL}/${ep}/${id}/status?status=${next}`, { method: 'PUT', headers: authHeaders() });
      onStatusChange(id, next);
    } catch (e) { console.error(e); }
  };

  const handleQualifyClick = async (status) => {
    try {
      await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderId)}/qualify?status=${status}`, { method: 'PUT', headers: authHeaders() });
      onQualify(tenderId, status);
    } catch (e) { console.error(e); }
  };

  const otherFields = [
    { icon: Building2, label: 'Acheteur public', value: item.acheteur_public },
    { icon: Target, label: "Lieu d'exécution", value: item.lieu_execution },
    { icon: FileText, label: 'Procédure', value: item.procedure },
    { icon: Tag, label: 'Catégorie', value: item.categorie },
    { icon: Calendar, label: 'Date publication', value: item.date_publication ? new Date(item.date_publication).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : null },
    { icon: Monitor, label: 'Soumission électronique', value: item.reponse_electronique_obligatoire },
  ].filter(f => f.value !== null && f.value !== undefined && f.value !== '');

  const administrativeFields = [
    { icon: Shield, label: 'Attestations demandées', value: item.attestations_demandees },
    { icon: FileCheck, label: 'Types attestations', value: item.types_attestations },
    { icon: HashIcon, label: 'Nombre références', value: item.nombre_references },
    { icon: Award, label: 'Classe qualification', value: item.classe_qualification },
  ].filter(f => f.value !== null && f.value !== undefined);

  const financialFields = [
    { icon: DollarSign, label: "Chiffre d'affaires", value: item.chiffre_affaires },
    { icon: FileCheck, label: 'Déclaration honneur', value: item.declaration_honneur },
    { icon: Shield, label: 'Caution provisoire', value: item.caution_provisoire },
    { icon: Users, label: 'Note moyens humains', value: item.note_moyens_humains },
    { icon: BarChart3, label: 'Attestations CA', value: item.attestations_ca },
    { icon: Briefcase, label: 'Attestations référence', value: item.attestations_reference },
  ].filter(f => f.value !== null && f.value !== undefined);

  const technicalFields = [
    { icon: Truck, label: 'Dépôt prospectus', value: item.depot_prospectus },
    { icon: BarChart3, label: 'Plan de charge', value: item.plan_charge },
    { icon: Users, label: 'Moyens humains/tech.', value: item.moyens_humains_techniques },
    { icon: Wrench, label: 'Méthodologie travail', value: item.methodologie_travail },
    { icon: PenTool, label: 'Mémoire technique', value: item.memoire_technique },
    { icon: Beaker, label: 'Échantillon/prototype', value: item.echantillon },
    { icon: ClipboardList, label: "Acte d'engagement", value: item.acte_engagement },
    { icon: FileText, label: 'Bordereau des prix', value: item.bordereau_prix },
  ].filter(f => f.value !== null && f.value !== undefined);

  return (
    <>
      <div className="sticky top-0 bg-white/95 backdrop-blur-sm z-10">
        <div className="h-1 bg-[#2563EB]" />
        <div className="flex items-start justify-between gap-4 p-6 border-b border-[#E2E8F0]">
          <div className="flex items-start gap-4 min-w-0">
            <GaugeDial score={score} size={60} thickness={4.5} />
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-semibold text-[#0F172A] leading-snug mb-2">
                {item.objet || item.title || 'Untitled'}
              </h2>
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge status={item.status} onClick={cycleStatus} />
                {isUrgent && (
                  <span className="cw-mono inline-flex items-center gap-1 px-3 py-1 rounded-xl bg-[#FEE2E2] text-[11px] font-semibold text-[#DC2626]">
                    <Clock size={11} /> {daysLeft} days left
                  </span>
                )}
                {isExpired && (
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-xl bg-[#F1F5F9] text-[11px] font-semibold text-[#94A3B8]">Expired</span>
                )}
                {(qStatus === 'unseen' || qStatus === 'seen') && (
                  <button onClick={() => handleQualifyClick('preselected')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-amber-50 text-amber-600 border border-amber-200 hover:bg-amber-100 transition-all shadow-sm">
                    <Star size={12} />Présélectionner
                  </button>
                )}
                {qStatus === 'preselected' && (
                  <>
                    <button onClick={() => handleQualifyClick('qualified')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 transition-all shadow-sm">
                      <UserCheck size={12} />Qualifier
                    </button>
                    <button onClick={() => handleQualifyClick('seen')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-red-50 text-red-500 border border-red-200 hover:bg-red-100 transition-all shadow-sm">
                      <RotateCcw size={12} />Annuler présélection
                    </button>
                  </>
                )}
                {qStatus === 'qualified' && (
                  <button onClick={() => handleQualifyClick('seen')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold bg-red-50 text-red-500 border border-red-200 hover:bg-red-100 transition-all shadow-sm">
                    <RotateCcw size={12} />Annuler qualification
                  </button>
                )}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="flex-shrink-0 p-2 text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl transition-all duration-200">
            <X size={20} />
          </button>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {item.dce_zip_url && (
          <div className="p-5 bg-[#EFF6FF] rounded-2xl border border-[#BFDBFE]">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center shadow-sm flex-shrink-0">
                <FileArchive size={18} className="text-[#2563EB]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[#0F172A]">Full DCE Available</p>
                <p className="text-xs text-[#64748B]">Download complete tender documents</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setShowZipModal(true)} className="flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl text-sm font-medium text-[#0F172A] bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] transition-all duration-200 shadow-sm">
                <Eye size={15} /> Browse files
              </button>
              <a href={item.dce_zip_url} target="_blank" rel="noopener noreferrer" className="flex-1 flex items-center justify-center gap-1.5 px-4 py-3 rounded-xl text-sm font-medium text-white bg-[#111827] hover:bg-[#1E293B] transition-all duration-200 shadow-sm">
                <Download size={15} /> Download
              </a>
            </div>
            {hasBP && (
              <div className="mt-3 pt-3 border-t border-[#BFDBFE]">
                <button onClick={() => setShowBPModal(true)} className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium text-[#16A34A] bg-[#DCFCE7] border border-[#BBF7D0] hover:bg-[#BBF7D0] transition-all duration-200 shadow-sm active:scale-[0.98]">
                  <Table size={15} />View Bordereau des Prix (BP)<ChevronRight size={15} />
                </button>
              </div>
            )}
          </div>
        )}

        {showZipModal && <ZipViewerModal tenderId={tenderId} tenderTitle={item.objet || item.title} onClose={() => setShowZipModal(false)} />}
        {showBPModal && <BPItemsModal tenderReference={tenderId} onClose={() => setShowBPModal(false)} />}

        {hasBP && !item.dce_zip_url && (
          <div className="p-5 bg-[#DCFCE7] rounded-2xl border border-[#BBF7D0]">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center shadow-sm flex-shrink-0">
                <Table size={18} className="text-[#16A34A]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-[#0F172A]">Bordereau des Prix Available</p>
                <p className="text-xs text-[#64748B]">View extracted price schedule</p>
              </div>
            </div>
            <button onClick={() => setShowBPModal(true)} className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium text-white bg-[#16A34A] hover:bg-[#15803D] transition-all duration-200 shadow-sm active:scale-[0.98]">
              <Table size={15} />View Bordereau des Prix<ChevronRight size={15} />
            </button>
          </div>
        )}

        <div>
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-xl bg-[#EFF6FF] flex items-center justify-center">
              <FileText size={15} className="text-[#2563EB]" />
            </div>
            <h3 className="font-semibold text-base text-[#0F172A]">Key Information</h3>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <InfoCard icon={HashIcon} label="Référence" value={item.reference} color="#2563EB" />
            <InfoCard icon={DollarSign} label="Estimation TTC" value={item.avis_estimation_ttc} color="#2563EB" />
            <div className="bg-white rounded-2xl border border-[#E2E8F0] p-4 shadow-sm col-span-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl flex items-center justify-center bg-[#FEE2E2]">
                  <Clock size={14} className="text-[#DC2626]" />
                </div>
                <div>
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Date limite</span>
                  <p className="text-sm font-semibold text-[#0F172A] cw-mono">{item.date_limite_remise_plis ? fmtDate(item.date_limite_remise_plis) : '—'}</p>
                </div>
              </div>
            </div>
            <InfoCard icon={FileCheck} label="Nb Références" value={item.nombre_references} color="#CA8A04" />
            <InfoCard icon={Award} label="Classe qualification" value={item.classe_qualification} color="#475569" />
          </div>

          {otherFields.length > 0 && (
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden mb-4">
              <div className="px-4 py-3 bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">General Information</p>
              </div>
              <div className="p-2">{otherFields.map((f, i) => <DetailField key={i} {...f} />)}</div>
            </div>
          )}
          {administrativeFields.length > 0 && (
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden mb-4">
              <div className="px-4 py-3 bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Administrative</p>
              </div>
              <div className="p-2">{administrativeFields.map((f, i) => <DetailField key={i} {...f} />)}</div>
            </div>
          )}
          {financialFields.length > 0 && (
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden mb-4">
              <div className="px-4 py-3 bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Financial</p>
              </div>
              <div className="p-2">{financialFields.map((f, i) => <DetailField key={i} {...f} />)}</div>
            </div>
          )}
          {technicalFields.length > 0 && (
            <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-sm overflow-hidden mb-4">
              <div className="px-4 py-3 bg-[#F8FAFC] border-b border-[#E2E8F0]">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-[#64748B]">Technical</p>
              </div>
              <div className="p-2">{technicalFields.map((f, i) => <DetailField key={i} {...f} />)}</div>
            </div>
          )}
        </div>

        {item.source_url && (
          <div className="border-t border-[#E2E8F0] pt-4">
            <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-3 bg-white border border-[#E2E8F0] text-[#475569] rounded-2xl text-xs font-medium hover:bg-[#F8FAFC] hover:text-[#0F172A] transition-all duration-200 shadow-sm">
              <ExternalLink size={13} /> View original source
            </a>
          </div>
        )}
      </div>
    </>
  );
}

function TenderSidePanel({ item, onClose, onStatusChange, onQualify, itemType }) {
  const [visible, setVisible] = useState(false);
  const handleClose = useCallback(() => { setVisible(false); setTimeout(onClose, 200); }, [onClose]);
  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    const onKey = (e) => { if (e.key === 'Escape') handleClose(); };
    document.addEventListener('keydown', onKey);
    return () => {
      cancelAnimationFrame(id);
      document.removeEventListener('keydown', onKey);
    };
  }, [handleClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div onClick={handleClose} className={`absolute inset-0 bg-[#0F172A]/40 backdrop-blur-sm transition-opacity duration-200 ${visible ? 'opacity-100' : 'opacity-0'}`} />
      <div className={`relative w-full sm:w-[520px] lg:w-[600px] bg-[#F8FAFC] h-full shadow-2xl overflow-y-auto transition-all duration-200 ease-out ${visible ? 'translate-x-0' : 'translate-x-4 opacity-0'}`}>
        {item && <TenderSidePanelContent item={item} onClose={handleClose} onStatusChange={onStatusChange} onQualify={onQualify} itemType={itemType} />}
      </div>
    </div>
  );
}

const POLL_ACTIVE = 10000;
const POLL_IDLE = 60000;

export default function Tenders({ showOnlyPreselected = false }) {
  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [qualificationFilters, setQualificationFilters] = useState([]);
  const [search, setSearch] = useState('');
  const [lastScan, setLastScan] = useState(null);
  const [selected, setSelected] = useState(null);
  const [deadlineSort, setDeadlineSort] = useState('default');
  const [keywords, setKeywords] = useState([]);
  const [showKeywordManager, setShowKeywordManager] = useState(false);
  const [useKeywordFilter, setUseKeywordFilter] = useState(false);

  const pollingRef = useRef(null);
  const prevCount = useRef(0);

  const apiEndpoint = showOnlyPreselected ? `${API_URL}/tenders/preselected` : `${API_URL}/tenders`;

  const fetchAll = useCallback(async (showLoad = true) => {
    if (showLoad) setLoading(true);
    try {
      const tR = await fetch(apiEndpoint, { headers: authHeaders() });
      const tD = await tR.json();
      const nt = tD.tenders || [];
      const filteredTenders = showOnlyPreselected 
        ? nt.filter(t => t.qualification_status === 'preselected' || t.qualification_status === 'qualified')
        : nt;
      const total = filteredTenders.length;
      if (total > prevCount.current && prevCount.current > 0) console.log(`[Poll] ${total - prevCount.current} new items`);
      prevCount.current = total;
      setTenders(filteredTenders);
    } catch (e) { console.error(e); }
    if (showLoad) setLoading(false);
  }, [apiEndpoint, showOnlyPreselected]);

  const fetchKeywords = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/keywords`, { headers: authHeaders() });
      const data = await response.json();
      if (data.success) setKeywords(data.keywords || []);
    } catch (error) { console.error('Error fetching keywords:', error); }
  }, []);

  const addKeyword = async (keyword) => {
    try {
      const response = await fetch(`${API_URL}/keywords`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword, category: 'custom', is_active: true })
      });
      const data = await response.json();
      if (data.success) await fetchKeywords();
    } catch (error) { console.error(error); }
  };

  const deleteKeyword = async (keywordId) => {
    try { await fetch(`${API_URL}/keywords/${keywordId}`, { method: 'DELETE', headers: authHeaders() }); await fetchKeywords(); }
    catch (error) { console.error(error); }
  };

  const toggleKeyword = async (keywordId, isActive) => {
    try {
      await fetch(`${API_URL}/keywords/${keywordId}`, {
        method: 'PATCH',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: isActive })
      });
      await fetchKeywords();
    } catch (error) { console.error(error); }
  };

  const markAsSeen = async (tenderRef) => {
    setTenders(prev => prev.map(t => t.reference === tenderRef ? { ...t, seen: true, qualification_status: t.qualification_status === 'unseen' ? 'seen' : t.qualification_status } : t));
    try { await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderRef)}/seen`, { method: 'PUT', headers: authHeaders() }); }
    catch (e) { console.error('Failed to mark as seen:', e); }
  };

  const handleQualify = async (tenderRef, newStatus) => {
    setTenders(prev => prev.map(t => t.reference === tenderRef ? { ...t, qualification_status: newStatus } : t));
    if (selected && (selected.reference || selected.id) === tenderRef) setSelected(p => ({ ...p, qualification_status: newStatus }));
    try { await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderRef)}/qualify?status=${newStatus}`, { method: 'PUT', headers: authHeaders() }); }
    catch (e) { console.error('Failed to update qualification:', e); }
  };

  useEffect(() => {
    fetchAll();
    fetchKeywords();
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, [fetchAll, fetchKeywords]);

  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(() => fetchAll(false), scanning ? POLL_ACTIVE : POLL_IDLE);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  }, [scanning, fetchAll]);

  const handleScan = async () => {
    setScanning(true);
    try {
      const r = await fetch(`${API_URL}/tenders/scan`, { method: 'POST', headers: authHeaders() });
      const d = await r.json();
      if (d.success) setLastScan(new Date());
    } catch { }
    setTimeout(() => setScanning(false), 30000);
  };

  const handleStatusChange = (id, newStatus) => {
    setTenders(prev => prev.map(t => (t.reference || t.id) === id ? { ...t, status: newStatus } : t));
    if (selected && (selected.reference || selected.id) === id) setSelected(p => ({ ...p, status: newStatus }));
  };

  const clearAllFilters = () => {
    setQualificationFilters([]);
    setUseKeywordFilter(false);
    setDeadlineSort('default');
  };

  const toggleQualificationFilter = (status) => {
    setQualificationFilters(prev => prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]);
  };

  const sortItems = useCallback((items) => {
    return [...items].sort((a, b) => {
      if (deadlineSort === 'nearest') {
        const da = a.date_limite_remise_plis ? new Date(a.date_limite_remise_plis).getTime() : Infinity;
        const db = b.date_limite_remise_plis ? new Date(b.date_limite_remise_plis).getTime() : Infinity;
        if (da !== db) return da - db;
      }
      const sb = getScore(b), sa = getScore(a);
      if (sb !== sa) return sb - sa;
      const da = a.date_limite_remise_plis ? new Date(a.date_limite_remise_plis).getTime() : Infinity;
      const db = b.date_limite_remise_plis ? new Date(b.date_limite_remise_plis).getTime() : Infinity;
      return da - db;
    });
  }, [deadlineSort]);

  const filterItems = useCallback((items) => {
    let f = items;
    if (qualificationFilters.length > 0) f = f.filter(t => qualificationFilters.includes(t.qualification_status || 'unseen'));
    if (search) {
      const q = search.toLowerCase();
      f = f.filter(t => (t.objet || t.title || '').toLowerCase().includes(q) || (t.lieu_execution || '').toLowerCase().includes(q) || (t.acheteur_public || '').toLowerCase().includes(q) || (t.reference || '').toLowerCase().includes(q));
    }
    if (useKeywordFilter && keywords.length > 0) {
      const activeKeywords = keywords.filter(k => k.is_active).map(k => k.keyword);
      if (activeKeywords.length > 0) {
        f = f.filter(tender => {
          const txt = [tender.objet || '', tender.acheteur_public || '', tender.lieu_execution || '', tender.categorie || '', tender.procedure || '', tender.reference || ''].join(' ').toLowerCase()
            .replace(/[éèêë]/g, 'e').replace(/[àâä]/g, 'a').replace(/[ùûü]/g, 'u').replace(/[ôö]/g, 'o').replace(/[îï]/g, 'i').replace(/ç/g, 'c');
          return activeKeywords.some(kw => txt.includes(kw.toLowerCase().replace(/[éèêë]/g, 'e').replace(/[àâä]/g, 'a').replace(/[ùûü]/g, 'u').replace(/[ôö]/g, 'o').replace(/[îï]/g, 'i').replace(/ç/g, 'c')));
        });
      }
    }
    return sortItems(f);
  }, [qualificationFilters, search, useKeywordFilter, keywords, sortItems]);

  const current = filterItems(tenders);
  const isAllQuick = qualificationFilters.length === 0 && !useKeywordFilter && deadlineSort === 'default';
  const activeKeywordCount = keywords.filter(k => k.is_active).length;
  const handleSelectTender = (item) => { setSelected(item); if (!item.seen) markAsSeen(item.reference); };

  return (
    <div className="cw-theme min-h-screen">
      <style>{CW_THEME_STYLE}</style>
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">

        <div className="sticky top-0 z-20 bg-[#F8FAFC]/95 backdrop-blur-sm pb-4 -mt-2 pt-2">
          <div className="bg-white rounded-3xl border border-[#E2E8F0] shadow-sm p-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1 min-w-0">
                <Search size={15} className="absolute left-4 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by title, buyer, location, reference..." className="w-full pl-11 pr-4 py-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl text-sm text-[#0F172A] placeholder-[#94A3B8] focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] focus:bg-white outline-none transition-all" />
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <FilterPill active={isAllQuick} onClick={clearAllFilters} icon={<Filter size={11} />}>Tous</FilterPill>
                <QualificationFilterDropdown selected={qualificationFilters} onToggle={toggleQualificationFilter} onClear={() => setQualificationFilters([])} />
                <FilterPill active={deadlineSort === 'nearest'} onClick={() => setDeadlineSort(prev => prev === 'nearest' ? 'default' : 'nearest')} icon={<Clock size={11} />}>Deadline</FilterPill>
                <FilterPill active={useKeywordFilter} onClick={() => { if (!useKeywordFilter) setShowKeywordManager(true); else setUseKeywordFilter(false); }} icon={<SlidersHorizontal size={11} />}>
                  Mots-clés
                  {useKeywordFilter && activeKeywordCount > 0 && (<span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#2563EB] text-white text-[9px] font-semibold">{activeKeywordCount}</span>)}
                </FilterPill>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between text-[11px] text-[#94A3B8]">
              <span><span className="font-semibold text-[#0F172A] cw-mono">{current.length}</span> appel{current.length !== 1 ? 's' : ''} d'offre{current.length !== 1 ? 's' : ''} trouvé{current.length !== 1 ? 's' : ''}</span>
              {lastScan && (<span className="cw-mono">Dernier scan: {lastScan.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>)}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-32 gap-4">
            <Loader size={28} className="text-[#2563EB] animate-spin" />
            <p className="text-sm font-medium text-[#475569]">Chargement des appels d'offres...</p>
          </div>
        ) : current.length === 0 ? (
          <div className="bg-white rounded-3xl border border-[#E2E8F0] shadow-sm">
            <div className="flex flex-col items-center text-center py-20 px-4">
              <Globe size={28} className="text-[#94A3B8] mb-4" />
              <h3 className="text-lg font-semibold text-[#0F172A] mb-2">Aucun appel d'offre trouvé</h3>
              <p className="text-sm text-[#475569] max-w-md mb-6">{tenders.length === 0 ? "Vous n'avez pas encore découvert d'appels d'offres. Lancez votre premier scan." : "Aucun appel d'offre ne correspond à vos filtres."}</p>
              {tenders.length === 0 ? (
                <button onClick={handleScan} disabled={scanning} className="flex items-center gap-2 px-6 py-3 rounded-2xl font-medium text-sm text-white bg-[#111827] hover:bg-[#1E293B] disabled:opacity-50 transition-all duration-200 shadow-sm active:scale-95"><Zap size={14} /> Lancer le scan</button>
              ) : (
                <button onClick={clearAllFilters} className="flex items-center gap-2 px-6 py-3 rounded-2xl font-medium text-sm text-[#0F172A] bg-white border border-[#E2E8F0] hover:bg-[#F8FAFC] transition-all duration-200 shadow-sm">Effacer les filtres</button>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {current.map(item => (
              <TenderCard key={item.reference || item.id} item={item} active={selected && (selected.reference || selected.id) === (item.reference || item.id)} onClick={() => handleSelectTender(item)} onQualify={handleQualify} />
            ))}
          </div>
        )}
      </div>

      {selected && (
        <TenderSidePanel item={selected} itemType="tender" onClose={() => setSelected(null)} onStatusChange={handleStatusChange} onQualify={handleQualify} />
      )}

      <KeywordManager isOpen={showKeywordManager} onClose={() => { setShowKeywordManager(false); if (keywords.filter(k => k.is_active).length === 0) setUseKeywordFilter(false); }} keywords={keywords} onAdd={async (keyword) => { await addKeyword(keyword); setUseKeywordFilter(true); }} onDelete={deleteKeyword} onToggle={toggleKeyword} />
    </div>
  );
}