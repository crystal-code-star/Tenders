import React, { useState, useEffect, useCallback, useRef } from 'react';
import Login from './components/Login';
import Tenders from './components/Tenders';
import ScoringManager from './components/ScoringManager';
import {
  FileSearch, LogOut, Sparkles,
  PanelLeftClose, PanelLeft,
  Star, Sliders
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════════════
export const BRAND = {
  gradient: 'linear-gradient(135deg, #2563EB, #1D4ED8)',
  solid: '#2563EB',
  soft: '#EFF6FF',
};

const CW_THEME_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  
  * {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, ui-sans-serif, sans-serif;
  }
  
  * {
    transition-property: background-color, border-color, color, fill, stroke, opacity, box-shadow, transform;
    transition-duration: 150ms;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
`;

// ═══════════════════════════════════════════════════════════════
// TOAST SYSTEM
// ═══════════════════════════════════════════════════════════════
const ToastContext = React.createContext();
export const useToast = () => React.useContext(ToastContext);

function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const add = useCallback((msg, type = 'info', dur = 3500) => {
    const id = ++idRef.current;
    setToasts(p => [...p, { id, msg, type, dur }]);
    if (dur > 0) setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), dur);
    return id;
  }, []);

  const dismiss = useCallback((id) => setToasts(p => p.filter(t => t.id !== id)), []);

  const toast = {
    success: (m, d) => add(m, 'success', d || 3000),
    error:   (m, d) => add(m, 'error',   d || 5000),
    warning: (m, d) => add(m, 'warning', d || 4000),
    info:    (m, d) => add(m, 'info',    d || 3000),
    loading: (m)    => add(m, 'loading', 999999),
    dismiss,
  };

  const TS = {
    success: { bar: '#16A34A', icon: '✓', dot: 'bg-emerald-500' },
    error:   { bar: '#DC2626', icon: '✕', dot: 'bg-red-500'     },
    warning: { bar: '#CA8A04', icon: '!', dot: 'bg-amber-500'   },
    info:    { bar: BRAND.solid, icon: 'i', dot: 'bg-blue-500'  },
    loading: { bar: BRAND.solid, icon: '…', dot: 'bg-blue-400'  },
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map(t => {
          const s = TS[t.type] || TS.info;
          return (
            <div key={t.id} onClick={() => t.type !== 'loading' && dismiss(t.id)}
              style={{ borderLeftColor: s.bar }}
              className="pointer-events-auto border-l-4 rounded-2xl shadow-lg bg-white border border-[#E2E8F0] p-4 flex items-start gap-3 animate-slide-in cursor-pointer">
              <div className={`w-5 h-5 rounded-lg ${s.dot} flex items-center justify-center flex-shrink-0 mt-0.5`}>
                <span className="text-white text-xs font-bold">{s.icon}</span>
              </div>
              <p className="text-sm font-medium text-[#0F172A] leading-snug flex-1">{t.msg}</p>
              <button onClick={e => { e.stopPropagation(); dismiss(t.id); }} className="text-[#94A3B8] hover:text-[#0F172A] text-lg leading-none">×</button>
            </div>
          );
        })}
      </div>
      <style>{`@keyframes slideIn{from{transform:translateX(110%);opacity:0}to{transform:translateX(0);opacity:1}}.animate-slide-in{animation:slideIn .2s cubic-bezier(.16,1,.3,1)}`}</style>
    </ToastContext.Provider>
  );
}

// ═══════════════════════════════════════════════════════════════
// NAV
// ═══════════════════════════════════════════════════════════════
const NAV_GROUPS = [
  {
    label: 'Tenders',
    items: [
      { id: 'tenders',      label: 'All Tenders',        icon: FileSearch },
      { id: 'preselected',  label: 'Pre-selected',       icon: Star },
      { id: 'scoring',      label: 'Scoring Criteria',   icon: Sliders },
    ],
  },
];

const PAGE_TITLES = {
  tenders:       'All Tenders',
  preselected:   'Pre-selected Tenders',
  scoring:       'Scoring Criteria',
};

// ═══════════════════════════════════════════════════════════════
// APP
// ═══════════════════════════════════════════════════════════════

function Shell() {
  const [auth, setAuth] = useState(false);
  const [email, setEmail] = useState('');
  const [tab, setTab] = useState('tenders');
  const [collapsed, setCollapsed] = useState(false);

  const loginOk = (e) => { setEmail(e); setAuth(true); };
  const logout  = () => { localStorage.removeItem('access_token'); localStorage.removeItem('user_email'); setAuth(false); setEmail(''); };

  useEffect(() => {
    const t = localStorage.getItem('access_token');
    const e = localStorage.getItem('user_email');
    if (t && e) { setEmail(e); setAuth(true); }
  }, []);

  if (!auth) return <Login onLoginSuccess={loginOk} />;

  const initials = email ? email[0].toUpperCase() : '?';

  return (
    <div className="flex h-screen bg-[#F8FAFC]">
      <style>{CW_THEME_STYLE}</style>

      {/* SIDEBAR */}
      <aside className={`flex flex-col flex-shrink-0 bg-white border-r border-[#E2E8F0] transition-all duration-200 ${collapsed ? 'w-[76px]' : 'w-[250px]'}`}>
        <div className="h-14 flex items-center justify-between px-4 flex-shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 bg-[#111827] shadow-sm">
              <Sparkles size={15} className="text-white" />
            </div>
            {!collapsed && <span className="font-semibold text-[#0F172A] text-base truncate">CrystalWater</span>}
          </div>
          {!collapsed && (
            <button onClick={() => setCollapsed(true)} className="w-7 h-7 rounded-xl flex items-center justify-center text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors flex-shrink-0">
              <PanelLeftClose size={14} />
            </button>
          )}
        </div>
        {collapsed && (
          <button onClick={() => setCollapsed(false)} className="mx-auto mb-2 w-7 h-7 rounded-xl flex items-center justify-center text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F8FAFC] transition-colors">
            <PanelLeft size={14} />
          </button>
        )}

        <nav className="flex-1 px-3 space-y-5 overflow-y-auto pt-2">
          {NAV_GROUPS.map(group => (
            <div key={group.label}>
              {!collapsed && <p className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#94A3B8]">{group.label}</p>}
              <div className="space-y-0.5">
                {group.items.map(item => {
                  const Icon = item.icon;
                  const active = tab === item.id;
                  return (
                    <button key={item.id} onClick={() => setTab(item.id)}
                      title={collapsed ? item.label : undefined}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-2xl text-sm font-medium transition-all ${
                        active 
                          ? 'bg-[#EFF6FF] text-[#2563EB] shadow-sm' 
                          : 'text-[#475569] hover:bg-[#F8FAFC] hover:text-[#0F172A]'
                      }`}>
                      <Icon size={16} className="flex-shrink-0" />
                      {!collapsed && <span>{item.label}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="px-3 pb-3 border-t border-[#E2E8F0] pt-2">
          <button onClick={logout} title={collapsed ? 'Logout' : undefined}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-2xl text-xs font-medium text-[#94A3B8] hover:bg-[#FEE2E2] hover:text-[#DC2626] transition-all">
            <LogOut size={15} className="flex-shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* HEADER - sans background, design épuré */}
        <header className="h-14 flex items-center justify-between px-6 flex-shrink-0">
          <h1 className="text-lg font-semibold text-[#0F172A]">{PAGE_TITLES[tab] || 'Tenders'}</h1>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center font-semibold text-white text-[11px] flex-shrink-0 bg-[#111827] shadow-sm">
              {initials}
            </div>
            <span className="text-xs font-medium text-[#475569] max-w-[140px] truncate hidden sm:block">{email}</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          {tab === 'tenders' && <Tenders />}
          {tab === 'preselected' && <Tenders showOnlyPreselected={true} />}
          {tab === 'scoring' && <ScoringManager isOpen={true} onClose={() => setTab('tenders')} />}
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}

export default App;