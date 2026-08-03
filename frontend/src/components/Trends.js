import React, { useState, useEffect, useMemo } from 'react';
import {
  TrendingUp, ExternalLink, RefreshCw, Loader,
  Zap, Flame, TrendingDown, BarChart3, Hash,
  Filter, ChevronRight, Search, Sparkles, FileText,
  CheckCircle, AlertCircle, X, Calendar, Clock, Globe,
  ChevronDown, Newspaper, Database
} from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function getStrengthTier(strength) {
  if (strength >= 80) return { tier: 'dominant', label: 'Dominant', icon: Flame, color: 'text-red-600 bg-red-50 border-red-200' };
  if (strength >= 60) return { tier: 'strong', label: 'Strong', icon: TrendingUp, color: 'text-orange-600 bg-orange-50 border-orange-200' };
  if (strength >= 40) return { tier: 'emerging', label: 'Emerging', icon: Zap, color: 'text-blue-600 bg-blue-50 border-blue-200' };
  return { tier: 'weak', label: 'Early Signal', icon: TrendingDown, color: 'text-slate-500 bg-slate-50 border-slate-200' };
}

// ═══════════════════════════════════
// POPUP: Post Configuration
// ═══════════════════════════════════
function PostConfigPopup({ trend, onConfirm, onCancel, isPosting }) {
  const [language, setLanguage] = useState('english');
  const [scheduleDate, setScheduleDate] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [scheduleTime, setScheduleTime] = useState('09:00');

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        <div className="bg-gradient-to-r from-[#0A66C2] to-[#004182] p-5 text-white flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold">Generate Post</h3>
            <p className="text-blue-200 text-sm mt-0.5 truncate max-w-sm">{trend?.trend_name || 'Selected Trend'}</p>
          </div>
          <button onClick={onCancel} className="p-2 hover:bg-white/20 rounded-full transition-colors">
            <X size={20} />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Language</label>
            <div className="grid grid-cols-2 gap-2">
              {['english', 'french'].map(l => (
                <button key={l} onClick={() => setLanguage(l)}
                  className={`py-2.5 rounded-xl font-semibold text-sm border-2 transition-all ${
                    language === l ? 'bg-blue-50 border-[#0A66C2] text-[#0A66C2]' : 'bg-slate-50 border-slate-200 text-slate-600'
                  }`}>
                  {l === 'english' ? 'English' : 'Français'}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Date</label>
              <input type="date" value={scheduleDate} onChange={e => setScheduleDate(e.target.value)}
                min={new Date().toISOString().split('T')[0]}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#0A66C2] outline-none bg-slate-50" />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Time</label>
              <input type="time" value={scheduleTime} onChange={e => setScheduleTime(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#0A66C2] outline-none bg-slate-50" />
            </div>
          </div>
        </div>
        <div className="px-5 pb-5 flex gap-3">
          <button onClick={onCancel} className="flex-1 py-2.5 text-sm font-semibold text-slate-600 bg-slate-100 rounded-xl hover:bg-slate-200 transition-colors">Cancel</button>
          <button onClick={() => onConfirm({ language, schedule_date: scheduleDate, schedule_time: scheduleTime })}
            disabled={isPosting}
            className="flex-1 py-2.5 text-sm font-bold text-white bg-gradient-to-r from-[#0A66C2] to-[#004182] rounded-xl hover:shadow-lg disabled:opacity-50 transition-all flex items-center justify-center gap-2">
            {isPosting ? <><Loader size={14} className="animate-spin" />Creating...</> : <><Sparkles size={14} />Generate Post</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════
// POPUP: Success
// ═══════════════════════════════════
function SuccessPopup({ postId, hasImage, scheduledFor, onViewPosts, onClose }) {
  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden text-center">
        <div className="bg-emerald-500 p-5">
          <div className="w-14 h-14 bg-white rounded-full flex items-center justify-center mx-auto shadow-lg">
            <CheckCircle size={32} className="text-emerald-500" />
          </div>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Post Generated!</h3>
            <p className="text-sm text-slate-500">#{postId} created successfully</p>
          </div>
          {scheduledFor && (
            <p className="text-xs text-slate-400">Scheduled for {new Date(scheduledFor).toLocaleString()}</p>
          )}
        </div>
        <div className="px-5 pb-5 flex gap-3">
          <button onClick={onClose} className="flex-1 py-2.5 text-sm font-semibold text-slate-600 bg-slate-100 rounded-xl hover:bg-slate-200 transition-colors">Close</button>
          <button onClick={onViewPosts} className="flex-1 py-2.5 text-sm font-bold text-white bg-gradient-to-r from-[#0A66C2] to-[#004182] rounded-xl hover:shadow-lg transition-all">View Posts</button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════
// TREND CARD
// ═══════════════════════════════════
function TrendCard({ trend, isCurrentWeek }) {
  const [expanded, setExpanded] = useState(false);
  const { tier, label, icon: TierIcon, color } = getStrengthTier(trend.strength);

  const parseJSONB = (data) => {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (typeof data === 'string') {
      try { return JSON.parse(data); }
      catch { return []; }
    }
    return [];
  };

  const sourceArticles = parseJSONB(trend.source_articles);
  const postIdeas = parseJSONB(trend.post_ideas || trend.linkedin_post_ideas);

  return (
    <div className={`rounded-xl border transition-all ${
      expanded ? 'border-slate-300 shadow-sm bg-white' : 
      isCurrentWeek ? 'border-slate-200 bg-white hover:border-slate-300' : 
      'border-slate-200 bg-slate-50/80'
    }`}>
      <button onClick={() => setExpanded(!expanded)} className="w-full p-4 text-left flex items-start gap-3">
        <div className="flex-shrink-0 flex flex-col items-center">
          <span className={`text-lg font-bold ${isCurrentWeek ? 'text-slate-900' : 'text-slate-400'}`}>
            #{trend.id || '?'}
          </span>
          <div className={`mt-1 px-2 py-0.5 rounded-full text-xs font-bold border ${color}`}>
            {trend.strength}/100
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <h4 className={`font-bold text-sm ${isCurrentWeek ? 'text-slate-900' : 'text-slate-500'}`}>
              {trend.trend_name}
            </h4>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${color}`}>
              <TierIcon size={10} />{label}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1"><Hash size={10} />{trend.category || 'uncategorized'}</span>
            <span className="inline-flex items-center gap-1"><Newspaper size={10} />{trend.article_count || 0} articles</span>
            {trend.research_date && (
              <span className="inline-flex items-center gap-1"><Calendar size={10} />{trend.research_date}</span>
            )}
          </div>
        </div>
        <ChevronRight size={16} className={`flex-shrink-0 mt-1 transition-transform text-slate-300 ${expanded ? 'rotate-90' : ''}`} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-3">
          {trend.evidence && (
            <div>
              <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">Evidence</h5>
              <p className="text-xs text-slate-600 leading-relaxed">{trend.evidence}</p>
            </div>
          )}
          
          {trend.why_matters && (
            <div>
              <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">Why It Matters</h5>
              <p className="text-xs text-slate-600 leading-relaxed">{trend.why_matters}</p>
            </div>
          )}
          
          {sourceArticles.length > 0 && (
            <div>
              <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Sources</h5>
              <div className="space-y-1">
                {sourceArticles.slice(0, 3).map((article, i) => (
                  <a key={i} href={article.url || '#'} target="_blank" rel="noopener noreferrer"
                    className="flex items-start gap-2 p-2 rounded-lg hover:bg-blue-50 transition-all group">
                    <ExternalLink size={12} className="text-slate-400 group-hover:text-[#0A66C2] flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-slate-600 group-hover:text-[#0A66C2] leading-snug line-clamp-2">
                      {article.title || article.headline || 'Untitled Article'}
                    </p>
                  </a>
                ))}
              </div>
            </div>
          )}

          {postIdeas.length > 0 && (
            <div>
              <h5 className="text-xs font-bold text-slate-500 uppercase tracking-wide mb-2">Post Ideas</h5>
              <div className="space-y-1">
                {postIdeas.slice(0, 2).map((idea, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-600">
                    <span className="w-4 h-4 rounded-full bg-blue-100 text-[#0A66C2] flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">{i + 1}</span>
                    <p className="line-clamp-2">{typeof idea === 'string' ? idea : idea.idea || idea.title || 'No idea text'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {isCurrentWeek && (
            <button onClick={() => window.__openPostConfig?.(trend)}
              className="w-full py-2.5 rounded-lg text-sm font-bold text-white bg-gradient-to-r from-[#0A66C2] to-[#004182] hover:shadow-md transition-all flex items-center justify-center gap-2">
              <Sparkles size={14} />Generate Post from Trend
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════
export default function Trends() {
  const [groupedWeeks, setGroupedWeeks] = useState([]);
  const [meta, setMeta] = useState({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [filter, setFilter] = useState('all');
  const [expandedWeeks, setExpandedWeeks] = useState({});
  const [configPopup, setConfigPopup] = useState(null);
  const [successPopup, setSuccessPopup] = useState(null);
  const [postingTrendName, setPostingTrendName] = useState(null);
  const [postResult, setPostResult] = useState(null);
  const [fetchError, setFetchError] = useState(null);

  const fetchTrends = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/trends/current`, { 
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        } 
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('📊 Trends data received:', data); // Debug
      
      if (data.grouped_by_week && Array.isArray(data.grouped_by_week) && data.grouped_by_week.length > 0) {
        setGroupedWeeks(data.grouped_by_week);
        const expanded = {};
        data.grouped_by_week.forEach(w => { 
          if (w.is_current) expanded[w.week_key] = true; 
        });
        // Si aucune semaine n'est marquée comme courante, ouvrir la première
        if (Object.keys(expanded).length === 0 && data.grouped_by_week.length > 0) {
          expanded[data.grouped_by_week[0].week_key] = true;
        }
        setExpandedWeeks(expanded);
        setMeta({
          current_week_label: data.current_week_label || '',
          weeks_count: data.weeks_count || data.grouped_by_week.length,
          trends_count: data.trends_count || data.grouped_by_week.reduce((s, w) => s + (w.trends?.length || 0), 0),
          status: 'ok'
        });
      } else {
        console.log('📊 No trends data in response');
        setMeta({ status: 'no_data' });
        setGroupedWeeks([]);
      }
    } catch (e) {
      console.error('❌ Error fetching trends:', e);
      setFetchError(e.message);
      setMeta({ status: 'error' });
      setGroupedWeeks([]);
    } finally {
      setLoading(false);
    }
  };

  const generateTrends = async () => {
    setGenerating(true);
    setFetchError(null);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/trends/generate`, { 
        method: 'POST', 
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        } 
      });
      
      if (!response.ok) {
        throw new Error(`Generation failed with status: ${response.status}`);
      }
      
      // Attendre puis rafraîchir
      setTimeout(() => {
        fetchTrends();
        setGenerating(false);
      }, 3000);
    } catch (e) {
      console.error('❌ Error generating trends:', e);
      setFetchError(e.message);
      setGenerating(false);
    }
  };

  useEffect(() => { 
    fetchTrends(); 
  }, []);
  
  useEffect(() => {
    window.__openPostConfig = (trend) => setConfigPopup({ trend });
    return () => { delete window.__openPostConfig; };
  }, []);

  const handleViewPosts = () => {
    setSuccessPopup(null);
    if (window.switchToPostsTab) window.switchToPostsTab();
  };

  const handleConfirmGenerate = async (config) => {
    const trend = configPopup?.trend;
    if (!trend) return;
    setConfigPopup(null);
    setPostingTrendName(trend.trend_name);
    try {
      const token = localStorage.getItem('access_token');
      const r = await fetch(`${API_URL}/trends/generate-post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          trend_name: trend.trend_name, 
          category: trend.category || '',
          evidence: trend.evidence || '', 
          why_matters: trend.why_matters || '',
          post_ideas: trend.post_ideas || [], 
          source_articles: trend.source_articles || [],
          language: config.language, 
          schedule_date: config.schedule_date, 
          schedule_time: config.schedule_time,
        }),
      });
      const data = await r.json();
      if (data.success) {
        setSuccessPopup({ postId: data.post_id, hasImage: data.has_image, scheduledFor: data.scheduled_for });
      } else {
        setPostResult({ success: false, message: data.detail || 'Error generating post' });
        setTimeout(() => setPostResult(null), 5000);
      }
    } catch (e) {
      setPostResult({ success: false, message: e.message });
      setTimeout(() => setPostResult(null), 5000);
    } finally {
      setPostingTrendName(null);
    }
  };

  const toggleWeek = (weekKey) => setExpandedWeeks(prev => ({ ...prev, [weekKey]: !prev[weekKey] }));

  const allTrendsForStats = useMemo(() => {
    return groupedWeeks.flatMap(w => w.trends);
  }, [groupedWeeks]);

  const counts = useMemo(() => {
    const result = { dominant: 0, strong: 0, emerging: 0, weak: 0 };
    allTrendsForStats.forEach(t => {
      const tier = getStrengthTier(t.strength).tier;
      result[tier] = (result[tier] || 0) + 1;
    });
    return result;
  }, [allTrendsForStats]);

  const filteredWeeks = useMemo(() => {
    return groupedWeeks.map(week => ({
      ...week,
      trends: week.trends.filter(t => filter === 'all' || getStrengthTier(t.strength).tier === filter),
    })).filter(w => w.trends.length > 0);
  }, [groupedWeeks, filter]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <Loader size={32} className="animate-spin text-[#0A66C2]" />
        <p className="text-sm text-slate-500">Loading trends from database...</p>
      </div>
    );
  }

  if (!loading && meta.status === 'no_data') {
    return (
      <div className="space-y-6">
        <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl shadow-lg p-6">
          <div className="relative z-10">
            <h1 className="text-2xl md:text-3xl font-bold text-white">Trend Intelligence</h1>
            <p className="text-blue-100/80 text-sm mt-1">AI-powered water treatment trend discovery</p>
          </div>
        </div>
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-16 flex flex-col items-center justify-center text-center">
          <div className="bg-slate-50 p-6 rounded-full mb-6">
            <Database size={64} className="text-slate-300" />
          </div>
          <h2 className="text-xl font-bold text-slate-700 mb-2">No Trends in Database</h2>
          <p className="text-slate-500 max-w-md mb-6">
            Generate new trends to populate the database and start creating content.
          </p>
          <div className="flex gap-3">
            <button onClick={fetchTrends}
              className="flex items-center gap-2 bg-white border border-slate-200 text-slate-700 px-6 py-3 rounded-xl font-semibold hover:bg-slate-50 transition-all">
              <RefreshCw size={18} /> Refresh
            </button>
            <button onClick={generateTrends} disabled={generating}
              className="flex items-center gap-2 bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white px-6 py-3 rounded-xl font-bold hover:shadow-lg disabled:opacity-50 transition-all">
              {generating ? <><Loader size={18} className="animate-spin" />Generating...</> : <><Search size={18} />Generate Trends</>}
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!loading && meta.status === 'error') {
    return (
      <div className="space-y-6">
        <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl shadow-lg p-6">
          <div className="relative z-10">
            <h1 className="text-2xl md:text-3xl font-bold text-white">Trend Intelligence</h1>
            <p className="text-blue-100/80 text-sm mt-1">AI-powered water treatment trend discovery</p>
          </div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-2xl p-8 text-center">
          <AlertCircle size={48} className="text-red-400 mx-auto mb-4" />
          <p className="text-red-600 font-bold text-lg mb-2">Failed to Load Trends</p>
          <p className="text-red-500 text-sm mb-4">{fetchError || 'Unable to connect to the database'}</p>
          <div className="flex gap-3 justify-center">
            <button onClick={fetchTrends}
              className="flex items-center gap-2 bg-white border border-red-200 text-red-600 px-6 py-3 rounded-xl font-semibold hover:bg-red-50 transition-all">
              <RefreshCw size={18} /> Retry
            </button>
            <button onClick={generateTrends} disabled={generating}
              className="flex items-center gap-2 bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white px-6 py-3 rounded-xl font-bold hover:shadow-lg disabled:opacity-50 transition-all">
              {generating ? <><Loader size={18} className="animate-spin" />Generating...</> : <><Search size={18} />Generate New</>}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ═══ HERO HEADER ═══ */}
      <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl p-6 shadow-lg">
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-blue-400/10 rounded-full translate-y-1/2 -translate-x-1/2 blur-2xl"></div>
        
        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white leading-tight">
              Trend Intelligence
            </h1>
            <p className="text-blue-100/80 text-sm mt-1 max-w-xl">
              {meta.trends_count || allTrendsForStats.length} trends across {meta.weeks_count || groupedWeeks.length} week{(meta.weeks_count || groupedWeeks.length) !== 1 ? 's' : ''}
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2">
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {counts.dominant || 0} Dominant
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {counts.strong || 0} Strong
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {counts.emerging || 0} Emerging
              </span>
            </div>
            
            <button onClick={fetchTrends}
              className="bg-white/20 backdrop-blur-sm text-white p-2.5 rounded-xl hover:bg-white/30 transition-all" title="Refresh">
              <RefreshCw size={16} />
            </button>
            
            <button onClick={generateTrends} disabled={generating}
              className="bg-white text-[#0A66C2] px-5 py-2.5 rounded-xl font-bold text-sm hover:bg-blue-50 transition-all shadow-lg flex items-center gap-2 group disabled:opacity-50">
              {generating ? <><Loader size={16} className="animate-spin" /> Scanning...</> : <><Search size={16} /> Generate New</>}
            </button>
          </div>
        </div>
      </div>

      {/* ═══ ERROR NOTIFICATION ═══ */}
      {postResult && !postResult.success && (
        <div className="p-4 rounded-xl border bg-red-50 border-red-200 text-red-800 flex items-center gap-2">
          <AlertCircle size={18} />
          <p className="text-sm font-semibold">{postResult.message}</p>
        </div>
      )}

      {/* ═══ FILTERS ═══ */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter size={14} className="text-slate-400" />
        {[
          { key: 'all', label: 'All', count: allTrendsForStats.length },
          { key: 'dominant', label: 'Dominant', count: counts.dominant },
          { key: 'strong', label: 'Strong', count: counts.strong },
          { key: 'emerging', label: 'Emerging', count: counts.emerging },
          { key: 'weak', label: 'Early', count: counts.weak },
        ].map(f => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all border ${
              filter === f.key
                ? 'bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white border-transparent shadow-md'
                : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
            }`}>
            {f.label} ({f.count})
          </button>
        ))}
      </div>

      {/* ═══ TRENDS LIST ═══ */}
      <div className="space-y-6">
        {filteredWeeks.map(week => (
          <div key={week.week_key} className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <button 
                onClick={() => toggleWeek(week.week_key)}
                className="flex items-center gap-2 text-left hover:opacity-80 transition-opacity"
              >
                <h3 className={`text-sm font-bold ${week.is_current ? 'text-slate-900' : 'text-slate-500'}`}>
                  {week.week_label}
                </h3>
                {week.is_current && (
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                )}
                <span className="text-xs text-slate-400">· {week.trends.length} trends</span>
                <ChevronDown size={14} className={`text-slate-400 transition-transform ${expandedWeeks[week.week_key] ? 'rotate-180' : ''}`} />
              </button>
            </div>
            
            {expandedWeeks[week.week_key] && (
              <div className="space-y-2">
                {week.trends.map((trend, idx) => (
                  <TrendCard key={trend.id || idx} trend={trend} isCurrentWeek={week.is_current} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {filteredWeeks.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <TrendingUp size={48} className="mx-auto mb-3 opacity-30" />
          <p>No trends match this filter</p>
        </div>
      )}

      {/* ═══ POPUPS ═══ */}
      {configPopup && <PostConfigPopup trend={configPopup.trend} isPosting={!!postingTrendName} onConfirm={handleConfirmGenerate} onCancel={() => setConfigPopup(null)} />}
      {successPopup && <SuccessPopup postId={successPopup.postId} hasImage={successPopup.hasImage} scheduledFor={successPopup.scheduledFor} onViewPosts={handleViewPosts} onClose={() => setSuccessPopup(null)} />}
    </div>
  );
}