import React, { useState, useEffect, useCallback, useRef } from 'react';
import Login from './components/Login';
import Tenders from './components/Tenders';
import ScoringManager from './components/ScoringManager';
import Generate from './components/Generate';
import Dashboard from './components/Dashboard';
import Posts from './components/Posts';
import Trends from './components/Trends';
import {
  FileSearch, LogOut, Sparkles,
  PanelLeftClose, PanelLeft,
  ChevronDown, Star, Sliders,
  LayoutDashboard, PenTool, FileText,
  TrendingUp, Send, Key, Building2,
  Map, Settings2, HelpCircle
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════════════════════
export const BRAND = {
  gradient: 'linear-gradient(135deg,#8B7CF6,#7C5CFC)',
  solid: '#7C5CFC',
  soft: '#F1ECFF',
};

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
    success: { bar: '#10B981', icon: '✓', dot: 'bg-emerald-500' },
    error:   { bar: '#EF4444', icon: '✕', dot: 'bg-red-500'     },
    warning: { bar: '#F59E0B', icon: '!', dot: 'bg-amber-500'   },
    info:    { bar: BRAND.solid, icon: 'i', dot: 'bg-violet-500'  },
    loading: { bar: BRAND.solid, icon: '…', dot: 'bg-violet-400'  },
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
              className="pointer-events-auto border-l-4 rounded-xl shadow-xl bg-white border border-gray-100 p-4 flex items-start gap-3 animate-slide-in cursor-pointer">
              <div className={`w-5 h-5 rounded-full ${s.dot} flex items-center justify-center flex-shrink-0 mt-0.5`}>
                <span className="text-white text-xs font-bold">{s.icon}</span>
              </div>
              <p className="text-sm font-medium text-gray-800 leading-snug flex-1">{t.msg}</p>
              <button onClick={e => { e.stopPropagation(); dismiss(t.id); }} className="text-gray-300 hover:text-gray-500 text-lg leading-none">×</button>
            </div>
          );
        })}
      </div>
      <style>{`@keyframes slideIn{from{transform:translateX(110%);opacity:0}to{transform:translateX(0);opacity:1}}.animate-slide-in{animation:slideIn .3s cubic-bezier(.16,1,.3,1)}`}</style>
    </ToastContext.Provider>
  );
}

// ═══════════════════════════════════════════════════════════════
// PLACEHOLDER COMPONENT
// ═══════════════════════════════════════════════════════════════
function PlaceholderPage({ title, description, icon: Icon }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-center px-6">
      <div className="w-20 h-20 rounded-2xl flex items-center justify-center mb-6" style={{ background: BRAND.soft }}>
        {Icon && <Icon size={36} className="text-violet-600" />}
      </div>
      <h2 className="text-2xl font-bold text-gray-900 mb-3">{title}</h2>
      <p className="text-gray-500 max-w-md">{description}</p>
      <div className="mt-6 px-4 py-2 bg-violet-50 rounded-lg border border-violet-100">
        <p className="text-xs text-violet-600 font-medium">Section en développement</p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// NAV
// ═══════════════════════════════════════════════════════════════
const NAV_GROUPS = [
  {
    label: 'Principal',
    items: [
      { id: 'dashboard',    label: 'Dashboard',         icon: LayoutDashboard },
      { id: 'generator',    label: 'Générer des Posts', icon: PenTool },
      { id: 'posts',        label: 'Posts Générés',     icon: FileText },
      { id: 'trends',       label: 'Tendances',         icon: TrendingUp },
    ],
  },
  {
    label: 'Appels d\'Offres',
    items: [
      { id: 'tenders',      label: 'Tous les AO',       icon: FileSearch },
      { id: 'preselected',  label: 'Présélectionnés',   icon: Star },
      { id: 'scoring',      label: 'Critères Scoring',  icon: Sliders },
      { id: 'keywords',     label: 'Mots-clés',         icon: Key },
      { id: 'suppliers',    label: 'Fournisseurs',      icon: Building2 },
      { id: 'sectors',      label: 'Secteurs',           icon: Map },
    ],
  },
  {
    label: 'Prospection',
    items: [
      { id: 'outreach',     label: 'LinkedIn Outreach', icon: Send },
    ],
  },
  {
    label: 'Système',
    items: [
      { id: 'settings',     label: 'Paramètres',        icon: Settings2 },
      { id: 'help',         label: 'Aide & Support',    icon: HelpCircle },
    ],
  },
];

const PAGE_TITLES = {
  dashboard:     'Dashboard',
  generator:     'Génération de Posts',
  posts:         'Posts Générés',
  trends:        'Tendances du Marché',
  tenders:       'Appels d\'Offres',
  preselected:   'AO Présélectionnés',
  scoring:       'Critères de Scoring',
  keywords:      'Mots-clés AO',
  suppliers:     'Fournisseurs',
  sectors:       'Secteurs d\'Activité',
  outreach:      'LinkedIn Outreach',
  settings:      'Paramètres',
  help:          'Aide & Support',
};

// ═══════════════════════════════════════════════════════════════
// APP
// ═══════════════════════════════════════════════════════════════

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Shell() {
  const [auth, setAuth] = useState(false);
  const [email, setEmail] = useState('');
  const [tab, setTab] = useState('dashboard');
  const [collapsed, setCollapsed] = useState(false);
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState({ total: 0, pending: 0, approved: 0, posted: 0, rejected: 0, failed: 0 });

  const loginOk = (e) => { setEmail(e); setAuth(true); };
  const logout  = () => { localStorage.removeItem('access_token'); localStorage.removeItem('user_email'); setAuth(false); setEmail(''); };

  const fetchPostsAndStats = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const [postsRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/posts`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_URL}/stats`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (postsRes.ok) {
        const postsData = await postsRes.json();
        setPosts(Array.isArray(postsData) ? postsData : []);
      }
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (e) {
      console.error('Failed to fetch posts/stats:', e);
    }
  };

  useEffect(() => {
    const t = localStorage.getItem('access_token');
    const e = localStorage.getItem('user_email');
    if (t && e) { setEmail(e); setAuth(true); }
  }, []);

  useEffect(() => {
    if (auth) {
      fetchPostsAndStats();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth]);

  useEffect(() => {
    window.switchToPostsTab = () => setTab('posts');
    return () => { delete window.switchToPostsTab; };
  }, []);

  const handleUpdateStatus = async (postId, newStatus, editedText = null) => {
    try {
      const token = localStorage.getItem('access_token');
      if (newStatus === 'rejected') {
        await fetch(`${API_URL}/posts/${postId}/reject`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      } else if (editedText) {
        await fetch(`${API_URL}/posts/${postId}/edit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ post_text: editedText, status: newStatus }),
        });
      } else if (newStatus === 'approved') {
        await fetch(`${API_URL}/posts/${postId}/approve`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      }
      await fetchPostsAndStats();
    } catch (e) {
      console.error('Failed to update post:', e);
      throw e;
    }
  };

  const handleUploadImage = async (postId, file) => {
    try {
      const token = localStorage.getItem('access_token');
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_URL}/posts/${postId}/upload-image`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      await fetchPostsAndStats();
    } catch (e) {
      console.error('Failed to upload image:', e);
      throw e;
    }
  };

  if (!auth) return <Login onLoginSuccess={loginOk} />;

  const initials = email ? email[0].toUpperCase() : '?';

  return (
    <div className="flex h-screen bg-[#F5F6FB] font-sans">

      {/* SIDEBAR */}
      <aside className={`flex flex-col flex-shrink-0 bg-white border-r border-gray-100 transition-all duration-200 ${collapsed ? 'w-[76px]' : 'w-[250px]'}`}>
        <div className="h-16 flex items-center justify-between px-4 flex-shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: BRAND.gradient }}>
              <Sparkles size={15} className="text-white" />
            </div>
            {!collapsed && <span className="font-bold text-gray-900 text-base truncate">CrystalWater</span>}
          </div>
          {!collapsed && (
            <button onClick={() => setCollapsed(true)} className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-300 hover:text-gray-500 hover:bg-gray-50 transition-colors flex-shrink-0">
              <PanelLeftClose size={14} />
            </button>
          )}
        </div>
        {collapsed && (
          <button onClick={() => setCollapsed(false)} className="mx-auto mb-2 w-7 h-7 rounded-lg flex items-center justify-center text-gray-300 hover:text-gray-500 hover:bg-gray-50 transition-colors">
            <PanelLeft size={14} />
          </button>
        )}

        <nav className="flex-1 px-3 space-y-5 overflow-y-auto pt-2">
          {NAV_GROUPS.map(group => (
            <div key={group.label}>
              {!collapsed && <p className="px-2 mb-1.5 text-[9px] font-bold uppercase tracking-widest text-gray-300">{group.label}</p>}
              <div className="space-y-0.5">
                {group.items.map(item => {
                  const Icon = item.icon;
                  const active = tab === item.id;
                  return (
                    <button key={item.id} onClick={() => setTab(item.id)}
                      title={collapsed ? item.label : undefined}
                      className={`w-full flex items-center gap-3 px-2.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                        active ? 'bg-violet-50 text-violet-700' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
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

        <div className="px-3 pb-3 border-t border-gray-50 pt-2">
          <button onClick={logout} title={collapsed ? 'Logout' : undefined}
            className="w-full flex items-center gap-3 px-2.5 py-2 rounded-xl text-xs text-gray-400 hover:bg-red-50 hover:text-red-500 transition-all">
            <LogOut size={15} className="flex-shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* MAIN */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white border-b border-gray-100 flex items-center justify-between px-6 flex-shrink-0">
          <h1 className="text-base font-bold text-gray-900">{PAGE_TITLES[tab] || 'Dashboard'}</h1>
          <button className="flex items-center gap-2.5 pl-1 pr-2 py-1 rounded-xl hover:bg-gray-50 transition-colors">
            <div className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-white text-xs flex-shrink-0" style={{ background: BRAND.gradient }}>
              {initials}
            </div>
            <span className="text-xs font-semibold text-gray-700 max-w-[140px] truncate hidden sm:block">{email}</span>
            <ChevronDown size={13} className="text-gray-300 hidden sm:block" />
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          {tab === 'dashboard' && <Dashboard stats={stats} posts={posts} setActiveTab={setTab} />}
          {tab === 'generator' && <Generate setActiveTab={setTab} />}
          {tab === 'posts' && <Posts posts={posts} stats={stats} onUpdateStatus={handleUpdateStatus} onUploadImage={handleUploadImage} setActiveTab={setTab} />}
          {tab === 'trends' && <Trends />}
          {tab === 'tenders' && <Tenders />}
          {tab === 'preselected' && <Tenders showOnlyPreselected={true} />}
          {tab === 'scoring' && <ScoringManager isOpen={true} onClose={() => setTab('tenders')} />}
          {tab === 'keywords' && <PlaceholderPage title="Mots-clés AO" description="Gérez les mots-clés pour le filtrage des appels d'offres" icon={Key} />}
          {tab === 'suppliers' && <PlaceholderPage title="Fournisseurs" description="Consultez et gérez les fournisseurs détectés" icon={Building2} />}
          {tab === 'sectors' && <PlaceholderPage title="Secteurs d'Activité" description="Explorez les opportunités par secteur d'activité" icon={Map} />}
          {tab === 'outreach' && <PlaceholderPage title="LinkedIn Outreach" description="Prospection et envoi d'invitations LinkedIn" icon={Send} />}
          {tab === 'settings' && <PlaceholderPage title="Paramètres" description="Configurez votre application et vos préférences" icon={Settings2} />}
          {tab === 'help' && <PlaceholderPage title="Aide & Support" description="Documentation, guides et assistance technique" icon={HelpCircle} />}
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