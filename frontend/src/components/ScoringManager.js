import React, { useState, useEffect, useCallback } from 'react';
import {
  X, Plus, Trash2, Settings, Sliders, RefreshCw, Check,
} from 'lucide-react';
import { API_URL, authHeaders } from './tenderUtils';

const CATEGORIES = {
  strong_keyword: { label: 'Mot-clé fort', color: '#D6572E', bg: '#FBEAE6' },
  medium_keyword: { label: 'Mot-clé moyen', color: '#C7913F', bg: '#FBF3E6' },
  specific_keyword: { label: 'Mot-clé spécifique', color: '#0E93A1', bg: '#E6F5F6' },
  strategic_client: { label: 'Client stratégique', color: '#4A6B72', bg: '#EEF4F3' },
  exclusion: { label: 'Exclusion', color: '#9BB5B1', bg: '#F1F6F5' },
};

export default function ScoringManager({ isOpen, onClose }) {
  const [criteria, setCriteria] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newCriteria, setNewCriteria] = useState({ name: '', category: 'strong_keyword', value: '', weight: 1 });
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({});

  const fetchCriteria = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/scoring-criteria`, { headers: authHeaders() });
      const data = await response.json();
      if (data.success) setCriteria(data.criteria || []);
    } catch (error) { console.error('Error fetching scoring criteria:', error); }
    setLoading(false);
  }, []);

  useEffect(() => { if (isOpen) fetchCriteria(); }, [isOpen, fetchCriteria]);

  const addCriteria = async () => {
    if (!newCriteria.name || !newCriteria.value) return;
    try {
      await fetch(`${API_URL}/scoring-criteria`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(newCriteria)
      });
      setNewCriteria({ name: '', category: 'strong_keyword', value: '', weight: 1 });
      fetchCriteria();
    } catch (error) { console.error(error); }
  };

  const deleteCriteria = async (id) => {
    try {
      await fetch(`${API_URL}/scoring-criteria/${id}`, { method: 'DELETE', headers: authHeaders() });
      fetchCriteria();
    } catch (error) { console.error(error); }
  };

  const toggleActive = async (id, isActive) => {
    try {
      await fetch(`${API_URL}/scoring-criteria/${id}`, {
        method: 'PATCH',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !isActive })
      });
      fetchCriteria();
    } catch (error) { console.error(error); }
  };

  const startEdit = (item) => {
    setEditingId(item.id);
    setEditValues({ ...item });
  };

  const saveEdit = async () => {
    try {
      await fetch(`${API_URL}/scoring-criteria/${editingId}`, {
        method: 'PATCH',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(editValues)
      });
      setEditingId(null);
      fetchCriteria();
    } catch (error) { console.error(error); }
  };

  const groupedCriteria = criteria.reduce((acc, c) => {
    const cat = c.category || 'strong_keyword';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(c);
    return acc;
  }, {});

  if (!isOpen) return null;

  return (
    <div className="cw-theme min-h-screen bg-white">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        .cw-theme { font-family: 'Space Grotesk', ui-sans-serif, sans-serif; }
        .cw-serif { font-family: 'Newsreader', serif; }
        .cw-mono { font-family: 'IBM Plex Mono', monospace; }
      `}</style>
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="bg-white rounded-2xl border border-[#DCE8E5] shadow-lg shadow-[#123338]/5 overflow-hidden mb-4">
          <div className="p-5 border-b border-[#DCE8E5] bg-gradient-to-b from-[#F7FAF9] to-[#F1F6F5]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#0E93A1] to-[#0C7C88] flex items-center justify-center shadow-lg shadow-[#0E93A1]/20">
                  <Sliders size={18} className="text-white" />
                </div>
                <div>
                  <h3 className="font-bold text-[#123338] cw-serif text-base">Critères de Scoring</h3>
                  <p className="text-xs text-[#7FA09B]">{criteria.length} critères · Personnalisez le calcul du score de pertinence</p>
                </div>
              </div>
            </div>
          </div>

          {/* Add new criteria */}
          <div className="p-4 border-b border-[#DCE8E5] bg-white">
            <div className="flex gap-2 flex-wrap">
              <input type="text" value={newCriteria.name} onChange={e => setNewCriteria({ ...newCriteria, name: e.target.value })}
                placeholder="Nom du critère..." className="flex-1 min-w-[120px] px-3 py-2 text-xs border border-[#DCE8E5] rounded-lg focus:ring-2 focus:ring-[#0E93A1]/20 outline-none text-[#123338]" />
              <select value={newCriteria.category} onChange={e => setNewCriteria({ ...newCriteria, category: e.target.value })}
                className="px-3 py-2 text-xs border border-[#DCE8E5] rounded-lg focus:ring-2 focus:ring-[#0E93A1]/20 outline-none text-[#123338]">
                {Object.entries(CATEGORIES).map(([key, val]) => (
                  <option key={key} value={key}>{val.label}</option>
                ))}
              </select>
              <input type="text" value={newCriteria.value} onChange={e => setNewCriteria({ ...newCriteria, value: e.target.value })}
                placeholder="Mot-clé..." className="w-32 px-3 py-2 text-xs border border-[#DCE8E5] rounded-lg focus:ring-2 focus:ring-[#0E93A1]/20 outline-none text-[#123338]" />
              <input type="number" value={newCriteria.weight} onChange={e => setNewCriteria({ ...newCriteria, weight: parseInt(e.target.value) || 1 })}
                min="1" max="100" className="w-16 px-2 py-2 text-xs border border-[#DCE8E5] rounded-lg focus:ring-2 focus:ring-[#0E93A1]/20 outline-none text-[#123338]" />
              <button onClick={addCriteria}
                className="px-4 py-2 bg-[#0E93A1] text-white rounded-lg text-xs font-bold hover:bg-[#0C7C88] transition-all flex items-center gap-1 shadow-sm">
                <Plus size={12} />Ajouter
              </button>
            </div>
          </div>
        </div>

        {/* Criteria list */}
        <div className="bg-white rounded-2xl border border-[#DCE8E5] shadow-lg shadow-[#123338]/5 overflow-hidden">
          {loading ? (
            <div className="p-10 text-center"><RefreshCw size={24} className="text-[#0E93A1] animate-spin mx-auto mb-2" /><p className="text-xs text-[#9BB5B1]">Chargement des critères...</p></div>
          ) : Object.keys(groupedCriteria).length === 0 ? (
            <div className="p-10 text-center"><Sliders size={32} className="text-[#9BB5B1] mx-auto mb-2" /><p className="text-sm font-bold text-[#4F6E69]">Aucun critère</p><p className="text-xs text-[#9BB5B1]">Ajoutez des critères pour personnaliser le scoring</p></div>
          ) : (
            <div className="divide-y divide-[#DCE8E5]">
              {Object.entries(groupedCriteria).map(([category, items]) => {
                const catInfo = CATEGORIES[category] || CATEGORIES.strong_keyword;
                return (
                  <div key={category}>
                    <div className="px-4 py-2.5 bg-[#F7FAF9] flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: catInfo.color }} />
                      <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#4F6E69]">{catInfo.label}s ({items.length})</span>
                    </div>
                    {items.map(item => (
                      <div key={item.id} className={`px-4 py-2.5 flex items-center gap-3 hover:bg-[#F7FAF9]/50 transition-colors ${!item.is_active ? 'opacity-40' : ''}`}>
                        {editingId === item.id ? (
                          <div className="flex items-center gap-2 flex-1 flex-wrap">
                            <input type="text" value={editValues.name || ''} onChange={e => setEditValues({ ...editValues, name: e.target.value })}
                              className="flex-1 min-w-[100px] px-2 py-1 text-xs border border-[#DCE8E5] rounded focus:ring-2 focus:ring-[#0E93A1]/20 outline-none" />
                            <input type="text" value={editValues.value || ''} onChange={e => setEditValues({ ...editValues, value: e.target.value })}
                              className="w-24 px-2 py-1 text-xs border border-[#DCE8E5] rounded focus:ring-2 focus:ring-[#0E93A1]/20 outline-none" />
                            <input type="number" value={editValues.weight || 1} onChange={e => setEditValues({ ...editValues, weight: parseInt(e.target.value) || 1 })}
                              min="1" max="100" className="w-14 px-2 py-1 text-xs border border-[#DCE8E5] rounded focus:ring-2 focus:ring-[#0E93A1]/20 outline-none" />
                            <button onClick={saveEdit} className="p-1.5 text-emerald-500 hover:bg-emerald-50 rounded transition-all"><Check size={14} /></button>
                            <button onClick={() => setEditingId(null)} className="p-1.5 text-red-400 hover:bg-red-50 rounded transition-all"><X size={14} /></button>
                          </div>
                        ) : (
                          <>
                            <button onClick={() => toggleActive(item.id, item.is_active)}
                              className={`flex-shrink-0 w-4 h-4 rounded border-2 transition-all flex items-center justify-center ${item.is_active ? 'bg-[#0E93A1] border-[#0E93A1]' : 'border-[#C3D6D2]'}`}>
                              {item.is_active && <Check size={10} className="text-white" strokeWidth={3} />}
                            </button>
                            <div className="flex-1 min-w-0 flex items-center gap-2">
                              <span className="text-xs font-semibold text-[#123338] truncate">{item.name}</span>
                              <span className="cw-mono text-[10px] text-[#9BB5B1] bg-[#F1F6F5] px-1.5 py-0.5 rounded">{item.value}</span>
                              <span className="cw-mono text-[10px] font-bold text-[#0E93A1]">×{item.weight}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <button onClick={() => startEdit(item)} className="p-1 text-[#9BB5B1] hover:text-[#0E93A1] hover:bg-[#E6F5F6] rounded transition-all">
                                <Settings size={12} />
                              </button>
                              <button onClick={() => deleteCriteria(item.id)} className="p-1 text-[#9BB5B1] hover:text-red-500 hover:bg-red-50 rounded transition-all">
                                <Trash2 size={12} />
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}