import React, { useState, useEffect, useCallback } from 'react';
import {
  X, Plus, Trash2, Settings, Sliders, RefreshCw, Check,
} from 'lucide-react';
import { API_URL, authHeaders } from './tenderUtils';

const CW_THEME_STYLE = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  
  .cw-theme { 
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, ui-sans-serif, sans-serif; 
    background-color: #F8FAFC;
  }
  
  * {
    transition-property: background-color, border-color, color, fill, stroke, opacity, box-shadow, transform;
    transition-duration: 150ms;
    transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  }
`;

export default function ScoringManager({ isOpen, onClose }) {
  const [criteria, setCriteria] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newCriteria, setNewCriteria] = useState({ name: '', value: '', weight: 1 });
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [showAddModal, setShowAddModal] = useState(false);

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
      setNewCriteria({ name: '', value: '', weight: 1 });
      setShowAddModal(false);
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

  if (!isOpen) return null;

  return (
    <div className="cw-theme min-h-screen">
      <style>{CW_THEME_STYLE}</style>
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search bar + Add button */}
        <div className="bg-white rounded-3xl border border-[#E2E8F0] shadow-sm overflow-hidden mb-6">
          <div className="p-4">
            <div className="flex gap-3">
              <div className="relative flex-1">
                <input 
                  type="text" 
                  placeholder="Rechercher un critère..." 
                  className="w-full pl-4 pr-4 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] placeholder-[#94A3B8] bg-[#F8FAFC]" 
                />
              </div>
              <button 
                onClick={() => setShowAddModal(true)}
                className="px-6 py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all duration-200 flex items-center gap-2 shadow-sm active:scale-95"
              >
                <Plus size={14} />Ajouter un critère
              </button>
            </div>
          </div>
        </div>

        {/* Criteria list */}
        <div className="bg-white rounded-3xl border border-[#E2E8F0] shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-12 text-center">
              <RefreshCw size={28} className="text-[#2563EB] animate-spin mx-auto mb-3" />
              <p className="text-sm font-medium text-[#64748B]">Chargement des critères...</p>
            </div>
          ) : criteria.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-[#F8FAFC] flex items-center justify-center mx-auto mb-3">
                <Sliders size={24} className="text-[#94A3B8]" />
              </div>
              <p className="text-sm font-semibold text-[#475569]">Aucun critère</p>
              <p className="text-xs text-[#94A3B8] mt-1">Ajoutez des critères pour personnaliser le scoring</p>
            </div>
          ) : (
            <div className="divide-y divide-[#E2E8F0]">
              {criteria.map(item => (
                <div key={item.id} className={`px-5 py-3.5 flex items-center gap-3 hover:bg-[#F8FAFC]/50 transition-colors ${!item.is_active ? 'opacity-40' : ''}`}>
                  {editingId === item.id ? (
                    <div className="flex items-center gap-2 flex-1 flex-wrap">
                      <input 
                        type="text" 
                        value={editValues.name || ''} 
                        onChange={e => setEditValues({ ...editValues, name: e.target.value })}
                        className="flex-1 min-w-[120px] px-3 py-2 text-xs border border-[#E2E8F0] rounded-xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]" 
                      />
                      <input 
                        type="text" 
                        value={editValues.value || ''} 
                        onChange={e => setEditValues({ ...editValues, value: e.target.value })}
                        className="w-28 px-3 py-2 text-xs border border-[#E2E8F0] rounded-xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]" 
                      />
                      <input 
                        type="number" 
                        value={editValues.weight || 1} 
                        onChange={e => setEditValues({ ...editValues, weight: parseInt(e.target.value) || 1 })}
                        min="1" max="100" 
                        className="w-16 px-2 py-2 text-xs border border-[#E2E8F0] rounded-xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A]" 
                      />
                      <button onClick={saveEdit} className="p-2 text-[#16A34A] hover:bg-[#DCFCE7] rounded-xl transition-all">
                        <Check size={14} />
                      </button>
                      <button onClick={() => setEditingId(null)} className="p-2 text-[#DC2626] hover:bg-[#FEE2E2] rounded-xl transition-all">
                        <X size={14} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <button 
                        onClick={() => toggleActive(item.id, item.is_active)}
                        className={`flex-shrink-0 w-5 h-5 rounded-lg border-2 transition-all flex items-center justify-center ${
                          item.is_active ? 'bg-[#2563EB] border-[#2563EB]' : 'border-[#CBD5E1] hover:border-[#2563EB]/40'
                        }`}
                      >
                        {item.is_active && <Check size={11} className="text-white" strokeWidth={3} />}
                      </button>
                      <div className="flex-1 min-w-0 flex items-center gap-2.5">
                        <span className="text-sm font-medium text-[#0F172A] truncate">{item.name}</span>
                        <span className="text-[11px] font-medium text-[#64748B] bg-[#F8FAFC] px-2 py-0.5 rounded-lg border border-[#E2E8F0]">{item.value}</span>
                        <span className="text-[11px] font-semibold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded-lg border border-[#BFDBFE]">×{item.weight}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button 
                          onClick={() => startEdit(item)} 
                          className="p-2 text-[#94A3B8] hover:text-[#2563EB] hover:bg-[#EFF6FF] rounded-xl transition-all"
                        >
                          <Settings size={13} />
                        </button>
                        <button 
                          onClick={() => deleteCriteria(item.id)} 
                          className="p-2 text-[#94A3B8] hover:text-[#DC2626] hover:bg-[#FEE2E2] rounded-xl transition-all"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Add Criteria Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0F172A]/40 backdrop-blur-sm">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden border border-[#E2E8F0] transform transition-all duration-200 scale-100">
            <div className="p-6 border-b border-[#E2E8F0]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-[#111827] flex items-center justify-center shadow-sm">
                    <Plus size={18} className="text-white" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[#0F172A] text-base">Ajouter un critère</h3>
                    <p className="text-xs text-[#64748B]">Définissez un nouveau critère de scoring</p>
                  </div>
                </div>
                <button onClick={() => setShowAddModal(false)} className="p-2 text-[#94A3B8] hover:text-[#0F172A] hover:bg-[#F8FAFC] rounded-xl transition-colors">
                  <X size={18} />
                </button>
              </div>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#64748B] mb-1.5">Nom du critère</label>
                <input 
                  type="text" 
                  value={newCriteria.name} 
                  onChange={e => setNewCriteria({ ...newCriteria, name: e.target.value })}
                  placeholder="Ex: Certification ISO" 
                  className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] placeholder-[#94A3B8] bg-[#F8FAFC]" 
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#64748B] mb-1.5">Mot-clé / Valeur</label>
                  <input 
                    type="text" 
                    value={newCriteria.value} 
                    onChange={e => setNewCriteria({ ...newCriteria, value: e.target.value })}
                    placeholder="Ex: ISO 9001" 
                    className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] placeholder-[#94A3B8] bg-[#F8FAFC]" 
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#64748B] mb-1.5">Poids (×)</label>
                  <input 
                    type="number" 
                    value={newCriteria.weight} 
                    onChange={e => setNewCriteria({ ...newCriteria, weight: parseInt(e.target.value) || 1 })}
                    min="1" max="100" 
                    className="w-full px-4 py-3 text-sm border border-[#E2E8F0] rounded-2xl focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB] outline-none text-[#0F172A] bg-[#F8FAFC]" 
                  />
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-[#E2E8F0] bg-[#F8FAFC] flex gap-3">
              <button 
                onClick={() => setShowAddModal(false)}
                className="flex-1 py-3 bg-white border border-[#E2E8F0] text-[#475569] rounded-2xl text-sm font-medium hover:bg-[#F8FAFC] transition-all duration-200"
              >
                Annuler
              </button>
              <button 
                onClick={addCriteria}
                className="flex-1 py-3 bg-[#111827] text-white rounded-2xl text-sm font-medium hover:bg-[#1E293B] transition-all duration-200 shadow-sm active:scale-[0.98]"
              >
                Ajouter le critère
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}