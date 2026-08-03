import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  MessageSquare, Send, Loader, Bot, User, Sparkles,
  Database, FileText, AlertCircle, ChevronDown, X,
  Zap, Clock
} from 'lucide-react';
import { API_URL, authHeaders } from './tenderUtils';
import { BRAND } from '../App';

/* ------------------------------------------------------------------ */
/* Message Bubble                                                      */
/* ------------------------------------------------------------------ */
function ChatMessage({ msg }) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center py-2">
        <div className="bg-gray-100 text-gray-500 text-[11px] px-3 py-1.5 rounded-full flex items-center gap-1.5">
          {msg.icon && <msg.icon size={11} />}
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 ${
        isUser ? 'bg-violet-600' : 'bg-gradient-to-br from-violet-500 to-purple-600'
      }`}>
        {isUser ? (
          <User size={14} className="text-white" />
        ) : (
          <Bot size={14} className="text-white" />
        )}
      </div>

      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block max-w-[85%] px-4 py-2.5 rounded-2xl text-sm ${
          isUser
            ? 'bg-violet-600 text-white rounded-tr-md'
            : msg.isError
              ? 'bg-red-50 text-red-700 rounded-tl-md border border-red-100'
              : 'bg-gray-100 text-gray-800 rounded-tl-md'
        }`}>
          <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
        </div>

        {msg.sources && msg.sources.length > 0 && !isUser && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {msg.sources.map((src, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-violet-50 text-violet-700 rounded-lg text-[10px] font-medium border border-violet-100">
                <FileText size={10} />
                {src.file?.split('/').pop() || 'Doc'}
                {src.page && src.page !== 'N/A' && ` · p.${src.page}`}
              </span>
            ))}
          </div>
        )}

        {msg.timestamp && (
          <p className="text-[10px] text-gray-400 mt-1">{msg.timestamp}</p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Suggested Questions                                                 */
/* ------------------------------------------------------------------ */
const SUGGESTED_QUESTIONS = [
  "Quel est l'objet du marché ?",
  "Quel est le budget estimé ?",
  "Quelle est la date limite de remise des offres ?",
  "Qui est le maître d'ouvrage ?",
  "Quelles sont les conditions de participation ?",
  "Y a-t-il des lots ? Lesquels ?",
  "Quels sont les critères d'attribution ?",
  "Quelle est la caution provisoire ?",
];

function SuggestedQuestions({ onSelect, disabled }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? SUGGESTED_QUESTIONS : SUGGESTED_QUESTIONS.slice(0, 4);

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2">Questions suggérées</p>
      <div className="flex flex-wrap gap-1.5">
        {visible.map((q, i) => (
          <button
            key={i}
            onClick={() => onSelect(q)}
            disabled={disabled}
            className="px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg text-[11px] text-gray-600 hover:bg-violet-50 hover:border-violet-200 hover:text-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-left"
          >
            {q}
          </button>
        ))}
      </div>
      {SUGGESTED_QUESTIONS.length > 4 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="flex items-center gap-1 text-[11px] text-violet-600 hover:text-violet-700 font-medium mt-1"
        >
          {showAll ? 'Voir moins' : `Voir ${SUGGESTED_QUESTIONS.length - 4} autres`}
          <ChevronDown size={11} className={`transition-transform ${showAll ? 'rotate-180' : ''}`} />
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main Chatbot Panel                                                  */
/* ------------------------------------------------------------------ */
export default function ZipChatBot({ tenderId, tenderTitle, onClose }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexed, setIndexed] = useState(false);
  const [indexStats, setIndexStats] = useState(null);
  const [, setError] = useState(null);
  const [checkingIndex, setCheckingIndex] = useState(true);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input
  useEffect(() => {
    if (indexed) {
      inputRef.current?.focus();
    }
  }, [indexed]);

  const handleIndexDocuments = useCallback(async () => {
    setIndexing(true);
    setError(null);
    
    try {
      const r = await fetch(
        `${API_URL}/tenders/${encodeURIComponent(tenderId)}/chat/index`,
        {
          method: 'POST',
          headers: authHeaders(),
        }
      );

      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || `Erreur ${r.status}`);
      }

      const data = await r.json();
      setIndexed(true);
      setIndexStats(data);
      
      setMessages(prev => [
        ...prev,
        {
          role: 'system',
          content: `✅ ${data.chunks_created || data.chunk_count || 0} segments indexés en ${data.time_seconds || 'quelques'} secondes`,
          icon: Zap,
          timestamp: new Date().toLocaleTimeString()
        }
      ]);
    } catch (e) {
      setError(e.message);
      setMessages(prev => [
        ...prev,
        {
          role: 'system',
          content: `❌ Erreur d'indexation : ${e.message}`,
          icon: AlertCircle,
          timestamp: new Date().toLocaleTimeString()
        }
      ]);
    } finally {
      setIndexing(false);
    }
  }, [tenderId]);


  // ═══════════════════════════════════════════════════════════
  //  INDEXATION AUTOMATIQUE — checkIndexStatus modifié
  // ═══════════════════════════════════════════════════════════
  const checkIndexStatus = useCallback(async () => {
    setCheckingIndex(true);
    try {
      const r = await fetch(
        `${API_URL}/tenders/${encodeURIComponent(tenderId)}/chat/status`,
        { headers: authHeaders() }
      );
      if (r.ok) {
        const data = await r.json();
        if (data.indexed) {
          setIndexed(true);
          setIndexStats(data);
          setMessages([
            {
              role: 'system',
              content: `✅ Documents indexés : ${data.chunk_count} segments dans ${data.file_count} fichiers`,
              icon: Database,
              timestamp: new Date().toLocaleTimeString()
            }
          ]);
        } else {
          setMessages([
            {
              role: 'system',
              content: '🔍 Indexation automatique des documents en cours...',
              icon: Loader,
              timestamp: new Date().toLocaleTimeString()
            }
          ]);
          await handleIndexDocuments();
        }
      } else {
        setMessages([
          {
            role: 'system',
            content: '🔍 Préparation de l\'assistant...',
            icon: Loader,
            timestamp: new Date().toLocaleTimeString()
          }
        ]);
        await handleIndexDocuments();
      }
    } catch (e) {
      console.error('Chat status check failed:', e);
      try {
        setMessages([
          {
            role: 'system',
            content: '🔍 Indexation des documents en cours...',
            icon: Loader,
            timestamp: new Date().toLocaleTimeString()
          }
        ]);
        await handleIndexDocuments();
      } catch (e2) {
        console.error('Auto-indexing failed:', e2);
      }
    } finally {
      setCheckingIndex(false);
    }
  }, [tenderId, handleIndexDocuments]);
  

  // ═══════════════════════════════════════════════════════════
  //  Lancer la vérification auto au montage du composant
  // ═══════════════════════════════════════════════════════════
  useEffect(() => {
    checkIndexStatus();
  }, [checkIndexStatus]);

  const handleSend = async (text = input) => {
    if (!text.trim() || loading || !indexed) return;
    
    const question = text.trim();
    setInput('');
    setError(null);

    // Add user message
    const userMsg = {
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString()
    };
    setMessages(prev => [...prev, userMsg]);

    // Add typing indicator
    setLoading(true);
    const typingMsg = {
      role: 'bot',
      content: '...',
      isTyping: true,
      timestamp: new Date().toLocaleTimeString()
    };
    setMessages(prev => [...prev, typingMsg]);

    try {
      // Build chat history for context
      const chatHistory = messages
        .filter(m => m.role === 'user' || (m.role === 'bot' && !m.isTyping))
        .slice(-10)
        .map(m => ({ role: m.role === 'bot' ? 'assistant' : 'user', content: m.content }));

      const r = await fetch(
        `${API_URL}/tenders/${encodeURIComponent(tenderId)}/chat/query`,
        {
          method: 'POST',
          headers: {
            ...authHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            question,
            chat_history: chatHistory,
            top_k: 5
          }),
        }
      );

      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || `Erreur ${r.status}`);
      }

      const data = await r.json();

      // Remove typing indicator
      setMessages(prev => prev.filter(m => !m.isTyping));

      // Add bot response
      const botMsg = {
        role: 'bot',
        content: data.answer,
        sources: data.sources,
        needs_indexing: data.needs_indexing,
        isError: data.error || false,
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, botMsg]);

      if (data.needs_indexing) {
        setIndexed(false);
        // Relancer l'indexation automatique
        await handleIndexDocuments();
      }
    } catch (e) {
      // Remove typing indicator
      setMessages(prev => prev.filter(m => !m.isTyping));

      setMessages(prev => [
        ...prev,
        {
          role: 'bot',
          content: `Désolé, une erreur est survenue : ${e.message}`,
          isError: true,
          timestamp: new Date().toLocaleTimeString()
        }
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-[420px] bg-white shadow-2xl z-[70] flex flex-col border-l border-gray-200">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-gray-100">
        <div className="h-1 bg-gradient-to-r from-violet-500 to-purple-600" />
        <div className="px-4 py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0">
              <Sparkles size={16} className="text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-bold text-gray-900 truncate">
                Assistant IA
              </h3>
              <p className="text-[11px] text-gray-400 truncate max-w-[280px]">
                {tenderTitle || 'Documents DCE'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Status bar — indexation automatique */}
        <div className="px-4 pb-2 flex items-center gap-2">
          {(checkingIndex || indexing) ? (
            <div className="flex items-center gap-1.5 text-[11px] text-violet-600 bg-violet-50 px-2.5 py-1 rounded-full">
              <Loader size={12} className="animate-spin" />
              <span>{indexing ? 'Indexation en cours...' : 'Préparation...'}</span>
            </div>
          ) : indexed ? (
            <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
              <Database size={12} />
              <span>{indexStats?.chunk_count || 0} segments indexés</span>
            </div>
          ) : null}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && checkingIndex && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <Loader size={28} className="animate-spin text-gray-300" />
            <p className="text-sm text-gray-400">Préparation de l'assistant...</p>
          </div>
        )}

        {messages.length === 0 && !checkingIndex && !indexing && !indexed && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-red-50 flex items-center justify-center">
              <AlertCircle size={28} className="text-red-400" />
            </div>
            <div>
              <p className="text-sm font-bold text-gray-700 mb-1">
                Indexation impossible
              </p>
              <p className="text-xs text-gray-400 leading-relaxed">
                Les documents n'ont pas pu être indexés. Vérifiez que le DCE est bien téléchargé.
              </p>
            </div>
          </div>
        )}

        {messages.length === 0 && !checkingIndex && !indexing && indexed && (
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center px-4">
            <div className="w-16 h-16 rounded-2xl bg-violet-50 flex items-center justify-center">
              <MessageSquare size={28} className="text-violet-400" />
            </div>
            <div>
              <p className="text-sm font-bold text-gray-700 mb-1">
                Assistant DCE intelligent
              </p>
              <p className="text-xs text-gray-400 leading-relaxed">
                Posez vos questions sur les documents du DCE. L'assistant analysera le contenu pour vous répondre.
              </p>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested questions */}
      {messages.length <= 1 && indexed && (
        <div className="px-4 pb-2 border-t border-gray-100 pt-3">
          <SuggestedQuestions
            onSelect={(q) => handleSend(q)}
            disabled={loading || indexing || !indexed}
          />
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 border-t border-gray-100 p-3 bg-gray-50/50">
        <div className="flex items-end gap-2 bg-white rounded-xl border border-gray-200 p-2 focus-within:border-violet-300 focus-within:ring-2 focus-within:ring-violet-100 transition-all">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={indexed ? "Posez une question sur le DCE..." : "Préparation de l'assistant..."}
            disabled={!indexed || loading}
            rows={1}
            className="flex-1 resize-none border-0 outline-none text-sm px-2 py-1 max-h-32 bg-transparent disabled:opacity-50"
            style={{ minHeight: '24px' }}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading || !indexed}
            className="p-2 rounded-lg text-white disabled:opacity-30 transition-all flex-shrink-0"
            style={{ background: input.trim() && !loading && indexed ? BRAND.gradient : '#E5E7EB' }}
          >
            {loading ? (
              <Loader size={16} className="animate-spin" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </div>

        <div className="flex items-center justify-between mt-2 px-1">
          <p className="text-[10px] text-gray-400">
            Propulsé par Groq AI + RAG
          </p>
          <div className="flex items-center gap-1 text-[10px] text-gray-400">
            <Clock size={10} />
            <span>Réponses basées sur le DCE</span>
          </div>
        </div>
      </div>
    </div>
  );
}