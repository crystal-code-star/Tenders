import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, Calendar, CheckCircle2, AlertTriangle, ArrowRight, 
  Sparkles, Clock, FileText, Users, UserCheck, Send, Globe,
  Flame, Zap, BarChart3, Hash, ExternalLink, PenTool, Activity,
  Target, Newspaper, ChevronUp, ChevronDown, PieChart, LineChart,
  TrendingDown, Award, Eye, MessageCircle, Share2, ThumbsUp
} from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ═══════════════════════════════════════════════════════════════
// MINI COMPOSANTS DE GRAPHIQUES
// ═══════════════════════════════════════════════════════════════

// Barre de progression simple
function ProgressBar({ value, max, color = 'bg-[#0A66C2]', bg = 'bg-slate-100', label, showValue = true }) {
  const percent = Math.min((value / max) * 100, 100);
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs">
          <span className="text-slate-500">{label}</span>
          {showValue && <span className="font-semibold text-slate-700">{value}/{max}</span>}
        </div>
      )}
      <div className={`h-2 rounded-full ${bg} overflow-hidden`}>
        <div className={`h-full rounded-full ${color} transition-all duration-500`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

// Mini graphique en barres
function MiniBarChart({ data, height = 40, color = '#0A66C2' }) {
  const maxVal = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="flex items-end gap-1" style={{ height }}>
      {data.map((item, i) => (
        <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
          <div 
            className="w-full rounded-t transition-all duration-300 hover:opacity-80 cursor-pointer"
            style={{ 
              height: `${(item.value / maxVal) * 100}%`,
              backgroundColor: color,
              minHeight: item.value > 0 ? '4px' : '0'
            }}
            title={`${item.label}: ${item.value}`}
          />
        </div>
      ))}
    </div>
  );
}

// Mini graphique circulaire
function DonutChart({ segments, size = 80, strokeWidth = 8 }) {
  const total = segments.reduce((s, seg) => s + seg.value, 0) || 1;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  let offset = 0;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        {segments.map((seg, i) => {
          const percent = seg.value / total;
          const dash = circumference * percent;
          const segment = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
              className="transition-all duration-500"
            />
          );
          offset += dash;
          return segment;
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold text-slate-900">{total}</span>
        <span className="text-xs text-slate-400">Total</span>
      </div>
    </div>
  );
}

// Sparkline miniature
function Sparkline({ data, width = 80, height = 30, color = '#0A66C2' }) {
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const points = data.map((val, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((val - min) / range) * (height - 4) - 2
  }));
  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaD = pathD + ` L ${width} ${height} L 0 ${height} Z`;

  return (
    <svg width={width} height={height} className="flex-shrink-0">
      <defs>
        <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.2" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#grad-${color})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ═══════════════════════════════════════════════════════════════
// KPI METRIC CARD
// ═══════════════════════════════════════════════════════════════

function MetricCard({ icon: Icon, label, value, sub, color, trend, sparkline, progress }) {
  const colors = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', dot: 'bg-blue-500', bar: 'bg-[#0A66C2]' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-600', dot: 'bg-emerald-500', bar: 'bg-emerald-500' },
    violet: { bg: 'bg-violet-50', text: 'text-violet-600', dot: 'bg-violet-500', bar: 'bg-violet-500' },
    amber: { bg: 'bg-amber-50', text: 'text-amber-600', dot: 'bg-amber-500', bar: 'bg-amber-500' },
    red: { bg: 'bg-red-50', text: 'text-red-600', dot: 'bg-red-500', bar: 'bg-red-500' },
    indigo: { bg: 'bg-indigo-50', text: 'text-indigo-600', dot: 'bg-indigo-500', bar: 'bg-indigo-500' },
    rose: { bg: 'bg-rose-50', text: 'text-rose-600', dot: 'bg-rose-500', bar: 'bg-rose-500' },
  };
  const c = colors[color] || colors.blue;

  return (
    <div className="bg-white rounded-xl border border-slate-200/60 p-5 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 group">
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2.5 rounded-xl ${c.bg}`}>
          <Icon size={20} className={c.text} />
        </div>
        {trend !== undefined && (
          <span className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full ${
            trend > 0 ? 'bg-emerald-50 text-emerald-700' : 
            trend < 0 ? 'bg-red-50 text-red-600' : 
            'bg-slate-50 text-slate-500'
          }`}>
            {trend > 0 ? <ChevronUp size={12} /> : trend < 0 ? <ChevronDown size={12} /> : null}
            {trend > 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
      <p className="text-3xl font-bold text-slate-900 mb-1">{value}</p>
      <p className="text-sm font-medium text-slate-600">{label}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      {sparkline && (
        <div className="mt-3 flex justify-center">
          <Sparkline data={sparkline} color={color === 'blue' ? '#0A66C2' : 
            color === 'emerald' ? '#059669' : 
            color === 'violet' ? '#7C3AED' : 
            color === 'amber' ? '#D97706' : 
            color === 'red' ? '#DC2626' : '#4F46E5'} />
        </div>
      )}
      {progress !== undefined && (
        <div className="mt-3">
          <ProgressBar value={progress.value} max={progress.max} color={c.bar} label={progress.label} />
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD PRINCIPAL
// ═══════════════════════════════════════════════════════════════

const Dashboard = ({ stats, posts, setActiveTab }) => {
  const [outreachStats, setOutreachStats] = useState(null);
  const [trendsData, setTrendsData] = useState(null);
  const [loadingOutreach, setLoadingOutreach] = useState(true);
  const [loadingTrends, setLoadingTrends] = useState(true);

  useEffect(() => {
    const fetchOutreach = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const r = await fetch(`${API_URL}/outreach/status`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (r.ok) setOutreachStats(await r.json());
      } catch (e) { console.error(e); }
      finally { setLoadingOutreach(false); }
    };
    fetchOutreach();
  }, []);

  useEffect(() => {
    const fetchTrends = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const r = await fetch(`${API_URL}/trends/current`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (r.ok) setTrendsData(await r.json());
      } catch (e) { console.error(e); }
      finally { setLoadingTrends(false); }
    };
    fetchTrends();
  }, []);

  // Données des posts
  const postStatusData = [
    { label: 'Published', value: stats.posted || 0, color: '#059669' },
    { label: 'Scheduled', value: stats.approved || 0, color: '#0A66C2' },
    { label: 'Pending', value: stats.pending || 0, color: '#D97706' },
    { label: 'Failed', value: stats.failed || 0, color: '#DC2626' },
  ].filter(d => d.value > 0);

  // Données des tendances
  const currentWeekTrends = trendsData?.grouped_by_week?.find(w => w.is_current)?.trends || [];
  const topTrends = currentWeekTrends.slice(0, 5);
  const totalArticles = currentWeekTrends.reduce((sum, t) => sum + (t.article_count || 0), 0);
  const trendsCount = trendsData?.trends_count || currentWeekTrends.length;
  const currentWeekLabel = trendsData?.current_week_label || '';

  // Sparkline simulée pour les posts (7 derniers jours)
  const postsSparkline = Array.isArray(posts) ? 
    Array.from({ length: 7 }, (_, i) => 
      posts.filter(p => {
        const d = new Date(p.created_at);
        const now = new Date();
        const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
        return diff === (6 - i);
      }).length
    ) : [0, 0, 0, 0, 0, 0, 0];

  // Tendance des scores
  const trendScores = topTrends.map(t => ({
    label: t.trend_name?.substring(0, 15) || '—',
    value: t.strength || 0
  }));

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* ═══ HERO BANNER ═══ */}
      <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl p-8 shadow-xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-400/10 rounded-full translate-y-1/2 -translate-x-1/2 blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 w-48 h-48 bg-white/5 rounded-full -translate-x-1/2 -translate-y-1/2 blur-2xl"></div>
        
        <div className="relative z-10">
          <h1 className="text-3xl md:text-4xl font-bold text-white leading-tight mb-2">
            Dashboard
          </h1>
          <p className="text-blue-200/90 text-sm max-w-2xl">
            Real-time overview of your LinkedIn content strategy, outreach performance, and market intelligence.
          </p>
        </div>
      </div>

      {/* ═══ TOP KPI ROW ═══ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard 
          icon={FileText} 
          label="Total Posts" 
          value={stats.total || 0} 
          sub={`${stats.posted || 0} published · ${stats.approved || 0} scheduled`}
          color="blue" 
          trend={12.5}
          sparkline={postsSparkline}
        />
        <MetricCard 
          icon={Users} 
          label="Profiles Found" 
          value={outreachStats?.total_profiles || 0} 
          sub={`${outreachStats?.invitations_sent || 0} invites sent`}
          color="indigo" 
          progress={outreachStats ? { value: outreachStats.invitations_sent || 0, max: outreachStats.total_profiles || 1, label: 'Invitation rate' } : undefined}
        />
        <MetricCard 
          icon={Flame} 
          label="Active Trends" 
          value={trendsCount} 
          sub={`${totalArticles} articles analyzed`}
          color="red" 
          trend={trendsCount > 0 ? 8.3 : 0}
        />
        <MetricCard 
          icon={Activity} 
          label="Engagement Rate" 
          value={`${stats.posted > 0 ? Math.round((stats.posted / Math.max(stats.total, 1)) * 100) : 0}%`}
          sub={`${stats.posted || 0} of ${stats.total || 0} posts live`}
          color="emerald" 
          trend={5.2}
        />
      </div>

      {/* ═══ MAIN GRID : GRAPHIQUES + LISTS ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* ── Colonne Gauche : Distribution des Posts ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <PieChart size={16} className="text-slate-500" />
              Post Distribution
            </h3>
            <button onClick={() => setActiveTab('posts')} className="text-xs text-[#0A66C2] font-semibold hover:underline">
              Details →
            </button>
          </div>
          <div className="flex items-center justify-center mb-4">
            <DonutChart segments={postStatusData.length > 0 ? postStatusData : [{ label: 'Empty', value: 1, color: '#E2E8F0' }]} size={120} />
          </div>
          <div className="space-y-2">
            {postStatusData.map((seg, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: seg.color }}></span>
                  <span className="text-slate-600">{seg.label}</span>
                </div>
                <span className="font-bold text-slate-900">{seg.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Colonne Centre : Tendances du Moment ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Zap size={16} className="text-amber-500" />
              Top Trends
            </h3>
            <button onClick={() => setActiveTab('trends')} className="text-xs text-[#0A66C2] font-semibold hover:underline">
              Explore →
            </button>
          </div>
          {topTrends.length > 0 ? (
            <>
              <div className="mb-4">
                <MiniBarChart data={trendScores} height={50} color="#0A66C2" />
              </div>
              <div className="space-y-2">
                {topTrends.slice(0, 3).map((trend, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-2 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors" onClick={() => setActiveTab('trends')}>
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      idx === 0 ? 'bg-red-100 text-red-600' : 
                      idx === 1 ? 'bg-orange-100 text-orange-600' : 
                      'bg-blue-100 text-blue-600'
                    }`}>
                      {idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-900 truncate">{trend.trend_name}</p>
                      <p className="text-xs text-slate-400">{trend.article_count || 0} articles · Score {trend.strength || 0}</p>
                    </div>
                    <ProgressBar value={trend.strength || 0} max={100} color="bg-amber-500" />
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-8">
              <Flame size={32} className="text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No trends yet</p>
            </div>
          )}
        </div>

        {/* ── Colonne Droite : Derniers Posts ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Clock size={16} className="text-slate-500" />
              Recent Activity
            </h3>
            <button onClick={() => setActiveTab('posts')} className="text-xs text-[#0A66C2] font-semibold hover:underline">
              View all →
            </button>
          </div>
          {Array.isArray(posts) && posts.length > 0 ? (
            <div className="space-y-2">
              {posts.slice(0, 5).map((post, idx) => (
                <div key={post.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors border border-transparent hover:border-slate-200" onClick={() => setActiveTab('posts')}>
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    post.status === 'posted' ? 'bg-emerald-500' :
                    post.status === 'approved' ? 'bg-blue-500' :
                    post.status === 'rejected' ? 'bg-red-500' :
                    'bg-amber-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{post.topic || 'Untitled'}</p>
                    <p className="text-xs text-slate-400">
                      {post.status || 'pending'} · {post.scheduled_time ? new Date(post.scheduled_time).toLocaleDateString() : 'Not scheduled'}
                    </p>
                  </div>
                  {post.image_url && (
                    <div className="w-8 h-8 rounded-md bg-slate-100 overflow-hidden flex-shrink-0">
                      <img src={post.image_url.startsWith('http') ? post.image_url : `${API_URL}${post.image_url}`} className="w-full h-full object-cover" alt="" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <FileText size={32} className="text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No posts yet</p>
            </div>
          )}
        </div>
      </div>

      {/* ═══ BOTTOM GRID : OUTREACH + QUICK STATS ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* ── Outreach Summary ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Users size={16} className="text-indigo-500" />
              Outreach Performance
            </h3>
            <button onClick={() => setActiveTab('outreach')} className="text-xs text-[#0A66C2] font-semibold hover:underline">
              Manage →
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-indigo-50 rounded-xl p-4">
              <p className="text-xs text-indigo-600 font-semibold mb-1">Profiles Found</p>
              <p className="text-2xl font-bold text-indigo-900">{outreachStats?.profiles_found || 0}</p>
            </div>
            <div className="bg-emerald-50 rounded-xl p-4">
              <p className="text-xs text-emerald-600 font-semibold mb-1">Invites Sent</p>
              <p className="text-2xl font-bold text-emerald-900">{outreachStats?.invitations_sent || 0}</p>
            </div>
          </div>
          <ProgressBar 
            value={outreachStats?.invitations_sent || 0} 
            max={outreachStats?.total_profiles || 1} 
            color="bg-indigo-500" 
            label="Invitation Progress" 
          />
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
            <span>Daily limit: {outreachStats?.daily_remaining || 0}/{outreachStats?.daily_limit || 30}</span>
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              {outreachStats?.linkedin_email || 'Not connected'}
            </span>
          </div>
        </div>

        {/* ── Market Intelligence ── */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Globe size={16} className="text-blue-500" />
              Market Intelligence
            </h3>
            <button onClick={() => setActiveTab('trends')} className="text-xs text-[#0A66C2] font-semibold hover:underline">
              Explore →
            </button>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Newspaper size={14} className="text-slate-400" />
                <span className="text-sm text-slate-600">Articles Tracked</span>
              </div>
              <span className="text-sm font-bold text-slate-900">{totalArticles}</span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target size={14} className="text-slate-400" />
                <span className="text-sm text-slate-600">Categories</span>
              </div>
              <span className="text-sm font-bold text-slate-900">
                {currentWeekTrends.length > 0 ? [...new Set(currentWeekTrends.map(t => t.category).filter(Boolean))].length : 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Award size={14} className="text-slate-400" />
                <span className="text-sm text-slate-600">Dominant Trends</span>
              </div>
              <span className="text-sm font-bold text-slate-900">
                {currentWeekTrends.filter(t => (t.strength || 0) >= 80).length}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar size={14} className="text-slate-400" />
                <span className="text-sm text-slate-600">Current Week</span>
              </div>
              <span className="text-sm font-bold text-slate-900">{currentWeekLabel || '—'}</span>
            </div>
          </div>
          {topTrends.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Trend Strength</p>
              <div className="space-y-1.5">
                {topTrends.slice(0, 3).map((trend, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="text-xs text-slate-600 w-20 truncate">{trend.trend_name?.substring(0, 12)}</span>
                    <div className="flex-1">
                      <ProgressBar value={trend.strength || 0} max={100} color={idx === 0 ? 'bg-red-500' : idx === 1 ? 'bg-orange-500' : 'bg-blue-500'} />
                    </div>
                    <span className="text-xs font-bold text-slate-700 w-8 text-right">{trend.strength || 0}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
     
    </div>
  );
};

export default Dashboard;