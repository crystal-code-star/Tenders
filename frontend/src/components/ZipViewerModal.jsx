import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactDOM from 'react-dom';
import {
  X, Folder, FolderOpen, FileText, FileSpreadsheet, File,
  Image as ImageIcon, Loader, AlertCircle, Download,
  ChevronRight, ChevronDown, ZoomIn, ZoomOut, RefreshCw,
  FileArchive, PanelRightClose, PanelRightOpen, Sparkles,
  GripVertical,
} from 'lucide-react';
import { API_URL, authHeaders } from './tenderUtils';
import { BRAND } from '../App';
import DocumentIntelligencePanel from './DocumentIntelligencePanel';
import ZipChatBot from './ZipChatBot';

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */

function extOf(name) {
  const i = name.lastIndexOf('.');
  return i === -1 ? '' : name.slice(i + 1).toLowerCase();
}

function iconForFile(name) {
  const ext = extOf(name);
  if (ext === 'pdf') return <FileText size={15} className="text-red-500 flex-shrink-0" />;
  if (['doc', 'docx'].includes(ext)) return <FileText size={15} className="text-blue-500 flex-shrink-0" />;
  if (['xls', 'xlsx', 'xlsm', 'csv'].includes(ext)) return <FileSpreadsheet size={15} className="text-emerald-600 flex-shrink-0" />;
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return <ImageIcon size={15} className="text-violet-500 flex-shrink-0" />;
  return <File size={15} className="text-gray-400 flex-shrink-0" />;
}

function previewUrl(tenderId, path) {
  return `${API_URL}/tenders/${tenderId}/preview/${encodeURIComponent(path)}`;
}
function rawDownloadUrl(tenderId, path) {
  return `${API_URL}/tenders/${tenderId}/raw/${encodeURIComponent(path)}?download=true`;
}
function isXlsxExt(ext) {
  return ['xlsx', 'xlsm', 'xls'].includes(ext);
}

/* ------------------------------------------------------------------ */
/* Folder tree (left panel)                                            */
/* ------------------------------------------------------------------ */

function TreeNode({ node, depth, selectedPath, onSelectFile }) {
  const [open, setOpen] = useState(true);

  if (node.type === 'file') {
    const isSelected = selectedPath === node.path;
    return (
      <button
        onClick={() => onSelectFile(node.path)}
        style={{ paddingLeft: `${depth * 16 + 28}px` }}
        className={`w-full flex items-center gap-2 py-1.5 pr-3 text-sm rounded-lg transition-colors text-left ${
          isSelected ? 'bg-gray-100 text-gray-800 font-medium' : 'text-gray-600 hover:bg-gray-50'
        }`}
      >
        {iconForFile(node.name)}
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        className="w-full flex items-center gap-2 py-1.5 pr-3 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg text-left"
      >
        {open ? <ChevronDown size={13} className="flex-shrink-0" /> : <ChevronRight size={13} className="flex-shrink-0" />}
        {open ? <FolderOpen size={15} className="text-amber-500 flex-shrink-0" /> : <Folder size={15} className="text-amber-500 flex-shrink-0" />}
        <span className="truncate">{node.name === '/' ? 'Documents' : node.name}</span>
      </button>
      {open && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.path || child.name} node={child} depth={depth + 1} selectedPath={selectedPath} onSelectFile={onSelectFile} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Preview renderers (center panel)                                    */
/* ------------------------------------------------------------------ */

function CenteredState({ icon, text, action }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-8 gap-2">
      {icon}
      <p className="text-gray-500 text-sm">{text}</p>
      {action}
    </div>
  );
}

function PdfPreview({ tenderId, path }) {
  const [zoom, setZoom] = useState(100);
  const url = previewUrl(tenderId, path);
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end gap-2 px-3 py-2 border-b border-gray-100 bg-gray-50">
        <button onClick={() => setZoom((z) => Math.max(50, z - 10))} className="p-1.5 rounded-lg hover:bg-white text-gray-500" title="Zoom out">
          <ZoomOut size={14} />
        </button>
        <span className="text-xs font-medium text-gray-500 w-12 text-center">{zoom}%</span>
        <button onClick={() => setZoom((z) => Math.min(200, z + 10))} className="p-1.5 rounded-lg hover:bg-white text-gray-500" title="Zoom in">
          <ZoomIn size={14} />
        </button>
        <a href={rawDownloadUrl(tenderId, path)} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded-lg hover:bg-white text-gray-500" title="Download file">
          <Download size={14} />
        </a>
      </div>
      <div className="flex-1 overflow-auto bg-gray-200">
        <iframe title={path} src={`${url}#zoom=${zoom}`} className="w-full h-full border-0" style={{ minHeight: '60vh' }} />
      </div>
    </div>
  );
}

function DocxPreview({ tenderId, path }) {
  const [html, setHtml] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(null); setHtml(null);
    fetch(`${API_URL}/tenders/${tenderId}/text/${encodeURIComponent(path)}`, { headers: authHeaders() })
      .then((r) => { if (!r.ok) throw new Error(`Server returned ${r.status}`); return r.json(); })
      .then((data) => {
        if (!active) return;
        if (data.type === 'html' && data.content) setHtml(data.content);
        else if (data.type === 'text' && data.content) setHtml(`<pre style="font-family: monospace; white-space: pre-wrap; padding: 20px;">${data.content}</pre>`);
        else throw new Error('Unexpected response format from server');
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [tenderId, path]);

  if (loading) return <CenteredState icon={<Loader size={24} className="animate-spin text-gray-400" />} text="Loading document…" />;
  if (error) return (
    <CenteredState icon={<AlertCircle size={24} className="text-red-400" />} text={`Could not open: ${error}`} action={
      <a href={rawDownloadUrl(tenderId, path)} className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: BRAND.gradient }}>
        <Download size={14} /> Download DOCX
      </a>
    } />
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 bg-gray-50 flex-shrink-0">
        <div className="flex items-center gap-2 text-gray-600">
          <FileText size={14} />
          <span className="text-xs font-medium">Document preview</span>
        </div>
        <a href={rawDownloadUrl(tenderId, path)} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-600 hover:bg-white border border-gray-200 transition-colors">
          <Download size={13} /> Download
        </a>
      </div>
      <div className="flex-1 overflow-auto bg-white">
        <iframe title={path} srcDoc={html} className="w-full h-full border-0" style={{ minHeight: '60vh' }} sandbox="allow-same-origin" />
      </div>
    </div>
  );
}

function XlsxPreview({ tenderId, path, sheets, loading, error }) {
  const [activeSheet, setActiveSheet] = useState(0);

  useEffect(() => { setActiveSheet(0); }, [path]);

  if (loading) return <CenteredState icon={<Loader size={24} className="animate-spin text-gray-400" />} text="Rendering spreadsheet…" />;
  if (error) return (
    <CenteredState icon={<AlertCircle size={24} className="text-red-400" />} text={`Could not render: ${error}`} action={
      <a href={rawDownloadUrl(tenderId, path)} className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: BRAND.gradient }}>
        <Download size={14} /> Download instead
      </a>
    } />
  );
  if (!sheets || sheets.length === 0) return <CenteredState icon={<FileSpreadsheet size={24} className="text-gray-300" />} text="Empty workbook" />;

  const sheet = sheets[Math.min(activeSheet, sheets.length - 1)];
  const mergedSkip = new Set();
  const mergedSpan = {};
  (sheet.merged_cells || []).forEach((range) => {
    const [start, end] = range.split(':');
    const parse = (ref) => {
      const m = ref.match(/^([A-Z]+)(\d+)/);
      const col = m[1].split('').reduce((acc, c) => acc * 26 + (c.charCodeAt(0) - 64), 0);
      return { col, row: parseInt(m[2], 10) };
    };
    const s = parse(start);
    const e = end ? parse(end) : s;
    const colSpan = e.col - s.col + 1;
    const rowSpan = e.row - s.row + 1;
    mergedSpan[`${s.row}-${s.col}`] = { colSpan, rowSpan };
    for (let r = s.row; r <= e.row; r++) {
      for (let c = s.col; c <= e.col; c++) {
        if (r === s.row && c === s.col) continue;
        mergedSkip.add(`${r}-${c}`);
      }
    }
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto bg-white">
        <table className="border-collapse text-xs">
          <tbody>
            {sheet.rows.map((row, rIdx) => (
              <tr key={rIdx}>
                {row.map((cell, cIdx) => {
                  const key = `${rIdx + 1}-${cIdx + 1}`;
                  if (mergedSkip.has(key)) return null;
                  const span = mergedSpan[key];
                  return (
                    <td key={cIdx} colSpan={span?.colSpan || 1} rowSpan={span?.rowSpan || 1}
                      title={cell.formula ? `Formula: ${cell.formula}` : undefined}
                      className="border border-gray-200 px-2 py-1 whitespace-nowrap"
                      style={{
                        fontWeight: cell.bold ? 700 : 400,
                        fontStyle: cell.italic ? 'italic' : 'normal',
                        backgroundColor: cell.fill || undefined,
                        textAlign: cell.align || 'left',
                        minWidth: '70px',
                      }}>
                      {cell.value !== null && cell.value !== undefined ? String(cell.value) : ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sheets.length > 1 && (
        <div className="flex items-center gap-1 px-2 py-1.5 border-t border-gray-200 bg-gray-50 overflow-x-auto">
          {sheets.map((s, idx) => (
            <button key={s.name} onClick={() => setActiveSheet(idx)}
              className={`px-3 py-1 text-xs font-medium rounded-md whitespace-nowrap transition-colors ${
                idx === activeSheet ? 'bg-gray-200 text-gray-800' : 'text-gray-500 hover:bg-gray-100'
              }`}>
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ImagePreview({ tenderId, path }) {
  return (
    <div className="h-full overflow-auto bg-gray-100 flex items-center justify-center p-6">
      <img src={previewUrl(tenderId, path)} alt={path} className="max-w-full max-h-full rounded-lg shadow-md" />
    </div>
  );
}

function TextPreview({ tenderId, path }) {
  const [text, setText] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetch(`${API_URL}/tenders/${tenderId}/text/${encodeURIComponent(path)}`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((data) => active && setText(data.content || ''))
      .catch(() => active && setText('Could not load file content.'))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [tenderId, path]);

  if (loading) return <CenteredState icon={<Loader size={24} className="animate-spin text-gray-400" />} text="Loading…" />;

  return (
    <div className="h-full overflow-auto bg-white p-6">
      <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{text}</pre>
    </div>
  );
}

function UnsupportedPreview({ tenderId, path }) {
  return (
    <CenteredState icon={<File size={32} className="text-gray-300" />} text="No inline preview available for this file type." action={
      <a href={rawDownloadUrl(tenderId, path)} className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: BRAND.gradient }}>
        <Download size={14} /> Download file
      </a>
    } />
  );
}

function PreviewPane({ tenderId, path, xlsxState }) {
  if (!path) {
    return <CenteredState icon={<FileText size={40} className="text-gray-200" />} text="Select a file from the explorer to preview it here." />;
  }
  const ext = extOf(path);
  if (ext === 'pdf') return <PdfPreview tenderId={tenderId} path={path} />;
  if (ext === 'docx') return <DocxPreview tenderId={tenderId} path={path} />;
  if (ext === 'doc') return <UnsupportedPreview tenderId={tenderId} path={path} />;
  if (isXlsxExt(ext)) {
    return (
      <XlsxPreview
        tenderId={tenderId}
        path={path}
        sheets={xlsxState?.sheets}
        loading={xlsxState?.loading}
        error={xlsxState?.error}
      />
    );
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) return <ImagePreview tenderId={tenderId} path={path} />;
  if (['txt', 'csv', 'md', 'xml', 'json'].includes(ext)) return <TextPreview tenderId={tenderId} path={path} />;
  return <UnsupportedPreview tenderId={tenderId} path={path} />;
}

/* ------------------------------------------------------------------ */
/* Main Modal – 3-panel: Explorer | Viewer | Document Intelligence     */
/* ------------------------------------------------------------------ */

export default function ZipViewerModal({ tenderId, tenderTitle, onClose }) {
  const [tree, setTree] = useState(null);
  const [files, setFiles] = useState([]);
  const [fileCount, setFileCount] = useState(0);
  const [zipUrl, setZipUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [visible, setVisible] = useState(false);
  const [intelOpen, setIntelOpen] = useState(true);
  const [showChat, setShowChat] = useState(false);
  const [tabs, setTabs] = useState([]);
  const [activeTabIndex, setActiveTabIndex] = useState(0);
  const [xlsxCache, setXlsxCache] = useState({});

  // ═══ Resizable right panel ═══
  const [rightPanelWidth, setRightPanelWidth] = useState(288); // 72 * 4 = 288px
  const [isDragging, setIsDragging] = useState(false);
  const dragStartX = useRef(0);
  const dragStartWidth = useRef(288);

  const onDragStart = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartX.current = e.clientX;
    dragStartWidth.current = rightPanelWidth;
  }, [rightPanelWidth]);

  useEffect(() => {
    if (!isDragging) return;

    const onMouseMove = (e) => {
      const delta = dragStartX.current - e.clientX; // inverted: drag left = larger
      const newWidth = Math.max(200, Math.min(600, dragStartWidth.current + delta));
      setRightPanelWidth(newWidth);
    };

    const onMouseUp = () => setIsDragging(false);

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isDragging]);

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const handleClose = useCallback(() => {
    setVisible(false);
    setTimeout(() => onCloseRef.current(), 160);
  }, []);

  const loadContents = useCallback(() => {
    setLoading(true); setError(null);
    fetch(`${API_URL}/tenders/${tenderId}/files`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) { const body = await r.json().catch(() => ({})); throw new Error(body.detail || `Server returned ${r.status}`); }
        return r.json();
      })
      .then((data) => {
        setTree(data.tree);
        setFiles(data.files || []);
        setFileCount(data.file_count || 0);
        setZipUrl(data.dce_zip_url || null);
        const flat = data.files || [];
        const firstPdf = flat.find((f) => f.path.toLowerCase().endsWith('.pdf'));
        const firstFile = firstPdf || flat[0];
        if (firstFile) {
          setTabs([{ path: firstFile.path, name: firstFile.path.split('/').pop() }]);
          setActiveTabIndex(0);
        } else {
          setTabs([]);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tenderId]);

  useEffect(() => { loadContents(); }, [loadContents]);

  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    const onKey = (e) => { if (e.key === 'Escape') handleClose(); };
    document.addEventListener('keydown', onKey);
    return () => { cancelAnimationFrame(id); document.removeEventListener('keydown', onKey); };
  }, [handleClose]);

  const handleFileClick = (path) => {
    const name = path.split('/').pop();
    const existingIndex = tabs.findIndex((t) => t.path === path);
    if (existingIndex !== -1) {
      setActiveTabIndex(existingIndex);
      return;
    }
    setTabs((prev) => [...prev, { path, name }]);
    setActiveTabIndex(tabs.length);
  };

  const closeTab = (index, e) => {
    e.stopPropagation();
    if (tabs.length === 1) return;
    const newTabs = tabs.filter((_, i) => i !== index);
    setTabs(newTabs);
    if (activeTabIndex >= newTabs.length) {
      setActiveTabIndex(newTabs.length - 1);
    } else if (activeTabIndex === index) {
      setActiveTabIndex(Math.min(index, newTabs.length - 1));
    }
  };

  const activeTab = tabs[activeTabIndex];
  const activeFileMeta = activeTab ? files.find((f) => f.path === activeTab.path) : null;
  const activeExt = activeTab ? extOf(activeTab.path) : '';

  useEffect(() => {
    if (!activeTab || !isXlsxExt(activeExt)) return;
    if (xlsxCache[activeTab.path]) return;

    setXlsxCache((prev) => ({ ...prev, [activeTab.path]: { sheets: null, loading: true, error: null } }));
    fetch(`${API_URL}/tenders/${tenderId}/text/${encodeURIComponent(activeTab.path)}`, { headers: authHeaders() })
      .then((r) => { if (!r.ok) throw new Error(`Server returned ${r.status}`); return r.json(); })
      .then((data) => {
        setXlsxCache((prev) => ({ ...prev, [activeTab.path]: { sheets: data.sheets || [], loading: false, error: null } }));
      })
      .catch((e) => {
        setXlsxCache((prev) => ({ ...prev, [activeTab.path]: { sheets: null, loading: false, error: e.message } }));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab?.path, activeExt, tenderId]);

  const zipDownloadUrl = zipUrl || `${API_URL}/tenders/${tenderId}/files`;

  const displayTitle = tenderTitle && tenderTitle.length > 50 
    ? tenderTitle.substring(0, 50) + '...' 
    : tenderTitle || 'Tender documents';

  const modalElement = (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div onClick={handleClose}
        className={`absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity duration-200 ${visible ? 'opacity-100' : 'opacity-0'}`} />

      <div className={`relative bg-white rounded-xl shadow-2xl w-full max-w-7xl h-[90vh] overflow-hidden flex flex-col transition-all duration-200 ease-out ${
        visible ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
      }`}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 flex-shrink-0 bg-white gap-3">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <FileArchive size={16} className="text-gray-500 flex-shrink-0" />
            <div className="min-w-0">
              <h3 className="font-semibold text-sm text-gray-800 truncate max-w-[300px] lg:max-w-[500px]" title={tenderTitle}>
                {displayTitle}
              </h3>
              <p className="text-[11px] text-gray-400">
                {loading ? 'Loading archive…' : `${fileCount} document${fileCount !== 1 ? 's' : ''}`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            {!loading && fileCount > 0 && (
              <a href={zipDownloadUrl} target="_blank" rel="noopener noreferrer"
                className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors border border-gray-200">
                <FileArchive size={14} /> Download ZIP
              </a>
            )}
            <button onClick={() => setShowChat(true)} 
              className="p-2 rounded-lg hover:bg-violet-100 transition-colors text-violet-500"
              title="Assistant IA">
              <Sparkles size={16} />
            </button>
            <button onClick={() => setIntelOpen((o) => !o)} 
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-400"
              title={intelOpen ? 'Hide panel' : 'Show panel'}>
              {intelOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
            </button>
            <button onClick={loadContents} 
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-400" 
              title="Refresh">
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            </button>
            <button onClick={handleClose} 
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-400" 
              title="Close">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        {loading ? (
          <CenteredState icon={<Loader size={28} className="animate-spin text-gray-400" />} text="Reading ZIP contents…" />
        ) : error ? (
          <CenteredState icon={<AlertCircle size={28} className="text-red-400" />} text={error} action={
            <button onClick={loadContents} className="mt-3 px-4 py-2 bg-gray-100 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-200">Retry</button>
          } />
        ) : fileCount === 0 ? (
          <CenteredState icon={<Folder size={32} className="text-gray-300" />} text="This tender has no DCE ZIP stored yet." />
        ) : (
          <div className="flex flex-1 min-h-0">
            {/* Left panel – file tree */}
            <div className="w-48 xl:w-56 border-r border-gray-100 overflow-y-auto py-2 flex-shrink-0 bg-gray-50/30">
              {tree && <TreeNode node={tree} depth={0} selectedPath={activeTab?.path} onSelectFile={handleFileClick} />}
            </div>

            {/* Center panel – tabs + preview */}
            <div className="flex-1 min-w-0 flex flex-col border-r border-gray-100">
              {tabs.length > 0 && (
                <div className="flex items-center gap-1 px-3 py-1.5 border-b border-gray-200 overflow-x-auto flex-shrink-0 bg-gray-50">
                  {tabs.map((tab, idx) => (
                    <div
                      key={tab.path}
                      onClick={() => setActiveTabIndex(idx)}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium cursor-pointer whitespace-nowrap transition-colors ${
                        idx === activeTabIndex
                          ? 'bg-white text-gray-800 shadow-sm border border-gray-200'
                          : 'text-gray-500 hover:bg-gray-100'
                      }`}
                    >
                      {iconForFile(tab.name)}
                      <span className="max-w-[120px] truncate">{tab.name}</span>
                      {tabs.length > 1 && (
                        <button onClick={(e) => closeTab(idx, e)}
                          className="ml-0.5 p-0.5 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600">
                          <X size={12} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex-1 min-h-0">
                {activeTab ? (
                  <div className="flex flex-col h-full">
                    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-white flex-shrink-0">
                      <div className="flex items-center gap-2 min-w-0">
                        {iconForFile(activeTab.name)}
                        <span className="text-xs font-medium text-gray-700 truncate">{activeTab.path}</span>
                      </div>
                      <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                        <a href={rawDownloadUrl(tenderId, activeTab.path)} title="Download this file"
                          className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors font-medium">
                          <Download size={13} /> Download
                        </a>
                      </div>
                    </div>
                    <div className="flex-1 min-h-0">
                      <PreviewPane tenderId={tenderId} path={activeTab.path} xlsxState={activeTab ? xlsxCache[activeTab.path] : null} />
                    </div>
                  </div>
                ) : (
                  <CenteredState icon={<FileText size={40} className="text-gray-200" />} text="Select a file from the explorer to preview it here." />
                )}
              </div>
            </div>

            {/* Right panel – Document Intelligence (RESIZABLE) */}
            {intelOpen && (
              <div 
                className="flex-shrink-0 overflow-hidden bg-white relative"
                style={{ width: `${rightPanelWidth}px` }}
              >
                {/* Drag handle – on the left edge of the right panel */}
                <div
                  onMouseDown={onDragStart}
                  className={`absolute left-0 top-0 bottom-0 w-2.5 cursor-col-resize z-10 group ${
                    isDragging ? 'bg-violet-200/60' : 'hover:bg-violet-100/40'
                  }`}
                  style={{ marginLeft: '-5px' }}
                >
                  <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 transition-opacity ${
                    isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                  }`}>
                    <GripVertical size={16} className="text-violet-400" />
                  </div>
                </div>
                
                <div className="h-full overflow-y-auto">
                  <DocumentIntelligencePanel
                    tenderId={tenderId}
                    filePath={activeTab?.path || null}
                    fileMeta={activeFileMeta}
                    xlsxState={activeTab ? xlsxCache[activeTab.path] : null}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showChat && (
        <ZipChatBot
          tenderId={tenderId}
          tenderTitle={tenderTitle}
          onClose={() => setShowChat(false)}
        />
      )}
    </div>
  );

  return ReactDOM.createPortal(modalElement, document.body);
}