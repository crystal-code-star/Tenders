import React, { useState, useEffect, useRef } from 'react';
import { 
  Plus, Trash2, ChevronDown, ToggleLeft, ToggleRight, 
  Loader, X, Calendar, Clock, Sparkles, ChevronRight, CheckCircle, 
  AlertCircle, Ban, Zap, ChevronLeft, Eye, EyeOff, Edit3, FileText,
  Wand2, Keyboard, Lightbulb, ArrowRight
} from 'lucide-react';
import { useToast } from '../App';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ANGLE_COLORS = {
  Problem: 'bg-red-50 text-red-700 border-red-200',
  'Deep Problem': 'bg-orange-50 text-orange-700 border-orange-200',
  Education: 'bg-blue-50 text-blue-700 border-blue-200',
  'Product Focus': 'bg-violet-50 text-violet-700 border-violet-200',
  'Case Study': 'bg-emerald-50 text-emerald-700 border-emerald-200',
  Technical: 'bg-slate-100 text-slate-700 border-slate-200',
  Comparison: 'bg-amber-50 text-amber-700 border-amber-200',
  Engagement: 'bg-rose-50 text-rose-700 border-rose-200',
};

const DEFAULT_DAYS = [
  { day_number: 1, angle: 'Problem', custom_text: '', enabled: true },
  { day_number: 2, angle: 'Deep Problem', custom_text: '', enabled: true },
  { day_number: 3, angle: 'Education', custom_text: '', enabled: true },
  { day_number: 4, angle: 'Product Focus', custom_text: '', enabled: true },
  { day_number: 5, angle: 'Case Study', custom_text: '', enabled: true },
  { day_number: 6, angle: 'Technical', custom_text: '', enabled: true },
  { day_number: 7, angle: 'Engagement', custom_text: '', enabled: true },
];

export default function Generate({ onSuccess, setActiveTab }) {
  const toast = useToast();
  
  const [mode, setMode] = useState('ai');
  const [lang, setLang] = useState('english');
  const [query, setQuery] = useState('');
  const [days, setDays] = useState(DEFAULT_DAYS);
  const [angles, setAngles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const abortRef = useRef(null);
  const [startDate, setStartDate] = useState(() => {
    const t = new Date(); t.setDate(t.getDate() + 1);
    return t.toISOString().split('T')[0];
  });
  const [startTime, setStartTime] = useState('09:00');

  const n = days.filter(d => d.enabled).length;

  useEffect(() => {
    const t = localStorage.getItem('access_token');
    fetch(`${API_URL}/angles`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.json())
      .then(d => setAngles(d.angles || []))
      .catch(() => setAngles([
        { key: 'Problem', name: 'Problem Awareness' }, { key: 'Deep Problem', name: 'Hidden Costs' },
        { key: 'Education', name: 'Science & Technology' }, { key: 'Product Focus', name: 'Product Deep Dive' },
        { key: 'Case Study', name: 'Before & After' }, { key: 'Technical', name: 'Technical Specs' },
        { key: 'Comparison', name: 'Why This Solution' }, { key: 'Engagement', name: 'Community Quiz' },
      ]));
  }, []);

  const upd = (i, f, v) => setDays(p => p.map((d, j) => j === i ? { ...d, [f]: v } : d));
  const tog = (i) => setDays(p => p.map((d, j) => j === i ? { ...d, enabled: !d.enabled } : d));
  const addDay = () => {
    const num = days.length > 0 ? Math.max(...days.map(d => d.day_number)) + 1 : 1;
    setDays(p => [...p, { day_number: num, angle: 'Problem', custom_text: '', enabled: true }]);
  };
  const del = (i) => setDays(p => p.filter((_, j) => j !== i));

  const handleAIPlan = async () => {
    if (!query.trim()) { toast.warning('Please enter a topic'); return; }
    if (n === 0) { toast.warning('Enable at least one day'); return; }
    
    setPlanning(true);
    const enabledAngles = [...new Set(days.filter(d => d.enabled).map(d => d.angle))];
    
    try {
      const t = localStorage.getItem('access_token');
      const r = await fetch(`${API_URL}/plan-campaign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
        body: JSON.stringify({ brief: query.trim(), language: lang, angle_keys: enabledAngles }),
      });
      
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Failed'); }
      const data = await r.json();
      
      const instructions = data.day_instructions || {};
      setDays(prev => prev.map(d => {
        if (!d.enabled) return d;
        const instruction = instructions[d.angle] || d.custom_text;
        return { ...d, custom_text: instruction, ai_suggested: true };
      }));
      
      setAiResult(data);
      toast.success('AI topics generated! Review below');
    } catch (e) {
      toast.error(e.message || 'Planning failed');
    } finally {
      setPlanning(false);
    }
  };

  const generate = async () => {
    if (n === 0) { toast.warning('Enable at least one day'); return; }
    
    const emptyDays = days.filter(d => d.enabled && !d.custom_text.trim());
    if (emptyDays.length > 0 && mode === 'manual') {
      toast.warning(`Day ${emptyDays[0].day_number} has no instructions`);
      return;
    }

    setLoading(true);
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const t = localStorage.getItem('access_token');
      const [y, m, d] = startDate.split('-').map(Number);
      const [h, min] = startTime.split(':').map(Number);
      const base = new Date(y, m - 1, d, h, min);
      
      const sd = days.filter(d => d.enabled).sort((a, b) => a.day_number - b.day_number).map((d, i) => {
        const pd = new Date(base); pd.setDate(base.getDate() + i);
        return { ...d, scheduled_for: pd.toISOString(), day_products: [] };
      });

      const r = await fetch(`${API_URL}/generate-campaign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
        body: JSON.stringify({
          product_query: query || 'water treatment',
          language: lang,
          days: sd,
          schedule_config: { start_date: startDate, start_time: startTime, interval_hours: 24 }
        }),
        signal: ac.signal,
      });

      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || 'Failed'); }
      const data = await r.json();
      
      const f = new Date(startDate + 'T' + startTime);
      const l = new Date(f); l.setDate(f.getDate() + (n - 1));
      toast.success(`${data.days_enabled} posts generated — ${f.toLocaleDateString()} → ${l.toLocaleDateString()}`, 5000);

      if (onSuccess) onSuccess();
      if (setActiveTab) setActiveTab('posts');
    } catch (e) {
      if (e.name === 'AbortError') return;
      toast.error(e.message || 'Generation failed', 5000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* ═══ HERO HEADER ═══ */}
      <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl shadow-lg">
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-blue-400/10 rounded-full translate-y-1/2 -translate-x-1/2 blur-2xl"></div>
        
        <div className="relative z-10 p-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-bold text-white leading-tight">
                Generate Campaign
              </h1>
              <p className="text-blue-100/80 text-sm mt-1 max-w-xl">
                {mode === 'ai' ? 'AI generates topics for each day' : 'Write your own instructions per day'}
              </p>
            </div>
            
            {/* Mode Selector - À DROITE */}
            <div className="flex items-center gap-2 bg-white/10 backdrop-blur-sm p-1.5 rounded-xl border border-white/20">
              <button
                onClick={() => { setMode('ai'); setAiResult(null); }}
                className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 ${
                  mode === 'ai' 
                    ? 'bg-white text-[#0A66C2] shadow-md' 
                    : 'text-white/70 hover:text-white hover:bg-white/10'
                }`}
              >
                <Wand2 size={14} /> AI-Powered
              </button>
              <button
                onClick={() => { setMode('manual'); setAiResult(null); }}
                className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 ${
                  mode === 'manual' 
                    ? 'bg-white text-[#0A66C2] shadow-md' 
                    : 'text-white/70 hover:text-white hover:bg-white/10'
                }`}
              >
                <Keyboard size={14} /> Manual Input
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ MAIN LAYOUT: Structure (Left) + Content (Right) ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        
        {/* ═══ LEFT: Campaign Structure ═══ */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                  <FileText size={16} className="text-[#0A66C2]" />
                  Campaign Structure
                </h3>
                <span className="text-xs text-slate-400">{n}/{days.length} enabled</span>
              </div>
            </div>
            
            <div className="p-4 space-y-2">
              {days.map((day, i) => {
                const ac = ANGLE_COLORS[day.angle] || 'bg-slate-100 text-slate-600 border-slate-200';
                const hasContent = day.custom_text?.trim();
                return (
                  <div key={i} className={`rounded-xl border transition-all ${
                    day.enabled ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50 opacity-50'
                  }`}>
                    <div className="flex items-center gap-3 px-3 py-3">
                      <span className="w-6 h-6 rounded-md bg-slate-100 flex items-center justify-center font-bold text-slate-600 text-xs flex-shrink-0">
                        {day.day_number}
                      </span>
                      <div className="relative flex-1 min-w-0">
                        <select
                          value={day.angle}
                          onChange={e => upd(i, 'angle', e.target.value)}
                          disabled={!day.enabled}
                          className={`appearance-none w-full text-xs font-semibold px-2.5 py-1.5 rounded-lg border cursor-pointer outline-none truncate ${ac}`}
                        >
                          {angles.map(a => <option key={a.key} value={a.key}>{a.name || a.key}</option>)}
                        </select>
                        <ChevronDown size={10} className="absolute right-2 top-1/2 -translate-y-1/2 opacity-40 pointer-events-none" />
                      </div>
                      {hasContent && (
                        <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" title="Has instructions" />
                      )}
                      <button onClick={() => tog(i)} className="flex-shrink-0">
                        {day.enabled ? <Eye size={14} className="text-emerald-500" /> : <EyeOff size={14} className="text-slate-300" />}
                      </button>
                      <button onClick={() => del(i)} className="text-slate-300 hover:text-red-400 flex-shrink-0">
                        <Trash2 size={13} />
                      </button>
                    </div>
                    
                    {day.enabled && hasContent && (
                      <div className="px-3 pb-3">
                        <p className="text-xs text-slate-500 line-clamp-2 bg-slate-50 rounded-lg p-2">
                          {day.custom_text}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
              
              <button onClick={addDay} className="w-full py-2 border border-dashed border-slate-200 rounded-xl text-xs text-[#0A66C2] font-semibold hover:bg-blue-50 transition-colors flex items-center justify-center gap-1">
                <Plus size={12} /> Add Day
              </button>
            </div>
          </div>

          {/* Quick Summary */}
          <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
            <p className="text-sm font-bold text-slate-900 mb-2">📋 Preview</p>
            <div className="flex flex-wrap gap-1.5">
              {days.filter(d => d.enabled).map((d, i) => {
                const dayDate = new Date(new Date(startDate + 'T' + startTime).getTime() + i * 86400000);
                return (
                  <span key={i} className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${ANGLE_COLORS[d.angle] || 'bg-slate-100 text-slate-600'}`}>
                    {dayDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} · {d.angle}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* ═══ RIGHT: Content (AI or Manual) ═══ */}
        <div className="lg:col-span-3 space-y-4">
          
          {/* ═══ AI MODE ═══ */}
          {mode === 'ai' && (
            <>
              <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                  <Wand2 size={18} className="text-[#0A66C2]" />
                  <h3 className="font-bold text-slate-900">AI-Powered Generation</h3>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">
                      Describe your campaign
                    </label>
                    <textarea
                      value={query}
                      onChange={e => setQuery(e.target.value)}
                      placeholder={lang === 'french' 
                        ? 'Ex: Campagne sur l\'osmose inverse pour les hôtels, traitement des eaux...' 
                        : 'e.g. Reverse osmosis campaign for hotels, industrial water treatment...'}
                      rows={3}
                      className="w-full px-4 py-3 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#0A66C2] outline-none resize-none placeholder:text-slate-300"
                    />
                  </div>
                  
                  <div>
                    <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Language</label>
                    <div className="grid grid-cols-2 gap-3">
                      {['english', 'french'].map(l => (
                        <button
                          key={l}
                          onClick={() => setLang(l)}
                          className={`py-3 rounded-xl font-semibold text-sm border-2 transition-all ${
                            lang === l ? 'bg-blue-50 border-[#0A66C2] text-[#0A66C2] shadow-sm' : 'bg-slate-50 border-slate-200 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          {l === 'english' ? '🇬🇧 English' : '🇫🇷 French'}
                        </button>
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={handleAIPlan}
                    disabled={planning || !query.trim()}
                    className="w-full bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 hover:shadow-lg disabled:opacity-40 transition-all"
                  >
                    {planning ? (
                      <><Loader className="animate-spin" size={16} />AI is thinking...</>
                    ) : (
                      <><Lightbulb size={16} />Generate Topics for Each Day</>
                    )}
                  </button>
                </div>
              </div>

              {aiResult && (
                <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                  {aiResult.campaign_subject && (
                    <div className="bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white p-4">
                      <p className="text-xs font-bold uppercase tracking-wide text-blue-200 mb-1">Campaign Subject</p>
                      <p className="font-bold">{aiResult.campaign_subject}</p>
                    </div>
                  )}
                  <div className="p-4">
                    <h4 className="font-bold text-slate-900 text-sm mb-3">AI-Generated Instructions — Review & Edit</h4>
                    <div className="space-y-2 max-h-[40vh] overflow-y-auto">
                      {days.filter(d => d.enabled).map((day, i) => {
                        const originalIndex = days.findIndex(d => d === day);
                        return (
                          <div key={i} className="border border-slate-200 rounded-lg p-3 bg-slate-50/50">
                            <div className="flex items-center gap-2 mb-2">
                              <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${ANGLE_COLORS[day.angle] || 'bg-slate-100 text-slate-600'}`}>
                                Day {day.day_number} · {day.angle}
                              </span>
                              {day.ai_suggested && (
                                <span className="text-xs text-[#0A66C2] flex items-center gap-0.5">
                                  <Sparkles size={10} />AI
                                </span>
                              )}
                            </div>
                            <textarea
                              value={day.custom_text}
                              onChange={e => upd(originalIndex, 'custom_text', e.target.value)}
                              rows={2}
                              className="w-full text-xs p-2 bg-white border border-slate-200 rounded-lg resize-none outline-none focus:ring-2 focus:ring-[#0A66C2] placeholder:text-slate-300"
                              placeholder="No instructions yet..."
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          {/* ═══ MANUAL MODE ═══ */}
          {mode === 'manual' && (
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50">
                <div className="flex items-center gap-2">
                  <Edit3 size={16} className="text-[#0A66C2]" />
                  <h3 className="font-bold text-slate-900 text-sm">Manual Input — Write Each Day's Instructions</h3>
                </div>
              </div>
              <div className="p-4 space-y-3 max-h-[60vh] overflow-y-auto">
                {days.filter(d => d.enabled).map((day, i) => {
                  const originalIndex = days.findIndex(d => d === day);
                  const ac = ANGLE_COLORS[day.angle] || 'bg-slate-100 text-slate-600 border-slate-200';
                  return (
                    <div key={i} className="border border-slate-200 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="w-6 h-6 rounded-md bg-slate-100 flex items-center justify-center font-bold text-slate-600 text-xs">
                          {day.day_number}
                        </span>
                        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${ac}`}>
                          {day.angle}
                        </span>
                      </div>
                      <textarea
                        value={day.custom_text}
                        onChange={e => upd(originalIndex, 'custom_text', e.target.value)}
                        placeholder={`Write instructions for Day ${day.day_number}...`}
                        rows={2}
                        className="w-full text-xs p-3 bg-slate-50 border border-slate-200 rounded-lg resize-none outline-none focus:ring-2 focus:ring-[#0A66C2] placeholder:text-slate-300"
                      />
                    </div>
                  );
                })}
                {days.filter(d => d.enabled).length === 0 && (
                  <p className="text-center text-slate-400 text-sm py-8">
                    Enable at least one day in the Structure panel
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ═══ SCHEDULE ═══ */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <Calendar size={18} className="text-[#0A66C2]" />
              <h3 className="font-bold text-slate-900">Schedule</h3>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={e => setStartDate(e.target.value)}
                  min={new Date().toISOString().split('T')[0]}
                  className="w-full px-3 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#0A66C2] outline-none"
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-500 uppercase mb-1.5 block">Time</label>
                <input
                  type="time"
                  value={startTime}
                  onChange={e => setStartTime(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-[#0A66C2] outline-none"
                />
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-1.5">
              <Calendar size={12} />
              <span>{n} posts · {new Date(startDate + 'T' + startTime).toLocaleDateString()} → {new Date(new Date(startDate + 'T' + startTime).getTime() + (n-1) * 86400000).toLocaleDateString()}</span>
            </div>
          </div>

          {/* ═══ GENERATE BUTTON ═══ */}
          <button
            onClick={generate}
            disabled={loading || n === 0}
            className="w-full bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white py-4 rounded-xl font-bold text-base flex items-center justify-center gap-3 hover:shadow-xl disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <><Loader className="animate-spin" size={20} /> Generating {n} Posts...</>
            ) : (
              <><Zap size={20} /> Generate {n}-Day Campaign</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}