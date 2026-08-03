import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search, RefreshCw, Globe, Building2,
  ExternalLink, CheckCircle,
  Loader, Zap,
  Activity,
  Download, FileArchive, Wifi, WifiOff,
  X, Target, Calendar, Clock,
  Info, Monitor,
  Plus, Trash2, Tag, Filter, SlidersHorizontal, FileText, Check,
  ChevronRight, MapPin, Shield, Users,
  DollarSign, FileCheck, Briefcase, ClipboardList,
  Truck, Wrench, Beaker, PenTool,
  BarChart3, Award, Eye, Hash, Laptop,
  Table, ChevronDown, ChevronUp, Star, UserCheck, AlertTriangle,
  RotateCcw,
} from 'lucide-react';
import {
  API_URL, authHeaders, STATUS_MAP, fmtDate, getScore,
} from './tenderUtils';
import ZipViewerModal from './ZipViewerModal';

// ═══════════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════════
const CW_THEME_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
  .cw-theme { font-family: 'Space Grotesk', ui-sans-serif, sans-serif; }
  .cw-serif { font-family: 'Newsreader', serif; }
  .cw-mono { font-family: 'IBM Plex Mono', monospace; }
`;

const HashIcon = (props) => (
  <span {...props} style={{ fontSize: '14px', fontWeight: 'bold', lineHeight: 1 }}>#</span>
);

// ═══════════════════════════════════════════════════════════
// QUALIFICATION ICON
// ═══════════════════════════════════════════════════════════
function QualificationIcon({ status, size = 20 }) {
  const colors = {
    unseen: { bg: '#F1F6F5', fg: '#9BB5B1' },
    seen: { bg: '#EEF4F3', fg: '#7FA09B' },
    preselected: { bg: '#FFF8EB', fg: '#C7913F' },
    qualified: { bg: '#E9F5EF', fg: '#1F6B4C' },
  };
  const c = colors[status] || colors.unseen;
  
  return (
    <div 
      className="relative flex-shrink-0 rounded-full flex items-center justify-center font-bold text-[10px] cw-mono shadow-sm"
      style={{ 
        width: size + 4, 
        height: size + 4, 
        backgroundColor: c.bg, 
        color: c.fg,
        border: `2px solid ${c.fg}20`
      }}
    >
      {status === 'preselected' && <Star size={size - 4} style={{ color: c.fg }} />}
      {status === 'qualified' && <UserCheck size={size - 4} style={{ color: c.fg }} />}
      {(status === 'unseen' || status === 'seen') && <Eye size={size - 4} style={{ color: c.fg }} />}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// SIGNATURE ELEMENT
// ═══════════════════════════════════════════════════════════
function GaugeDial({ score, size = 44, thickness = 4 }) {
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const band = score >= 70 ? '#0E93A1' : score >= 45 ? '#C7913F' : '#7FA09B';
  const cx = size / 2, cy = size / 2;
  const ticks = Array.from({ length: 20 });
  return (
    <div className="relative flex-shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g opacity="0.5">
          {ticks.map((_, i) => {
            const angle = (i / ticks.length) * 2 * Math.PI;
            const x1 = cx + Math.cos(angle) * (r + thickness / 2 + 1);
            const y1 = cy + Math.sin(angle) * (r + thickness / 2 + 1);
            const x2 = cx + Math.cos(angle) * (r + thickness / 2 + 3);
            const y2 = cy + Math.sin(angle) * (r + thickness / 2 + 3);
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#DCE8E5" strokeWidth="1" />;
          })}
        </g>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#EFF5F3" strokeWidth={thickness} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={band}
          strokeWidth={thickness} strokeDasharray={`${c * pct} ${c}`} strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="cw-mono font-semibold" style={{ fontSize: size * 0.3, color: band }}>{score}</span>
      </div>
    </div>
  );
}

function StatusBadge({ status, onClick }) {
  if (status === 'new') return null;
  const c = STATUS_MAP[status] || STATUS_MAP.new;
  return (
    <button onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold transition-all duration-200 hover:scale-105 active:scale-95 hover:shadow-sm ${c.bg} ${c.text} border ${c.ring}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />{c.label}
    </button>
  );
}

function FilterPill({ active, onClick, children, icon }) {
  return (
    <button onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold border transition-all duration-200 whitespace-nowrap hover:shadow-md active:scale-95 ${
        active
          ? 'bg-[#123338] border-[#123338] text-white shadow-lg shadow-[#123338]/20'
          : 'bg-white border-[#DCE8E5] text-[#4F6E69] hover:bg-[#F7FAF9] hover:border-[#123338]/30 hover:shadow-sm'
      }`}>
      {icon}{children}
    </button>
  );
}

function InfoCard({ icon: Icon, label, value, color = '#0E93A1' }) {
  return (
    <div className="bg-white rounded-xl border border-[#DCE8E5] p-3 shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex items-center gap-2 mb-1.5">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15` }}>
          <Icon size={14} style={{ color }} />
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider text-[#7FA09B]">{label}</span>
      </div>
      <p className="text-sm font-bold text-[#123338] truncate cw-mono">{value || '—'}</p>
    </div>
  );
}

function DetailField({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between py-2.5 px-2 border-b border-[#DCE8E5] last:border-b-0 hover:bg-[#F7FAF9]/60 rounded-lg transition-colors duration-150">
      <div className="flex items-center gap-2.5 min-w-0 flex-1">
        <div className="w-7 h-7 rounded-lg bg-[#F7FAF9] flex items-center justify-center flex-shrink-0 shadow-sm">
          <Icon size={13} className="text-[#4F6E69]" />
        </div>
        <span className="text-xs text-[#4F6E69] truncate font-medium">{label}</span>
      </div>
      <div className="flex-shrink-0 ml-3">
        {typeof value === 'boolean' ? (
          value ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#E9F5EF] text-[11px] font-bold text-[#1F6B4C] shadow-sm">
              <CheckCircle size={10} className="text-[#2F8F66]" /> Yes
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#FBEAE6] text-[11px] font-bold text-[#A6432A] shadow-sm">
              <X size={10} className="text-[#D6572E]" /> No
            </span>
          )
        ) : value && value !== '—' ? (
          <span className="text-xs font-bold text-[#123338] text-right max-w-[180px] truncate cw-mono">{value}</span>
        ) : (
          <span className="text-xs text-[#9BB5B1] italic">—</span>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// QUALIFICATION FILTER DROPDOWN
// ═══════════════════════════════════════════════════════════
const QUALIFICATION_OPTIONS = [
  { value: 'preselected', label: 'Présélectionnés', icon: Star, color: '#C7913F' },
  { value: 'qualified', label: 'Qualifiés', icon: UserCheck, color: '#1F6B4C' },
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
        className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold border transition-all duration-200 whitespace-nowrap hover:shadow-md active:scale-95 ${
          activeCount > 0
            ? 'bg-[#123338] border-[#123338] text-white shadow-lg shadow-[#123338]/20'
            : 'bg-white border-[#DCE8E5] text-[#4F6E69] hover:bg-[#F7FAF9] hover:border-[#123338]/30 hover:shadow-sm'
        }`}>
        <Filter size={11} />
        Statut
        {activeCount > 0 && (
          <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-white/20 text-white text-[9px] font-bold">{activeCount}</span>
        )}
        <ChevronDown size={11} className={`transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded-xl border border-[#DCE8E5] shadow-xl shadow-[#123338]/10 z-30 overflow-hidden">
          <div className="p-2 space-y-1">
            {QUALIFICATION_OPTIONS.map(opt => {
              const Icon = opt.icon;
              const isActive = selected.includes(opt.value);
              return (
                <button key={opt.value} onClick={() => onToggle(opt.value)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all ${
                    isActive ? 'bg-[#F7FAF9] text-[#123338]' : 'text-[#4F6E69] hover:bg-[#F7FAF9] hover:text-[#123338]'
                  }`}>
                  <Icon size={13} style={{ color: isActive ? opt.color : '#9BB5B1' }} />
                  <span className="flex-1 text-left">{opt.label}</span>
                  {isActive && <Check size={13} className="text-[#0E93A1]" strokeWidth={3} />}
                </button>
              );
            })}
          </div>
          {activeCount > 0 && (
            <div className="border-t border-[#DCE8E5] p-1.5">
              <button onClick={() => { onClear(); setIsOpen(false); }}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold text-[#9BB5B1] hover:text-[#D6572E] hover:bg-red-50 transition-all">
                <X size={11} />Effacer les filtres
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// KEYWORD MANAGER
// ═══════════════════════════════════════════════════════════
function KeywordManager({ isOpen, onClose, keywords, onAdd, onDelete, onToggle }) {
  const [newKeyword, setNewKeyword] = useState('');
  const [error, setError] = useState('');
  const handleAdd = () => { if (!newKeyword.trim()) { setError('Keyword cannot be empty'); return; } onAdd(newKeyword.trim()); setNewKeyword(''); setError(''); };
  if (!isOpen) return null;
  const activeCount = keywords.filter(k => k.is_active).length;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#123338]/30 backdrop-blur-md">
      <div className="bg-white rounded-2xl shadow-2xl shadow-[#123338]/10 w-full max-w-lg mx-4 overflow-hidden border border-[#DCE8E5] transform transition-all duration-300 scale-100">
        <div className="p-5 border-b border-[#DCE8E5] bg-gradient-to-b from-[#F7FAF9] to-[#F1F6F5]"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#0E93A1] to-[#0C7C88] flex items-center justify-center shadow-lg shadow-[#0E93A1]/20"><Tag size={18} className="text-white" /></div><div><h3 className="font-bold text-[#123338] cw-serif text-base">Filter Keywords</h3><p className="text-xs text-[#7FA09B]">{activeCount} active · {keywords.length} total</p></div></div><button onClick={onClose} className="p-2 text-[#7FA09B] hover:text-[#123338] hover:bg-white rounded-lg transition-colors shadow-sm"><X size={18} /></button></div></div>
        <div className="p-5 border-b border-[#DCE8E5] bg-white"><div className="flex gap-2"><input type="text" value={newKeyword} onChange={(e) => { setNewKeyword(e.target.value); setError(''); }} onKeyPress={(e) => e.key === 'Enter' && handleAdd()} placeholder="Add a keyword..." className="flex-1 px-4 py-2.5 text-sm border border-[#DCE8E5] rounded-xl focus:ring-2 focus:ring-[#0E93A1]/20 focus:border-[#0E93A1] outline-none text-[#123338] placeholder-[#9BB5B1] shadow-sm" /><button onClick={handleAdd} className="px-5 py-2.5 bg-[#0E93A1] text-white rounded-xl text-sm font-bold hover:bg-[#0C7C88] transition-all duration-200 active:scale-95 flex items-center gap-1.5 flex-shrink-0 shadow-lg shadow-[#0E93A1]/20 hover:shadow-xl hover:shadow-[#0E93A1]/30"><Plus size={15} /> Add</button></div>{error && <p className="flex items-center gap-1.5 mt-2 text-xs text-[#D6572E]"><AlertTriangle size={12} /> {error}</p>}</div>
        <div className="max-h-72 overflow-y-auto">{keywords.length === 0 ? (<div className="p-10 text-center"><div className="w-12 h-12 rounded-2xl bg-[#F1F6F5] flex items-center justify-center mx-auto mb-3 shadow-sm"><Tag size={22} className="text-[#7FA09B]" /></div><p className="text-sm font-bold text-[#4F6E69]">No keywords yet</p><p className="text-xs text-[#9BB5B1] mt-1">Add keywords to filter tenders</p></div>) : (<div className="divide-y divide-[#DCE8E5]">{keywords.map((kw) => (<div key={kw.id} className="flex items-center justify-between px-5 py-3.5 hover:bg-[#F7FAF9] transition-colors duration-150"><div className="flex items-center gap-3 flex-1 min-w-0"><button onClick={() => onToggle(kw.id, !kw.is_active)} className={`flex-shrink-0 w-5 h-5 rounded-lg border-2 transition-all duration-200 flex items-center justify-center hover:shadow-sm ${kw.is_active ? 'bg-[#0E93A1] border-[#0E93A1] shadow-sm shadow-[#0E93A1]/20' : 'border-[#C3D6D2] hover:border-[#0E93A1]/40'}`}>{kw.is_active && <Check size={12} className="text-white" strokeWidth={3} />}</button><span className={`text-sm truncate font-medium transition-colors ${kw.is_active ? 'text-[#123338]' : 'text-[#9BB5B1]'}`}>{kw.keyword}</span></div><button onClick={() => onDelete(kw.id)} className="p-1.5 text-[#9BB5B1] hover:text-[#D6572E] hover:bg-[#FBEAE6] rounded-lg transition-all duration-200 ml-2 hover:shadow-sm"><Trash2 size={14} /></button></div>))}</div>)}</div>
        <div className="p-4 border-t border-[#DCE8E5] bg-[#F7FAF9]"><button onClick={onClose} className="w-full py-2.5 bg-[#123338] text-white rounded-xl text-sm font-bold hover:bg-[#0D2A2E] transition-all duration-200 active:scale-[0.98] shadow-lg shadow-[#123338]/10 hover:shadow-xl hover:shadow-[#123338]/20">Done</button></div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// BP ITEMS MODAL
// ═══════════════════════════════════════════════════════════
function BPItemsModal({ tenderReference, onClose }) {
  const [bpData, setBpData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedItems, setExpandedItems] = useState({});
  const [showAll, setShowAll] = useState(false);
  const fetchBPData = useCallback(async () => {
    try { setLoading(true); const response = await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderReference)}/bp-items`, { headers: authHeaders() }); if (!response.ok) throw new Error('Failed to fetch BP data'); const data = await response.json(); setBpData(data); } catch (err) { setError(err.message); } finally { setLoading(false); }
  }, [tenderReference]);
  useEffect(() => { fetchBPData(); }, [fetchBPData]);
  const toggleItem = (id) => setExpandedItems(prev => ({ ...prev, [id]: !prev[id] }));
  const displayItems = showAll ? (bpData?.items || []) : (bpData?.items || []).slice(0, 20);
  const totalItems = bpData?.total_items || bpData?.items?.length || 0;
  const summary = bpData?.summary || {};
  if (loading) return (<div className="fixed inset-0 z-50 flex items-center justify-center bg-[#123338]/30 backdrop-blur-md"><div className="bg-white rounded-2xl shadow-2xl p-8 flex flex-col items-center gap-4"><Loader size={32} className="text-[#0E93A1] animate-spin" /><p className="text-sm font-bold text-[#4F6E69]">Loading BP items...</p></div></div>);
  if (error) return (<div className="fixed inset-0 z-50 flex items-center justify-center bg-[#123338]/30 backdrop-blur-md"><div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md mx-4"><div className="flex items-center gap-3 mb-4"><div className="w-10 h-10 rounded-xl bg-[#FBEAE6] flex items-center justify-center"><AlertTriangle size={20} className="text-[#D6572E]" /></div><div><h3 className="font-bold text-[#123338]">Error Loading BP Data</h3><p className="text-xs text-[#7FA09B]">{error}</p></div></div><button onClick={onClose} className="w-full py-2.5 bg-[#123338] text-white rounded-xl text-sm font-bold hover:bg-[#0D2A2E] transition-all">Close</button></div></div>);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-[#123338]/30 backdrop-blur-md overflow-y-auto py-8">
      <div className="bg-white rounded-2xl shadow-2xl shadow-[#123338]/10 w-full max-w-5xl mx-4 border border-[#DCE8E5]">
        <div className="p-5 border-b border-[#DCE8E5] bg-gradient-to-b from-[#F7FAF9] to-[#F1F6F5] rounded-t-2xl"><div className="flex items-center justify-between"><div className="flex items-center gap-3"><div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#0E93A1] to-[#0C7C88] flex items-center justify-center shadow-lg shadow-[#0E93A1]/20"><Table size={18} className="text-white" /></div><div><h3 className="font-bold text-[#123338] cw-serif text-lg">Bordereau des Prix</h3><p className="text-xs text-[#7FA09B]">{totalItems} items • Total HT: {(summary.total_ht || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} DHS</p></div></div><button onClick={onClose} className="p-2 text-[#7FA09B] hover:text-[#123338] hover:bg-white rounded-lg transition-colors shadow-sm"><X size={20} /></button></div></div>
        <div className="p-5 grid grid-cols-4 gap-3"><div className="bg-[#E6F5F6] rounded-xl p-3 border border-[#BFE2E4]/60"><p className="text-[10px] font-bold text-[#4F6E69] uppercase mb-1">Total Items</p><p className="text-lg font-bold text-[#0E93A1] cw-mono">{totalItems}</p></div><div className="bg-[#FBF3E6] rounded-xl p-3 border border-[#E7D2A8]/60"><p className="text-[10px] font-bold text-[#4F6E69] uppercase mb-1">Total HT</p><p className="text-lg font-bold text-[#C7913F] cw-mono">{(summary.total_ht || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p></div><div className="bg-[#EEF4F3] rounded-xl p-3 border border-[#C7DAD8]/60"><p className="text-[10px] font-bold text-[#4F6E69] uppercase mb-1">Total Quantité</p><p className="text-lg font-bold text-[#4A6B72] cw-mono">{(summary.total_qty || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p></div><div className="bg-[#E9F5EF] rounded-xl p-3 border border-[#9BC8A8]/60"><p className="text-[10px] font-bold text-[#4F6E69] uppercase mb-1">Prix Moyen</p><p className="text-lg font-bold text-[#1F6B4C] cw-mono">{(summary.avg_price || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p></div></div>
        <div className="overflow-x-auto border-t border-[#DCE8E5]"><table className="w-full text-sm"><thead className="bg-[#F7FAF9]"><tr className="border-b border-[#DCE8E5]"><th className="text-left px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider">N° Prix</th><th className="text-left px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider">Désignation</th><th className="text-center px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider">Unité</th><th className="text-right px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider">Quantité</th><th className="text-right px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider">PU HT</th><th className="text-right px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider">Total HT</th><th className="text-center px-4 py-3 text-[10px] font-extrabold text-[#4F6E69] uppercase tracking-wider w-10"></th></tr></thead><tbody className="divide-y divide-[#DCE8E5]">{displayItems.map((item, index) => (<React.Fragment key={item.id || index}><tr className="hover:bg-[#F7FAF9]/50 transition-colors group"><td className="px-4 py-2.5 cw-mono text-xs font-semibold text-[#0E93A1]">{item.n_prix || '—'}</td><td className="px-4 py-2.5 text-xs text-[#123338] max-w-xs"><div className="truncate" title={item.designation}>{item.designation || '—'}</div></td><td className="px-4 py-2.5 text-center text-xs text-[#4F6E69]">{item.unite || '—'}</td><td className="px-4 py-2.5 text-right cw-mono text-xs text-[#123338]">{item.quantite ? parseFloat(item.quantite).toLocaleString('fr-FR') : '—'}</td><td className="px-4 py-2.5 text-right cw-mono text-xs font-semibold text-[#0E93A1]">{item.prix_unitaire_ht ? parseFloat(item.prix_unitaire_ht).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}</td><td className="px-4 py-2.5 text-right cw-mono text-xs font-bold text-[#123338]">{item.total_ht ? parseFloat(item.total_ht).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}</td><td className="px-4 py-2.5 text-center"><button onClick={() => toggleItem(item.id || index)} className="p-1 rounded-lg hover:bg-[#E6F5F6] text-[#7FA09B] hover:text-[#0E93A1] transition-all opacity-0 group-hover:opacity-100">{expandedItems[item.id || index] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></td></tr>{expandedItems[item.id || index] && (<tr className="bg-[#F7FAF9]"><td colSpan={7} className="px-6 py-3"><div className="grid grid-cols-3 gap-3 text-xs">{item.code_ouvrage_peq && <div><span className="text-[#9BB5B1]">Code Ouvrage PEQ:</span><span className="ml-2 font-semibold text-[#123338]">{item.code_ouvrage_peq}</span></div>}{item.code_serie_peq && <div><span className="text-[#9BB5B1]">Code Série PEQ:</span><span className="ml-2 font-semibold text-[#123338]">{item.code_serie_peq}</span></div>}{item.code_prix_peq && <div><span className="text-[#9BB5B1]">Code Prix PEQ:</span><span className="ml-2 font-semibold text-[#123338]">{item.code_prix_peq}</span></div>}<div className="col-span-3"><span className="text-[#9BB5B1]">Désignation complète:</span><p className="mt-1 text-[#123338]">{item.designation}</p></div></div></td></tr>)}</React.Fragment>))}</tbody></table></div>
        {totalItems > 20 && !showAll && (<div className="p-4 border-t border-[#DCE8E5] text-center"><button onClick={() => setShowAll(true)} className="px-4 py-2 bg-white border border-[#DCE8E5] rounded-xl text-sm font-bold text-[#4F6E69] hover:bg-[#F7FAF9] hover:text-[#123338] transition-all shadow-sm">Show all {totalItems} items</button></div>)}
        <div className="p-4 border-t border-[#DCE8E5] bg-[#F7FAF9] rounded-b-2xl"><button onClick={onClose} className="w-full py-2.5 bg-[#123338] text-white rounded-xl text-sm font-bold hover:bg-[#0D2A2E] transition-all shadow-lg">Close</button></div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
// Tender Card
// ═══════════════════════════════════════════════════════════
function TenderCard({ item, active, onClick, onQualify }) {
  const score = getScore(item);
  const hasDCE = item.dce_resume || item.dce_zip_url;
  const deadline = item.date_limite_remise_plis;
  const daysLeft = deadline ? Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24)) : null;
  const isUrgent = daysLeft !== null && daysLeft <= 7 && daysLeft >= 0;
  const isExpired = daysLeft !== null && daysLeft < 0;
  const buyer = item.acheteur_public || '—';
  const location = item.lieu_execution || '—';
  const isElectronic = item.reponse_electronique_obligatoire;
  const hasBP = item.bp_extraction_status === 'completed';
  const qStatus = item.qualification_status || 'unseen';
  const isUnseen = qStatus === 'unseen';

  const handleQualifyClick = (e) => {
    e.stopPropagation();
    const cycle = { unseen: 'preselected', preselected: 'qualified', qualified: 'seen', seen: 'unseen' };
    const next = cycle[qStatus] || 'unseen';
    onQualify(item.reference, next);
  };

  return (
    <button onClick={onClick}
      className={`w-full text-left transition-all duration-300 group relative bg-white rounded-xl border-2 overflow-hidden ${
        active ? 'border-[#123338] shadow-xl shadow-[#123338]/10 scale-[1.01] z-10 ring-1 ring-[#123338]/5'
          : 'shadow-sm hover:shadow-lg hover:shadow-[#123338]/5 hover:border-[#C3D6D2]'
      } ${item.status === 'ignored' ? 'opacity-50 hover:opacity-70' : ''}`}
      style={!active ? { borderColor: isUnseen ? '#9BB5B1' : '#DCE8E5' } : {}}>
      {active && <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-[#0E93A1] to-[#0C7C88]" />}
      <div className="px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={handleQualifyClick} title="Changer le statut" className="flex-shrink-0 hover:scale-110 transition-transform active:scale-95">
            <QualificationIcon status={qStatus} size={24} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h3 className={`cw-serif text-[15px] font-medium leading-snug truncate transition-colors duration-200 ${active ? 'text-[#123338]' : 'text-[#123338] group-hover:text-[#0E93A1]'}`}>{item.objet || item.title || 'Untitled'}</h3>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#4F6E69] bg-[#F7FAF9] px-1.5 py-0.5 rounded border border-[#DCE8E5]/60"><Building2 size={10} className="text-[#7FA09B]" /><span className="truncate max-w-[120px]">{buyer}</span></span>
                  <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#4F6E69] bg-[#F7FAF9] px-1.5 py-0.5 rounded border border-[#DCE8E5]/60"><MapPin size={10} className="text-[#7FA09B]" /><span className="truncate max-w-[100px]">{location}</span></span>
                  {isElectronic !== null && isElectronic !== undefined && (<span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${isElectronic ? 'text-[#4A6B72] bg-[#EEF4F3] border-[#C7DAD8]/60' : 'text-[#4F6E69] bg-[#F7FAF9] border-[#DCE8E5]/60'}`}>{isElectronic ? <Laptop size={10} /> : <Building2 size={10} />}{isElectronic ? 'Électronique' : 'Physique'}</span>)}
                  {item.reference && <span className="cw-mono inline-flex items-center gap-1 text-[10px] font-semibold text-[#0E93A1] bg-[#E6F5F6] px-1.5 py-0.5 rounded border border-[#BFE2E4]/60"><Hash size={10} />{item.reference}</span>}
                  {item.avis_estimation_ttc && <span className="cw-mono inline-flex items-center gap-1 text-[10px] font-semibold text-[#0E93A1] bg-[#E6F5F6] px-1.5 py-0.5 rounded border border-[#BFE2E4]/60"><DollarSign size={10} />{item.avis_estimation_ttc}</span>}
                  {hasBP && <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#1F6B4C] bg-[#E9F5EF] px-1.5 py-0.5 rounded border border-[#9BC8A8]/60"><Table size={10} />BP</span>}
                  {item.nombre_references && <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#C7913F] bg-[#FBF3E6] px-1.5 py-0.5 rounded border border-[#E7D2A8]/60"><FileCheck size={10} />{item.nombre_references} réf.</span>}
                  {item.classe_qualification && <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#4A6B72] bg-[#EEF4F3] px-1.5 py-0.5 rounded border border-[#C7DAD8]/60"><Award size={10} />{item.classe_qualification}</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <GaugeDial score={score} size={40} thickness={3.5} />
                  {deadline && (
                    <div className={`text-right min-w-[70px] px-2 py-1 rounded-lg ${isUrgent ? 'bg-[#FBEAE6]' : isExpired ? 'bg-[#F1F6F5]' : 'bg-[#F7FAF9]'}`}>
                      <div className={`cw-mono text-[11px] font-bold ${isUrgent ? 'text-[#D6572E]' : isExpired ? 'text-[#9BB5B1] line-through' : 'text-[#4F6E69]'}`}>{isExpired ? 'Expiré' : daysLeft !== null ? `${daysLeft}j` : fmtDate(deadline)}</div>
                      {!isExpired && daysLeft !== null && <div className={`cw-mono text-[10px] font-semibold mt-0.5 ${isUrgent ? 'text-[#D6572E]' : daysLeft <= 3 ? 'text-[#C7913F]' : 'text-[#9BB5B1]'}`}>{fmtDate(deadline)}</div>}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={item.status} onClick={(e) => { e.stopPropagation(); }} />
                  {hasDCE && <span className="p-1 rounded-lg bg-[#E9F5EF] shadow-sm" title="DCE Available"><FileText size={13} className="text-[#2F8F66]" /></span>}
                </div>
                <ChevronRight size={18} className={`transition-all duration-300 ${active ? 'text-[#0E93A1] translate-x-1' : 'text-[#C3D6D2] group-hover:text-[#0E93A1] group-hover:translate-x-1'}`} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}

// ═══════════════════════════════════════════════════════════
// Tender Side Panel Content
// ═══════════════════════════════════════════════════════════
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
    try { const ep = itemType === 'supplier' ? 'suppliers' : itemType === 'sector' ? 'sectors' : 'tenders'; const id = item.reference || item.id; await fetch(`${API_URL}/${ep}/${id}/status?status=${next}`, { method: 'PUT', headers: authHeaders() }); onStatusChange(id, next); } catch (e) { console.error(e); }
  };

  const handleQualifyClick = async (status) => {
    try { await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderId)}/qualify?status=${status}`, { method: 'PUT', headers: authHeaders() }); onQualify(tenderId, status); } catch (e) { console.error(e); }
  };

  const otherFields = [
    { icon: Building2, label: 'Acheteur public', value: item.acheteur_public }, { icon: Target, label: "Lieu d'exécution", value: item.lieu_execution }, { icon: FileText, label: 'Procédure', value: item.procedure }, { icon: Tag, label: 'Catégorie', value: item.categorie }, { icon: Calendar, label: 'Date publication', value: item.date_publication ? new Date(item.date_publication).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : null }, { icon: HashIcon, label: 'Lots', value: item.lots }, { icon: Monitor, label: 'Soumission électronique', value: item.reponse_electronique_obligatoire },
  ].filter(f => f.value !== null && f.value !== undefined && f.value !== '');
  const administrativeFields = [
    { icon: Shield, label: 'Attestations demandées', value: item.attestations_demandees }, { icon: FileCheck, label: 'Types attestations', value: item.types_attestations }, { icon: HashIcon, label: 'Nombre références', value: item.nombre_references }, { icon: Award, label: 'Classe qualification', value: item.classe_qualification },
  ].filter(f => f.value !== null && f.value !== undefined);
  const financialFields = [
    { icon: DollarSign, label: "Chiffre d'affaires", value: item.chiffre_affaires }, { icon: FileCheck, label: 'Déclaration honneur', value: item.declaration_honneur }, { icon: Shield, label: 'Caution provisoire', value: item.caution_provisoire }, { icon: Users, label: 'Note moyens humains', value: item.note_moyens_humains }, { icon: BarChart3, label: 'Attestations CA', value: item.attestations_ca }, { icon: Briefcase, label: 'Attestations référence', value: item.attestations_reference },
  ].filter(f => f.value !== null && f.value !== undefined);
  const technicalFields = [
    { icon: Truck, label: 'Dépôt prospectus', value: item.depot_prospectus }, { icon: BarChart3, label: 'Plan de charge', value: item.plan_charge }, { icon: Users, label: 'Moyens humains/tech.', value: item.moyens_humains_techniques }, { icon: Wrench, label: 'Méthodologie travail', value: item.methodologie_travail }, { icon: PenTool, label: 'Mémoire technique', value: item.memoire_technique }, { icon: Beaker, label: 'Échantillon/prototype', value: item.echantillon }, { icon: ClipboardList, label: "Acte d'engagement", value: item.acte_engagement }, { icon: FileText, label: 'Bordereau des prix', value: item.bordereau_prix },
  ].filter(f => f.value !== null && f.value !== undefined);

  return (
    <>
      <div className="sticky top-0 bg-white/95 backdrop-blur-sm z-10 shadow-sm">
        <div className="h-1.5 bg-gradient-to-r from-[#0E93A1] to-[#0C7C88]" />
        <div className="flex items-start justify-between gap-4 p-5 border-b border-[#DCE8E5]">
          <div className="flex items-start gap-3 min-w-0">
            <GaugeDial score={score} size={56} thickness={4.5} />
            <div>
              <h2 className="cw-serif text-lg font-medium text-[#123338] leading-snug mb-2">{item.objet || item.title || 'Untitled'}</h2>
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge status={item.status} onClick={cycleStatus} />
                {isUrgent && <span className="cw-mono inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#FBEAE6] text-[11px] font-bold text-[#D6572E] shadow-sm"><Clock size={11} /> {daysLeft} days left</span>}
                {isExpired && <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#F1F6F5] text-[11px] font-bold text-[#9BB5B1] shadow-sm">Expired</span>}
                {(qStatus === 'unseen' || qStatus === 'seen') && (
                      <button onClick={() => handleQualifyClick('preselected')}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-amber-50 text-amber-600 border border-amber-200 hover:bg-amber-100 transition-all shadow-sm">
                        <Star size={12} />Présélectionner
                      </button>
                    )}
                    {qStatus === 'preselected' && (
                      <>
                        <button onClick={() => handleQualifyClick('qualified')}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-emerald-50 text-emerald-600 border border-emerald-200 hover:bg-emerald-100 transition-all shadow-sm">
                          <UserCheck size={12} />Qualifier
                        </button>
                        <button onClick={() => handleQualifyClick('seen')}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-red-50 text-red-500 border border-red-200 hover:bg-red-100 transition-all shadow-sm">
                          <RotateCcw size={12} />Annuler présélection
                        </button>
                      </>
                    )}
                    {qStatus === 'qualified' && (
                      <button onClick={() => handleQualifyClick('seen')}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold bg-red-50 text-red-500 border border-red-200 hover:bg-red-100 transition-all shadow-sm">
                        <RotateCcw size={12} />Annuler qualification
                      </button>
                    )}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="flex-shrink-0 p-2 text-[#9BB5B1] hover:text-[#123338] hover:bg-[#F1F6F5] rounded-xl transition-all duration-200 hover:shadow-sm"><X size={20} /></button>
        </div>
      </div>
      <div className="p-5 space-y-5">
        {item.dce_zip_url && (<div className="p-5 bg-gradient-to-br from-[#E6F5F6] to-[#D3EEF0] rounded-2xl border border-[#BFE2E4]/60 shadow-lg shadow-[#0E93A1]/5"><div className="flex items-center gap-3 mb-4"><div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center shadow-md"><FileArchive size={18} className="text-[#0E93A1]" /></div><div><p className="text-sm font-bold text-[#123338]">Full DCE Available</p><p className="text-xs text-[#4F6E69]">Download complete tender documents</p></div></div><div className="flex items-center gap-2"><button onClick={() => setShowZipModal(true)} className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-bold text-[#123338] bg-white border border-[#DCE8E5] hover:bg-[#F7FAF9] transition-all duration-200 shadow-sm hover:shadow-md"><Eye size={15} /> Browse files</button><a href={item.dce_zip_url} target="_blank" rel="noopener noreferrer" className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-bold text-white bg-[#123338] hover:bg-[#0D2A2E] transition-all duration-200 shadow-lg shadow-[#123338]/10 hover:shadow-xl hover:shadow-[#123338]/20"><Download size={15} /> Download</a></div>{hasBP && (<div className="mt-3 pt-3 border-t border-[#BFE2E4]/60"><button onClick={() => setShowBPModal(true)} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-[#1F6B4C] bg-[#E9F5EF] border border-[#9BC8A8]/60 hover:bg-[#D3EDDF] transition-all duration-200 shadow-sm hover:shadow-md active:scale-[0.98]"><Table size={15} />View Bordereau des Prix (BP)<ChevronRight size={15} /></button></div>)}</div>)}
        {showZipModal && <ZipViewerModal tenderId={tenderId} tenderTitle={item.objet || item.title} onClose={() => setShowZipModal(false)} />}
        {showBPModal && <BPItemsModal tenderReference={tenderId} onClose={() => setShowBPModal(false)} />}
        {hasBP && !item.dce_zip_url && (<div className="p-5 bg-gradient-to-br from-[#E9F5EF] to-[#D3EDDF] rounded-2xl border border-[#9BC8A8]/60 shadow-lg shadow-[#1F6B4C]/5"><div className="flex items-center gap-3 mb-4"><div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center shadow-md"><Table size={18} className="text-[#1F6B4C]" /></div><div><p className="text-sm font-bold text-[#123338]">Bordereau des Prix Available</p><p className="text-xs text-[#4F6E69]">View extracted price schedule</p></div></div><button onClick={() => setShowBPModal(true)} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-white bg-[#1F6B4C] hover:bg-[#175A3A] transition-all duration-200 shadow-lg shadow-[#1F6B4C]/10 hover:shadow-xl hover:shadow-[#1F6B4C]/20 active:scale-[0.98]"><Table size={15} />View Bordereau des Prix<ChevronRight size={15} /></button></div>)}
        <div>
          <div className="flex items-center gap-2 mb-3"><div className="w-8 h-8 rounded-xl bg-[#E6F5F6] flex items-center justify-center shadow-sm"><Info size={15} className="text-[#0E93A1]" /></div><h3 className="cw-serif font-medium text-base text-[#123338]">Key Information</h3></div>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <InfoCard icon={HashIcon} label="Référence" value={item.reference} color="#0E93A1" />
            <InfoCard icon={DollarSign} label="Estimation TTC" value={item.avis_estimation_ttc} color="#0E93A1" />
            <div className="bg-white rounded-xl border border-[#DCE8E5] p-3 shadow-sm hover:shadow-md transition-all duration-200 col-span-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#D6572E15' }}>
                      <Clock size={14} style={{ color: '#D6572E' }} />
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#7FA09B]">Date limite</span>
                      <p className="text-sm font-bold text-[#123338] truncate cw-mono">{item.date_limite_remise_plis ? fmtDate(item.date_limite_remise_plis) : '—'}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <InfoCard icon={FileCheck} label="Nb Références" value={item.nombre_references} color="#C7913F" />
            <InfoCard icon={Award} label="Classe qualification" value={item.classe_qualification} color="#4A6B72" />
            <InfoCard icon={Laptop} label="Type de réponse" value={item.reponse_electronique_obligatoire === true ? 'Électronique' : item.reponse_electronique_obligatoire === false ? 'Physique' : null} color="#4A6B72" />
          </div>
          {otherFields.length > 0 && <div className="bg-white rounded-xl border border-[#DCE8E5] shadow-sm overflow-hidden mb-3"><div className="px-4 py-2.5 bg-[#F7FAF9] border-b border-[#DCE8E5]"><p className="text-[10px] font-extrabold uppercase tracking-wider text-[#4F6E69]">General Information</p></div><div className="p-2">{otherFields.map((f, i) => <DetailField key={i} {...f} />)}</div></div>}
          {administrativeFields.length > 0 && <div className="bg-white rounded-xl border border-[#DCE8E5] shadow-sm overflow-hidden mb-3"><div className="px-4 py-2.5 bg-[#F7FAF9] border-b border-[#DCE8E5]"><p className="text-[10px] font-extrabold uppercase tracking-wider text-[#4F6E69]">Administrative</p></div><div className="p-2">{administrativeFields.map((f, i) => <DetailField key={i} {...f} />)}</div></div>}
          {financialFields.length > 0 && <div className="bg-white rounded-xl border border-[#DCE8E5] shadow-sm overflow-hidden mb-3"><div className="px-4 py-2.5 bg-[#F7FAF9] border-b border-[#DCE8E5]"><p className="text-[10px] font-extrabold uppercase tracking-wider text-[#4F6E69]">Financial</p></div><div className="p-2">{financialFields.map((f, i) => <DetailField key={i} {...f} />)}</div></div>}
          {technicalFields.length > 0 && <div className="bg-white rounded-xl border border-[#DCE8E5] shadow-sm overflow-hidden mb-3"><div className="px-4 py-2.5 bg-[#F7FAF9] border-b border-[#DCE8E5]"><p className="text-[10px] font-extrabold uppercase tracking-wider text-[#4F6E69]">Technical</p></div><div className="p-2">{technicalFields.map((f, i) => <DetailField key={i} {...f} />)}</div></div>}
        </div>
        {item.source_url && <div className="border-t border-[#DCE8E5] pt-4"><a href={item.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-[#DCE8E5] text-[#4F6E69] rounded-xl text-xs font-bold hover:bg-[#F7FAF9] hover:text-[#123338] transition-all duration-200 shadow-sm hover:shadow-md"><ExternalLink size={13} /> View original source</a></div>}
      </div>
    </>
  );
}

function TenderSidePanel({ item, onClose, onStatusChange, onQualify, itemType }) {
  const [visible, setVisible] = useState(false);
  const handleClose = useCallback(() => { setVisible(false); setTimeout(onClose, 200); }, [onClose]);
  useEffect(() => { const id = requestAnimationFrame(() => setVisible(true)); const onKey = (e) => { if (e.key === 'Escape') handleClose(); }; document.addEventListener('keydown', onKey); return () => { cancelAnimationFrame(id); document.removeEventListener('keydown', onKey); }; }, [handleClose]);
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div onClick={handleClose} className={`absolute inset-0 bg-[#123338]/40 backdrop-blur-sm transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'}`} />
      <div className={`relative w-full sm:w-[520px] lg:w-[580px] bg-white h-full shadow-2xl shadow-[#123338]/20 overflow-y-auto transition-all duration-300 ease-out ${visible ? 'translate-x-0' : 'translate-x-8 opacity-0'}`}>
        {item && <TenderSidePanelContent item={item} onClose={handleClose} onStatusChange={onStatusChange} onQualify={onQualify} itemType={itemType} />}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════
//  MAIN COMPONENT
// ═══════════════════════════════════════════════════════════
const POLL_ACTIVE = 10000;
const POLL_IDLE = 60000;

export default function Tenders({ showOnlyPreselected = false }) {
  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [qualificationFilters, setQualificationFilters] = useState([]);
  const [search, setSearch] = useState('');
  const [lastScan, setLastScan] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
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
      setLastUpdate(new Date());
    } catch (e) { console.error(e); }
    if (showLoad) setLoading(false);
  }, [apiEndpoint, showOnlyPreselected]);

  const fetchKeywords = useCallback(async () => { try { const response = await fetch(`${API_URL}/keywords`, { headers: authHeaders() }); const data = await response.json(); if (data.success) setKeywords(data.keywords || []); } catch (error) { console.error('Error fetching keywords:', error); } }, []);
  const addKeyword = async (keyword) => { try { const response = await fetch(`${API_URL}/keywords`, { method: 'POST', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ keyword, category: 'custom', is_active: true }) }); const data = await response.json(); if (data.success) await fetchKeywords(); } catch (error) { console.error(error); } };
  const deleteKeyword = async (keywordId) => { try { await fetch(`${API_URL}/keywords/${keywordId}`, { method: 'DELETE', headers: authHeaders() }); await fetchKeywords(); } catch (error) { console.error(error); } };
  const toggleKeyword = async (keywordId, isActive) => { try { await fetch(`${API_URL}/keywords/${keywordId}`, { method: 'PATCH', headers: { ...authHeaders(), 'Content-Type': 'application/json' }, body: JSON.stringify({ is_active: isActive }) }); await fetchKeywords(); } catch (error) { console.error(error); } };

  const markAsSeen = async (tenderRef) => { setTenders(prev => prev.map(t => t.reference === tenderRef ? { ...t, seen: true, qualification_status: t.qualification_status === 'unseen' ? 'seen' : t.qualification_status } : t)); try { await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderRef)}/seen`, { method: 'PUT', headers: authHeaders() }); } catch (e) { console.error('Failed to mark as seen:', e); } };
  const handleQualify = async (tenderRef, newStatus) => { setTenders(prev => prev.map(t => t.reference === tenderRef ? { ...t, qualification_status: newStatus } : t)); if (selected && (selected.reference || selected.id) === tenderRef) setSelected(p => ({ ...p, qualification_status: newStatus })); try { await fetch(`${API_URL}/tenders/${encodeURIComponent(tenderRef)}/qualify?status=${newStatus}`, { method: 'PUT', headers: authHeaders() }); } catch (e) { console.error('Failed to update qualification:', e); } };

  useEffect(() => { fetchAll(); fetchKeywords(); return () => { if (pollingRef.current) clearInterval(pollingRef.current); }; }, [fetchAll, fetchKeywords]);
  useEffect(() => { if (pollingRef.current) clearInterval(pollingRef.current); if (autoRefresh) pollingRef.current = setInterval(() => fetchAll(false), scanning ? POLL_ACTIVE : POLL_IDLE); return () => { if (pollingRef.current) clearInterval(pollingRef.current); }; }, [scanning, autoRefresh, fetchAll]);

  const handleScan = async () => { setScanning(true); try { const r = await fetch(`${API_URL}/tenders/scan`, { method: 'POST', headers: authHeaders() }); const d = await r.json(); if (d.success) setLastScan(new Date()); } catch { } setTimeout(() => setScanning(false), 30000); };
  const handleStatusChange = (id, newStatus) => { setTenders(prev => prev.map(t => (t.reference || t.id) === id ? { ...t, status: newStatus } : t)); if (selected && (selected.reference || selected.id) === id) setSelected(p => ({ ...p, status: newStatus })); };
  const clearAllFilters = () => { setQualificationFilters([]); setUseKeywordFilter(false); setDeadlineSort('default'); };

  const toggleQualificationFilter = (status) => { setQualificationFilters(prev => prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]); };

  const sortItems = useCallback((items) => { return [...items].sort((a, b) => { if (deadlineSort === 'nearest') { const da = a.date_limite_remise_plis ? new Date(a.date_limite_remise_plis).getTime() : Infinity; const db = b.date_limite_remise_plis ? new Date(b.date_limite_remise_plis).getTime() : Infinity; if (da !== db) return da - db; } const sb = getScore(b), sa = getScore(a); if (sb !== sa) return sb - sa; const da = a.date_limite_remise_plis ? new Date(a.date_limite_remise_plis).getTime() : Infinity; const db = b.date_limite_remise_plis ? new Date(b.date_limite_remise_plis).getTime() : Infinity; return da - db; }); }, [deadlineSort]);

  // ✅ FILTRAGE DES APPELS D'OFFRES EXPIRÉS
  const filterItems = useCallback((items) => {
    let f = items;
    
    // Filtrer les appels d'offres expirés
    f = f.filter(t => {
      const deadline = t.date_limite_remise_plis;
      if (!deadline) return true; // Garder si pas de date limite
      const daysLeft = Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24));
      return daysLeft >= 0; // Garder seulement si pas expiré (0 = aujourd'hui)
    });
    
    if (qualificationFilters.length > 0) f = f.filter(t => qualificationFilters.includes(t.qualification_status || 'unseen'));
    if (search) { const q = search.toLowerCase(); f = f.filter(t => (t.objet || t.title || '').toLowerCase().includes(q) || (t.lieu_execution || '').toLowerCase().includes(q) || (t.acheteur_public || '').toLowerCase().includes(q) || (t.reference || '').toLowerCase().includes(q)); }
    if (useKeywordFilter && keywords.length > 0) { const activeKeywords = keywords.filter(k => k.is_active).map(k => k.keyword); if (activeKeywords.length > 0) { f = f.filter(tender => { const txt = [tender.objet || '', tender.acheteur_public || '', tender.lieu_execution || '', tender.categorie || '', tender.procedure || '', tender.reference || ''].join(' ').toLowerCase().replace(/[éèêë]/g, 'e').replace(/[àâä]/g, 'a').replace(/[ùûü]/g, 'u').replace(/[ôö]/g, 'o').replace(/[îï]/g, 'i').replace(/ç/g, 'c'); return activeKeywords.some(kw => txt.includes(kw.toLowerCase().replace(/[éèêë]/g, 'e').replace(/[àâä]/g, 'a').replace(/[ùûü]/g, 'u').replace(/[ôö]/g, 'o').replace(/[îï]/g, 'i').replace(/ç/g, 'c'))); }); } }
    return sortItems(f);
  }, [qualificationFilters, search, useKeywordFilter, keywords, sortItems]);

  const current = filterItems(tenders);
  const isAllQuick = qualificationFilters.length === 0 && !useKeywordFilter && deadlineSort === 'default';
  const activeKeywordCount = keywords.filter(k => k.is_active).length;
  const handleSelectTender = (item) => { setSelected(item); if (!item.seen) markAsSeen(item.reference); };

  return (
    <div className="cw-theme min-h-screen bg-white">
      <style>{CW_THEME_STYLE}</style>
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
        {!showOnlyPreselected && (
          <div className="bg-white rounded-2xl border border-[#DCE8E5] shadow-lg shadow-[#123338]/5 overflow-hidden">
            <div className="p-3 sm:p-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <button onClick={() => setAutoRefresh(r => !r)} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border transition-all duration-200 hover:shadow-md active:scale-95 ${autoRefresh ? 'bg-[#E6F5F6] text-[#0E93A1] border-[#0E93A1]/20 shadow-sm' : 'bg-[#F1F6F5] text-[#9BB5B1] border-[#DCE8E5]'}`}>{autoRefresh ? <><Wifi size={12} /><span className="hidden sm:inline">Live</span><span className="flex h-1.5 w-1.5"><span className="animate-ping absolute inline-flex h-1.5 w-1.5 rounded-full bg-[#0E93A1] opacity-75"></span><span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#0E93A1]"></span></span></> : <><WifiOff size={12} /><span className="hidden sm:inline">Paused</span></>}</button>
                  {lastUpdate && <span className="hidden lg:flex items-center gap-1.5 text-[11px] text-[#9BB5B1] cw-mono"><Clock size={11} />Updated {lastUpdate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
                </div>
                <div className="flex items-center gap-2"><button onClick={() => fetchAll(true)} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border border-[#DCE8E5] bg-white text-[#4F6E69] hover:bg-[#F7FAF9] hover:text-[#123338] transition-all duration-200 shadow-sm hover:shadow-md"><RefreshCw size={12} className={loading ? 'animate-spin' : ''} /><span className="hidden sm:inline">Refresh</span></button><button onClick={handleScan} disabled={scanning} className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-gradient-to-r from-[#0E93A1] to-[#0C7C88] hover:from-[#0C7C88] hover:to-[#0A6B76] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg shadow-[#0E93A1]/20 hover:shadow-xl hover:shadow-[#0E93A1]/30 active:scale-95">{scanning ? <><Loader size={12} className="animate-spin" />Scanning...</> : <><Zap size={12} />Launch scan</>}</button></div>
              </div>
              {scanning && <div className="mt-3 flex items-center gap-2 px-4 py-2.5 bg-[#E6F5F6] border border-[#0E93A1]/20 rounded-xl shadow-sm"><Activity size={14} className="text-[#0E93A1] animate-pulse flex-shrink-0" /><div className="flex-1"><p className="text-xs font-bold text-[#123338]">Scan in progress…</p><p className="text-[10px] text-[#4F6E69]">New tenders will appear automatically</p></div><span className="text-[10px] text-[#9BB5B1] cw-mono">{lastScan ? `Last: ${lastScan.toLocaleTimeString()}` : 'Scanning...'}</span></div>}
            </div>
          </div>
        )}
        <div className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm pb-3 -mt-1 pt-1">
          <div className="bg-white rounded-2xl border border-[#DCE8E5] shadow-lg shadow-[#123338]/5 p-3">
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="relative flex-1 min-w-0"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9BB5B1]" /><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by title, buyer, location, reference..." className="w-full pl-9 pr-3 py-2.5 bg-[#F7FAF9] border border-[#DCE8E5] rounded-xl text-sm text-[#123338] placeholder-[#9BB5B1] focus:ring-2 focus:ring-[#0E93A1]/20 focus:border-[#0E93A1] focus:bg-white outline-none transition-all shadow-sm" /></div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <FilterPill active={isAllQuick} onClick={clearAllFilters} icon={<Filter size={11} />}>Tous</FilterPill>
                <QualificationFilterDropdown selected={qualificationFilters} onToggle={toggleQualificationFilter} onClear={() => setQualificationFilters([])} />
                <FilterPill active={deadlineSort === 'nearest'} onClick={() => setDeadlineSort(prev => prev === 'nearest' ? 'default' : 'nearest')} icon={<Clock size={11} />}>Deadline</FilterPill>
                <FilterPill active={useKeywordFilter} onClick={() => { if (!useKeywordFilter) setShowKeywordManager(true); else setUseKeywordFilter(false); }} icon={<SlidersHorizontal size={11} />}>Mots-clés{useKeywordFilter && activeKeywordCount > 0 && <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#0E93A1] text-white text-[9px] font-bold shadow-sm">{activeKeywordCount}</span>}</FilterPill>
              </div>
            </div>
            {qualificationFilters.length > 0 && (<div className="mt-2 flex items-center gap-2 px-3 py-2 bg-[#E6F5F6] border border-[#0E93A1]/20 rounded-xl shadow-sm"><Filter size={12} className="text-[#0E93A1] flex-shrink-0" /><div className="flex items-center gap-1 flex-wrap flex-1"><span className="text-[10px] font-bold text-[#123338]">Statut :</span>{qualificationFilters.map(f => (<span key={f} className={`px-1.5 py-0.5 rounded-md text-[10px] font-semibold border shadow-sm ${f === 'preselected' ? 'bg-amber-50 text-amber-700 border-amber-300' : 'bg-emerald-50 text-emerald-700 border-emerald-300'}`}>{f === 'preselected' ? 'Présélectionnés' : 'Qualifiés'}</span>))}</div></div>)}
            <div className="mt-2 flex items-center justify-between text-[10px] text-[#9BB5B1]"><span><span className="font-bold text-[#123338] cw-mono">{current.length}</span> appel{current.length !== 1 ? 's' : ''} d'offre{current.length !== 1 ? 's' : ''} trouvé{current.length !== 1 ? 's' : ''}</span>{lastScan && <span className="cw-mono">Dernier scan: {lastScan.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}</div>
          </div>
        </div>
        {loading ? (<div className="flex flex-col items-center justify-center py-24 gap-4"><div className="relative"><div className="w-14 h-14 rounded-2xl bg-white border border-[#DCE8E5] shadow-xl shadow-[#0E93A1]/10 flex items-center justify-center"><Loader size={24} className="text-[#0E93A1] animate-spin" /></div></div><p className="text-sm font-bold text-[#4F6E69]">Chargement des appels d'offres...</p><p className="text-xs text-[#9BB5B1]">Récupération des dernières opportunités</p></div>) : current.length === 0 ? (<div className="bg-white rounded-2xl border border-[#DCE8E5] shadow-lg shadow-[#123338]/5"><div className="flex flex-col items-center text-center py-16 px-4"><div className="w-16 h-16 rounded-2xl bg-[#F1F6F5] flex items-center justify-center mb-4 shadow-md"><Globe size={28} className="text-[#9BB5B1]" /></div><h3 className="cw-serif text-lg font-medium text-[#123338] mb-1">Aucun appel d'offre trouvé</h3><p className="text-sm text-[#4F6E69] max-w-md mb-4">{tenders.length === 0 ? "Vous n'avez pas encore découvert d'appels d'offres. Lancez votre premier scan." : 'Aucun appel d\'offre ne correspond à vos filtres.'}</p>{tenders.length === 0 ? <button onClick={handleScan} disabled={scanning} className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm text-white bg-gradient-to-r from-[#0E93A1] to-[#0C7C88] hover:from-[#0C7C88] hover:to-[#0A6B76] disabled:opacity-50 transition-all duration-200 shadow-lg shadow-[#0E93A1]/20 hover:shadow-xl hover:shadow-[#0E93A1]/30 active:scale-95"><Zap size={14} /> Lancer le scan</button> : <button onClick={clearAllFilters} className="flex items-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm text-[#123338] bg-white border border-[#DCE8E5] hover:bg-[#F7FAF9] transition-all duration-200 shadow-sm hover:shadow-md">Effacer les filtres</button>}</div></div>) : (<div className="flex flex-col gap-2">{current.map(item => (<TenderCard key={item.reference || item.id} item={item} active={selected && (selected.reference || selected.id) === (item.reference || item.id)} onClick={() => handleSelectTender(item)} onQualify={handleQualify} />))}</div>)}
      </div>
      {selected && <TenderSidePanel item={selected} itemType="tender" onClose={() => setSelected(null)} onStatusChange={handleStatusChange} onQualify={handleQualify} />}
      <KeywordManager isOpen={showKeywordManager} onClose={() => { setShowKeywordManager(false); if (keywords.filter(k => k.is_active).length === 0) setUseKeywordFilter(false); }} keywords={keywords} onAdd={async (keyword) => { await addKeyword(keyword); setUseKeywordFilter(true); }} onDelete={deleteKeyword} onToggle={toggleKeyword} />
    </div>
  );
}