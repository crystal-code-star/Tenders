import React, { useState, useEffect, useRef } from 'react';
import {
  Search, Send, Users, UserPlus, UserCheck, UserX,
  Loader, MapPin, Briefcase, ExternalLink,
  Settings, RefreshCw, AlertCircle, Clock,
  Activity, X, Trash2, Info, ChevronDown,
  Sparkles, Globe
} from 'lucide-react';
import { useToast } from '../App';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const PREDEFINED_LOCATIONS = [
  { id: 'morocco', label: '🇲🇦 Morocco', value: 'Morocco' },
  { id: 'france', label: '🇫🇷 France', value: 'France' },
  { id: 'spain', label: '🇪🇸 Spain', value: 'Spain' },
  { id: 'germany', label: '🇩🇪 Germany', value: 'Germany' },
  { id: 'italy', label: '🇮🇹 Italy', value: 'Italy' },
  { id: 'uk', label: '🇬🇧 United Kingdom', value: 'United Kingdom' },
  { id: 'usa', label: '🇺🇸 United States', value: 'United States' },
  { id: 'canada', label: '🇨🇦 Canada', value: 'Canada' },
  { id: 'belgium', label: '🇧🇪 Belgium', value: 'Belgium' },
  { id: 'switzerland', label: '🇨🇭 Switzerland', value: 'Switzerland' },
  { id: 'netherlands', label: '🇳🇱 Netherlands', value: 'Netherlands' },
  { id: 'portugal', label: '🇵🇹 Portugal', value: 'Portugal' },
  { id: 'algeria', label: '🇩🇿 Algeria', value: 'Algeria' },
  { id: 'tunisia', label: '🇹🇳 Tunisia', value: 'Tunisia' },
  { id: 'senegal', label: '🇸🇳 Senegal', value: 'Senegal' },
  { id: 'ivory_coast', label: '🇨🇮 Ivory Coast', value: 'Ivory Coast' },
  { id: 'uae', label: '🇦🇪 UAE', value: 'United Arab Emirates' },
  { id: 'saudi_arabia', label: '🇸🇦 Saudi Arabia', value: 'Saudi Arabia' },
  { id: 'qatar', label: '🇶🇦 Qatar', value: 'Qatar' },
  { id: 'brazil', label: '🇧🇷 Brazil', value: 'Brazil' },
];

function TagInput({ label, tags, onChange, placeholder }) {
  const [input, setInput] = useState('');
  const addTag = () => { const t = input.trim(); if (t && !tags.includes(t)) onChange([...tags, t]); setInput(''); };
  const removeTag = (i) => onChange(tags.filter((_, j) => j !== i));
  const kd = (e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } if (e.key === 'Backspace' && !input && tags.length > 0) removeTag(tags.length - 1); };
  return (
    <div>
      {label && <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">{label}</label>}
      <div className="flex flex-wrap gap-1.5 p-2 bg-slate-50 border border-slate-200 rounded-xl focus-within:ring-2 focus-within:ring-[#0A66C2] min-h-[42px]">
        {tags.map((tag, i) => (
          <span key={i} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs font-medium px-2.5 py-0.5 rounded-full border border-blue-200">
            {tag}<button onClick={() => removeTag(i)} className="hover:text-red-500"><X size={10} /></button>
          </span>
        ))}
        <input type="text" value={input} onChange={e => setInput(e.target.value)} onKeyDown={kd}
          placeholder={tags.length === 0 ? placeholder || 'Add...' : ''}
          className="flex-1 min-w-[120px] bg-transparent text-sm outline-none border-none px-1 py-1" />
      </div>
    </div>
  );
}

function LocationSelector({ selectedLocations, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setIsOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleLocation = (location) => {
    const isSelected = selectedLocations.find(l => l.value === location.value);
    if (isSelected) onChange(selectedLocations.filter(l => l.value !== location.value));
    else onChange([...selectedLocations, location]);
  };

  const removeLocation = (e, locationValue) => {
    e.stopPropagation();
    onChange(selectedLocations.filter(l => l.value !== locationValue));
  };

  const filteredLocations = PREDEFINED_LOCATIONS.filter(loc =>
    loc.label.toLowerCase().includes(search.toLowerCase()) ||
    loc.value.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div ref={dropdownRef} className="relative">
      <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">Target Locations</label>
      <div onClick={() => setIsOpen(!isOpen)}
        className="flex flex-wrap gap-1.5 p-2 bg-slate-50 border border-slate-200 rounded-xl cursor-pointer min-h-[42px] hover:border-slate-300 transition-colors">
        {selectedLocations.length === 0 ? (
          <span className="text-sm text-slate-400 px-1 py-1">Select locations...</span>
        ) : (
          selectedLocations.map((loc) => (
            <span key={loc.id} className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 text-xs font-medium px-2.5 py-0.5 rounded-full border border-emerald-200">
              {loc.label}
              <button onClick={(e) => removeLocation(e, loc.value)} className="hover:text-red-500"><X size={10} /></button>
            </span>
          ))
        )}
        <div className="flex-1" />
        <ChevronDown size={14} className={`text-slate-400 self-center transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </div>
      {isOpen && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-xl shadow-xl max-h-64 overflow-hidden">
          <div className="p-2 border-b border-slate-100">
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search locations..." autoFocus
              onClick={(e) => e.stopPropagation()}
              className="w-full px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#0A66C2]" />
          </div>
          <div className="overflow-y-auto max-h-48">
            {filteredLocations.map((location) => {
              const isSelected = selectedLocations.find(l => l.value === location.value);
              return (
                <button key={location.id} onClick={() => toggleLocation(location)}
                  className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between hover:bg-slate-50 transition-colors ${isSelected ? 'bg-emerald-50 text-emerald-700 font-semibold' : 'text-slate-700'}`}>
                  {location.label}
                  {isSelected && <span className="text-emerald-500">✓</span>}
                </button>
              );
            })}
          </div>
          <div className="p-2 border-t border-slate-100 flex gap-2">
            <button onClick={() => onChange([...PREDEFINED_LOCATIONS])} className="text-xs text-[#0A66C2] hover:underline font-semibold">Select All</button>
            <button onClick={() => onChange([])} className="text-xs text-slate-400 hover:text-slate-600 font-semibold">Clear</button>
          </div>
        </div>
      )}
    </div>
  );
}

function ConfirmModal({ open, title, msg, onConfirm, onCancel, loading, variant = 'blue' }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        <div className={`${variant === 'red' ? 'bg-red-600' : 'bg-gradient-to-r from-[#0A66C2] to-[#004182]'} p-5 text-white`}>
          <h3 className="text-lg font-bold">{title}</h3>
        </div>
        <div className="p-6"><p className="text-slate-600 text-sm leading-relaxed whitespace-pre-wrap">{msg}</p></div>
        <div className="px-6 pb-6 flex gap-3">
          <button onClick={onCancel} className="flex-1 py-2.5 text-sm font-semibold text-slate-600 bg-slate-100 rounded-xl hover:bg-slate-200">Cancel</button>
          <button onClick={onConfirm} disabled={loading}
            className={`flex-1 py-2.5 text-sm font-bold text-white rounded-xl disabled:opacity-50 flex items-center justify-center gap-2 ${variant === 'red' ? 'bg-red-600 hover:bg-red-700' : 'bg-gradient-to-r from-[#0A66C2] to-[#004182]'}`}>
            {loading ? <Loader size={14} className="animate-spin" /> : null} Confirm
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Outreach() {
  const toast = useToast();
  const [status, setStatus] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [searching, setSearching] = useState(false);
  const [sending, setSending] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [config, setConfig] = useState({
    keywords: ['water treatment', 'traitement des eaux', 'industrial water'],
    locations: [PREDEFINED_LOCATIONS[0], PREDEFINED_LOCATIONS[1]],
    language: 'french', max_results: 1, max_invites: 5,
  });
  const [showConfig, setShowConfig] = useState(false);
  const [confirmModal, setConfirmModal] = useState({ open: false, title: '', msg: '', action: null, variant: 'blue' });

  useEffect(() => { fetchStatus(); }, []);

  const headers = () => ({
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'Content-Type': 'application/json',
  });

  const fetchStatus = async () => {
    try {
      const r = await fetch(`${API_URL}/outreach/status`, { headers: headers() });
      if (r.ok) { const data = await r.json(); setStatus(data); setProfiles(data.recent_profiles || []); }
    } catch (e) { console.error('Status fetch error:', e); }
  };

  const handleSearch = async () => {
    if (config.keywords.length === 0) { toast.warning('Add at least one keyword'); return; }
    if (config.locations.length === 0) { toast.warning('Select at least one location'); return; }
    setSearching(true);
    try {
      const locationValues = config.locations.map(loc => loc.value);
      const r = await fetch(`${API_URL}/outreach/search`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ keywords: config.keywords, locations: locationValues, max_per_search: config.max_results, language: config.language }),
      });
      const data = await r.json();
      if (data.success) { toast.success('Search started!'); fetchStatus(); }
      else { toast.error(data.error || 'Search failed'); }
    } catch (e) { toast.error('Network error'); }
    finally { setSearching(false); }
  };

  const handleSendInvitations = () => {
    if (!status || status.profiles_found === 0) { toast.warning('No profiles to invite.'); return; }
    if (status.daily_remaining <= 0) { toast.warning('Daily limit reached.'); return; }
    setConfirmModal({
      open: true, title: 'Send LinkedIn Invitations?', variant: 'blue',
      msg: `Send up to ${Math.min(config.max_invites, status.daily_remaining)} invitations.\n\nMake sure you are logged into LinkedIn with:\n${status?.linkedin_email || 'your account'}\n\nDaily: ${status.daily_remaining}/${status.daily_limit}`,
      action: async () => { setConfirmModal(p => ({ ...p, open: false })); await executeSending(); },
    });
  };

  const executeSending = async () => {
    setSending(true);
    try {
      const r = await fetch(`${API_URL}/outreach/send-invitations`, {
        method: 'POST', headers: headers(),
        body: JSON.stringify({ max_invitations: config.max_invites, language: config.language }),
      });
      const data = await r.json();
      if (data.success) { toast.success(`${data.sent} sent!`); fetchStatus(); }
      else { toast.error(data.error || 'Failed'); }
    } catch (e) { toast.error('Error'); }
    finally { setSending(false); }
  };

  const handleClearInvited = () => {
    const totalCount = status?.total_profiles || 0;
    if (totalCount === 0) { toast.info('No profiles to clear.'); return; }
    setConfirmModal({
      open: true, title: 'Clear ALL Profiles?', variant: 'red',
      msg: `Delete ALL ${totalCount} profiles?\n\nThis cannot be undone.`,
      action: async () => { setConfirmModal(p => ({ ...p, open: false })); await executeClearInvited(); },
    });
  };

  const executeClearInvited = async () => {
    setClearing(true);
    try {
      const r = await fetch(`${API_URL}/outreach/profiles/invited`, { method: 'DELETE', headers: headers() });
      const data = await r.json();
      if (data.success) { toast.success(`${data.deleted} deleted!`); fetchStatus(); }
      else { toast.error(data.error || 'Failed'); }
    } catch (e) { toast.error('Error'); }
    finally { setClearing(false); }
  };

  const getStatusBadge = (s) => {
    switch (s) {
      case 'pending': return 'bg-blue-50 text-blue-600 border-blue-200';
      case 'invited': return 'bg-emerald-50 text-emerald-600 border-emerald-200';
      case 'failed': return 'bg-red-50 text-red-500 border-red-200';
      default: return 'bg-slate-50 text-slate-500 border-slate-200';
    }
  };

  const getStatusIcon = (s) => {
    switch (s) {
      case 'pending': return <Search size={14} className="text-blue-400" />;
      case 'invited': return <UserCheck size={14} className="text-emerald-500" />;
      case 'failed': return <UserX size={14} className="text-red-400" />;
      default: return <UserPlus size={14} className="text-slate-400" />;
    }
  };

  const getStatusLabel = (s) => {
    switch (s) {
      case 'pending': return 'Found';
      case 'invited': return 'Invited ✓';
      case 'failed': return 'Failed ✗';
      default: return s || 'Unknown';
    }
  };

  return (
    <div className="space-y-6">
      {/* ═══ HERO HEADER - Style Dashboard ═══ */}
      <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl p-6 shadow-lg">
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-blue-400/10 rounded-full translate-y-1/2 -translate-x-1/2 blur-2xl"></div>
        
        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            
            <h1 className="text-2xl md:text-3xl font-bold text-white leading-tight">
              LinkedIn Outreach
            </h1>
            <p className="text-blue-100/80 text-sm mt-1 max-w-xl">
              Find and connect with water treatment professionals
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Stats Pills */}
            <div className="hidden sm:flex items-center gap-2">
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {status?.total_profiles || 0} Total
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {status?.profiles_found || 0} Pending
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {status?.invitations_sent || 0} Invited
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {status?.daily_remaining || 0}/{status?.daily_limit || 30} Today
              </span>
            </div>
            
            {/* Action Buttons */}
            <button onClick={() => setShowConfig(!showConfig)}
              className="bg-white/10 backdrop-blur-sm text-white px-4 py-2.5 rounded-xl font-semibold text-sm hover:bg-white/20 transition-all border border-white/20 flex items-center gap-2">
              <Settings size={14} /> {showConfig ? 'Hide Config' : 'Settings'}
            </button>
            <button onClick={fetchStatus}
              className="bg-white text-[#0A66C2] px-4 py-2.5 rounded-xl font-bold text-sm hover:bg-blue-50 transition-all shadow-lg flex items-center gap-2">
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
        </div>
      </div>

      {/* ═══ CONFIG PANEL ═══ */}
      {showConfig && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
          <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
            <Settings size={16} className="text-[#0A66C2]" /> Search Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <TagInput label="Keywords" tags={config.keywords} onChange={(k) => setConfig({ ...config, keywords: k })} />
            <LocationSelector selectedLocations={config.locations} onChange={(locations) => setConfig({ ...config, locations })} />
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">Language</label>
              <select value={config.language} onChange={(e) => setConfig({ ...config, language: e.target.value })}
                className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-[#0A66C2] outline-none">
                <option value="french">French</option>
                <option value="english">English</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase mb-1.5">Max Results</label>
              <input type="number" value={config.max_results} onChange={(e) => setConfig({ ...config, max_results: parseInt(e.target.value) || 10 })}
                min="1" max="50" className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-[#0A66C2] outline-none" />
            </div>
          </div>
        </div>
      )}

      {/* ═══ ACTION BUTTONS ═══ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button onClick={handleSearch} disabled={searching}
          className="group bg-gradient-to-br from-[#0A66C2] to-[#004182] rounded-xl p-6 text-left transition-all hover:shadow-lg hover:-translate-y-0.5 disabled:opacity-50">
          <div className="flex items-center gap-3">
            <div className="bg-white/20 p-3 rounded-xl">
              {searching ? <Loader size={22} className="text-white animate-spin" /> : <Search size={22} className="text-white" />}
            </div>
            <div>
              <h3 className="font-bold text-white text-sm">1. Search Profiles</h3>
              <p className="text-blue-200 text-xs mt-0.5">Find professionals on LinkedIn</p>
            </div>
          </div>
        </button>

        <button onClick={handleSendInvitations} disabled={sending || !status || status.profiles_found === 0}
          className="group bg-white border-2 border-emerald-200 rounded-xl p-6 text-left transition-all hover:shadow-lg hover:-translate-y-0.5 hover:border-emerald-400 disabled:opacity-50">
          <div className="flex items-center gap-3">
            <div className="bg-emerald-50 p-3 rounded-xl">
              {sending ? <Loader size={22} className="text-emerald-600 animate-spin" /> : <Send size={22} className="text-emerald-600" />}
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">2. Send Invitations</h3>
              <p className="text-slate-500 text-xs mt-0.5">Auto-send connection requests</p>
            </div>
          </div>
        </button>

        <button onClick={handleClearInvited} disabled={clearing || (status?.total_profiles || 0) === 0}
          className="group bg-white border-2 border-red-200 rounded-xl p-6 text-left transition-all hover:shadow-lg hover:-translate-y-0.5 hover:border-red-400 disabled:opacity-50">
          <div className="flex items-center gap-3">
            <div className="bg-red-50 p-3 rounded-xl">
              {clearing ? <Loader size={22} className="text-red-500 animate-spin" /> : <Trash2 size={22} className="text-red-500" />}
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Clear All</h3>
              <p className="text-slate-500 text-xs mt-0.5">Delete all profiles</p>
            </div>
          </div>
        </button>
      </div>

      {/* ═══ PROFILES TABLE ═══ */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center">
          <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
            <Users size={16} className="text-[#0A66C2]" /> Discovered Profiles
          </h3>
          <span className="text-xs text-slate-400">{profiles.length} profiles</span>
        </div>
        {profiles.length === 0 ? (
          <div className="p-16 flex flex-col items-center justify-center text-center">
            <div className="bg-slate-50 p-4 rounded-full mb-4">
              <Users size={40} className="text-slate-300" />
            </div>
            <p className="text-slate-500 font-medium mb-1">No profiles yet</p>
            <p className="text-xs text-slate-400">Launch a search to find professionals</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Profile</th>
                  <th className="text-left px-4 py-3">Location</th>
                  <th className="text-center px-4 py-3">Status</th>
                  <th className="text-center px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile, i) => (
                  <tr key={i} className="border-t border-slate-100 hover:bg-slate-50/50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-bold text-xs">
                          {(profile.first_name || profile.name || '?')[0]}
                        </div>
                        <p className="text-sm font-semibold text-slate-800">{profile.name}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-slate-600"><MapPin size={10} className="inline mr-1 text-slate-400" />{profile.location || '—'}</p>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${getStatusBadge(profile.status)}`}>
                        {getStatusIcon(profile.status)}{getStatusLabel(profile.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {profile.profile_url && (
                        <a href={profile.profile_url} target="_blank" rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[#0A66C2] hover:text-[#004182] text-xs font-semibold">
                          <ExternalLink size={12} /> View
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {status?.last_run && (
        <div className="text-center text-xs text-slate-400 pb-4">
          Last outreach: {new Date(status.last_run).toLocaleString()}
        </div>
      )}

      <ConfirmModal open={confirmModal.open} title={confirmModal.title} msg={confirmModal.msg}
        onConfirm={confirmModal.action} onCancel={() => setConfirmModal(p => ({ ...p, open: false }))}
        loading={sending || clearing} variant={confirmModal.variant} />
    </div>
  );
}