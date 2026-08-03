import React, { useState, useEffect } from 'react';
import { 
  Search, Image as ImageIcon, Edit3, CheckCircle, XCircle, 
  AlertCircle, Clock, Upload, Calendar, CheckCheck, RefreshCw, 
  Globe, Sparkles, Save, X, PenTool, Plus, FileText 
} from 'lucide-react';
import { useToast } from '../App';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const STATUS_PILL = {
  pending: { label: 'Pending', bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  approved: { label: 'Approved', bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  posted: { label: 'Posted', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  rejected: { label: 'Rejected', bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

const Posts = ({ posts: externalPosts = [], stats: externalStats = {}, onUpdateStatus, onUploadImage, setActiveTab }) => {
  const toast = useToast();

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [activePost, setActivePost] = useState(null);
  const [editingText, setEditingText] = useState('');
  const [isUpdating, setIsUpdating] = useState(false);
  const [uploadingPostId, setUploadingPostId] = useState(null);
  const [regeneratingPostId, setRegeneratingPostId] = useState(null);
  const [editingPostId, setEditingPostId] = useState(null);
  const [tempEditText, setTempEditText] = useState('');
  const [localPosts, setLocalPosts] = useState([]);
  const [localStats, setLocalStats] = useState({ total: 0, pending: 0, approved: 0, posted: 0, rejected: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch posts from database
  const fetchPosts = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/posts`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Handle both array response and object with posts property
      const postsData = Array.isArray(data) ? data : (data.posts || data.data || []);
      setLocalPosts(postsData);
      
      // Calculate stats
      const stats = {
        total: postsData.length,
        pending: postsData.filter(p => p.status === 'pending').length,
        approved: postsData.filter(p => p.status === 'approved').length,
        posted: postsData.filter(p => p.status === 'posted').length,
        rejected: postsData.filter(p => p.status === 'rejected').length,
      };
      setLocalStats(stats);
      
    } catch (err) {
      console.error('Error fetching posts:', err);
      setError(err.message);
      toast.error('Failed to load posts from database');
    } finally {
      setLoading(false);
    }
  };

  // Fetch posts on component mount and when external posts change
  useEffect(() => {
    if (externalPosts && externalPosts.length > 0) {
      setLocalPosts(externalPosts);
      const stats = {
        total: externalPosts.length,
        pending: externalPosts.filter(p => p.status === 'pending').length,
        approved: externalPosts.filter(p => p.status === 'approved').length,
        posted: externalPosts.filter(p => p.status === 'posted').length,
        rejected: externalPosts.filter(p => p.status === 'rejected').length,
      };
      setLocalStats(stats);
    } else {
      fetchPosts();
    }
  }, [externalPosts]);

  // Use external stats if provided, otherwise use local stats
  const displayStats = externalStats && Object.keys(externalStats).length > 0 ? externalStats : localStats;
  const displayPosts = externalPosts && externalPosts.length > 0 ? externalPosts : localPosts;

  const safePosts = Array.isArray(displayPosts) ? displayPosts : [];

  const filteredPosts = safePosts.filter(p => {
    const matchesSearch = (p.post_text || p.topic || "").toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const isPostEditable = (post) => post.status === 'pending' || post.status === 'approved';

  const handleEdit = (post) => {
    setActivePost(post);
    setEditingText(post.post_text);
  };

  const handleSave = async () => {
    setIsUpdating(true);
    try {
      await onUpdateStatus(activePost.id, 'approved', editingText);
      setActivePost(null);
      toast.success('Post approved and saved!');
      fetchPosts(); // Refresh posts after update
    } catch (err) {
      toast.error('Failed to update post.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleQuickApprove = async (id) => {
    setIsUpdating(true);
    try {
      await onUpdateStatus(id, 'approved', null);
      toast.success('Post approved!');
      fetchPosts(); // Refresh posts after update
    } catch (err) {
      toast.error('Failed to approve post.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleQuickReject = async (id) => {
    setIsUpdating(true);
    try {
      await onUpdateStatus(id, 'rejected', null);
      toast.warning('Post rejected.');
      fetchPosts(); // Refresh posts after update
    } catch (err) {
      toast.error('Failed to reject post.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleReject = async (id) => {
    setIsUpdating(true);
    try {
      await onUpdateStatus(id, 'rejected', null);
      setActivePost(null);
      toast.warning('Post rejected.');
      fetchPosts(); // Refresh posts after update
    } catch (err) {
      toast.error('Failed to reject post.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleSaveInlineEdit = async (postId) => {
    setIsUpdating(true);
    try {
      const post = safePosts.find(p => p.id === postId);
      await onUpdateStatus(postId, post.status, tempEditText);
      setEditingPostId(null);
      setTempEditText('');
      toast.success('Text saved!');
      fetchPosts(); // Refresh posts after update
    } catch (err) {
      toast.error('Failed to save text.');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCancelInlineEdit = () => {
    setEditingPostId(null);
    setTempEditText('');
  };

  const handleStartInlineEdit = (post) => {
    setEditingPostId(post.id);
    setTempEditText(post.post_text);
  };

  const handleFileChange = async (e, postId) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { toast.warning('Please select an image file'); return; }
    if (file.size > 5 * 1024 * 1024) { toast.warning('Image size should be less than 5MB'); return; }
    if (onUploadImage) {
      setUploadingPostId(postId);
      try {
        await onUploadImage(postId, file);
        toast.success('Image uploaded successfully!');
        e.target.value = '';
        fetchPosts(); // Refresh posts after upload
      } catch (err) {
        toast.error('Failed to upload image.');
      } finally {
        setUploadingPostId(null);
      }
    }
  };

  const handleRegenerateImageWeb = async (postId, topic, angleKey) => {
    if (!isPostEditable({ status: safePosts.find(p => p.id === postId)?.status })) {
      toast.warning('Cannot regenerate image for posted/rejected posts.');
      return;
    }
    setRegeneratingPostId(postId);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/posts/${postId}/regenerate-image-web`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ topic, angle_key: angleKey || 'Education' }),
      });
      const data = await response.json();
      if (data.success) {
        toast.success('Web image found and applied!');
        fetchPosts(); // Refresh posts after regeneration
      } else {
        toast.warning('No suitable web image found. Try AI generation.');
      }
    } catch (err) {
      toast.error('Failed to search web image.');
    } finally {
      setRegeneratingPostId(null);
    }
  };

  const handleRegenerateImageAI = async (postId, topic, angleKey, dayNumber) => {
    if (!isPostEditable({ status: safePosts.find(p => p.id === postId)?.status })) {
      toast.warning('Cannot regenerate image for posted/rejected posts.');
      return;
    }
    setRegeneratingPostId(postId);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_URL}/posts/${postId}/regenerate-image-ai`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ topic, angle_key: angleKey || 'Education', day_number: dayNumber || 1 }),
      });
      const data = await response.json();
      if (data.success) {
        toast.success('AI image generated and applied!');
        fetchPosts(); // Refresh posts after regeneration
      } else {
        toast.error('AI generation failed: ' + (data.error || 'Unknown error'));
      }
    } catch (err) {
      toast.error('Failed to generate AI image.');
    } finally {
      setRegeneratingPostId(null);
    }
  };

  const formatDate = (date) => {
    if (!date) return '—';
    return new Date(date).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  // Loading state
  if (loading && safePosts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-8 h-8 rounded-full border-2 border-slate-200 border-t-[#0A66C2] animate-spin mb-4" />
        <p className="text-sm text-slate-500">Loading posts from database...</p>
      </div>
    );
  }

  // Error state
  if (error && safePosts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="bg-red-50 p-5 rounded-full inline-flex mb-5">
          <AlertCircle size={36} className="text-red-400" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 mb-2">Failed to load posts</h3>
        <p className="text-sm text-slate-500 mb-6">{error}</p>
        <button
          onClick={fetchPosts}
          className="bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white px-6 py-3 rounded-xl font-bold text-sm hover:shadow-lg transition-all inline-flex items-center gap-2"
        >
          <RefreshCw size={16} />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ═══ HERO HEADER - Style Dashboard ═══ */}
      <div className="relative overflow-hidden bg-gradient-to-br from-[#0A66C2] via-[#004182] to-[#0a2d5c] rounded-2xl p-6 shadow-lg">
        <div className="absolute top-0 right-0 w-48 h-48 bg-white/5 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-blue-400/10 rounded-full translate-y-1/2 -translate-x-1/2 blur-2xl"></div>
        
        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            
            <h1 className="text-2xl md:text-3xl font-bold text-white leading-tight">
              Campaign Posts
            </h1>
            <p className="text-blue-100/80 text-sm mt-1 max-w-xl">
              Review, edit, and manage your AI-generated LinkedIn content
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Stats Pills */}
            <div className="hidden sm:flex items-center gap-2">
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {displayStats.total || safePosts.length} Total
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {displayStats.pending || 0} Pending
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {displayStats.approved || 0} Approved
              </span>
              <span className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-semibold border border-white/20">
                {displayStats.posted || 0} Posted
              </span>
            </div>
            
            {/* New Post Button */}
            <button
              onClick={() => setActiveTab('generate')}
              className="bg-white text-[#0A66C2] px-5 py-2.5 rounded-xl font-bold text-sm hover:bg-blue-50 transition-all shadow-lg flex items-center gap-2 group"
            >
              <Plus size={16} className="group-hover:rotate-90 transition-transform" />
              New Post
            </button>
            
            {/* Refresh Button */}
            <button
              onClick={fetchPosts}
              className="bg-white/20 backdrop-blur-sm text-white p-2.5 rounded-xl hover:bg-white/30 transition-all"
              title="Refresh posts"
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* ═══ SEARCH + FILTER + NEW POST (Mobile) ═══ */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="flex-1 min-w-[200px] relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search posts by text or topic..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-[#0A66C2] focus:border-transparent outline-none shadow-sm"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm text-slate-700 outline-none focus:ring-2 focus:ring-[#0A66C2] shadow-sm"
        >
          <option value="all">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="posted">Posted</option>
          <option value="rejected">Rejected</option>
        </select>
        
        {/* Mobile New Post Button */}
        <button
          onClick={() => setActiveTab('generate')}
          className="sm:hidden bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white px-4 py-2.5 rounded-xl font-semibold text-sm hover:shadow-md transition-all flex items-center gap-2"
        >
          <Plus size={14} />
          New Post
        </button>
      </div>

      {/* ═══ CONTENT ═══ */}
      {filteredPosts.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-2xl p-16 text-center shadow-sm">
          <div className="bg-slate-50 p-5 rounded-full inline-flex mb-5">
            <AlertCircle size={36} className="text-slate-300" />
          </div>
          <h3 className="text-lg font-bold text-slate-900 mb-2">No posts found</h3>
          <p className="text-sm text-slate-500 mb-6">
            {safePosts.length === 0 
              ? 'Generate your first campaign to start creating LinkedIn content'
              : 'Try adjusting your search or filter criteria'}
          </p>
          <button
            onClick={() => setActiveTab('generate')}
            className="bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white px-6 py-3 rounded-xl font-bold text-sm hover:shadow-lg transition-all inline-flex items-center gap-2"
          >
            <PenTool size={16} />
            {safePosts.length === 0 ? 'Create First Campaign' : 'Generate New Posts'}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPosts.map((post) => {
            const editable = isPostEditable(post);
            const isEditingThis = editingPostId === post.id;
            const pill = STATUS_PILL[post.status] || { label: post.status || 'Unknown', bg: 'bg-slate-50', text: 'text-slate-600', border: 'border-slate-200' };

            return (
              <div key={post.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:border-slate-300 transition-all hover:shadow-md group">
                {/* Image */}
                <div className="aspect-video bg-slate-100 relative overflow-hidden">
                  {post.image_url ? (
                    <img
                      src={post.image_url.startsWith('http') ? post.image_url : `${API_URL}${post.image_url}`}
                      alt={post.topic || 'Post image'}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-300">
                      <ImageIcon size={40} />
                    </div>
                  )}

                  {editable && (
                    <label
                      htmlFor={`file-${post.id}`}
                      className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-slate-900/0 group-hover:bg-slate-900/50 transition-all cursor-pointer opacity-0 group-hover:opacity-100 text-white text-xs font-semibold uppercase tracking-wider"
                    >
                      {uploadingPostId === post.id ? (
                        <>
                          <div className="w-6 h-6 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                          <span>Uploading...</span>
                        </>
                      ) : (
                        <>
                          <Upload size={22} />
                          <span>Change image</span>
                        </>
                      )}
                    </label>
                  )}
                  {editable && (
                    <input
                      type="file"
                      id={`file-${post.id}`}
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => handleFileChange(e, post.id)}
                      disabled={uploadingPostId === post.id}
                    />
                  )}

                  <span className={`absolute top-3 right-3 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm ${pill.bg} ${pill.text} ${pill.border}`}>
                    {pill.label}
                  </span>
                  <span className="absolute top-3 left-3 px-2.5 py-1 rounded-full text-xs font-semibold bg-white/90 text-slate-600 shadow-sm backdrop-blur-sm">
                    #{post.id}{post.day_number && ` · D${post.day_number}`}
                  </span>
                </div>

                {/* Body */}
                <div className="p-4 flex flex-col gap-3.5">
                  {/* Topic/Title */}
                  {post.topic && (
                    <h3 className="text-sm font-semibold text-slate-900 line-clamp-1">
                      {post.topic}
                    </h3>
                  )}
                  
                  {isEditingThis ? (
                    <div className="space-y-2">
                      <textarea
                        value={tempEditText}
                        onChange={(e) => setTempEditText(e.target.value)}
                        className="w-full h-32 text-sm p-3 bg-slate-50 border border-slate-200 rounded-lg resize-none outline-none focus:ring-2 focus:ring-[#0A66C2]"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveInlineEdit(post.id)}
                          disabled={isUpdating}
                          className="flex-1 py-2 bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 hover:shadow-md transition-all"
                        >
                          <Save size={12} /> Save
                        </button>
                        <button
                          onClick={handleCancelInlineEdit}
                          className="flex-1 py-2 bg-white text-slate-600 border border-slate-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 hover:bg-slate-50 transition-all"
                        >
                          <X size={12} /> Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-700 leading-relaxed line-clamp-4 whitespace-pre-wrap">
                      {post.post_text}
                    </p>
                  )}

                  {/* Meta */}
                  <div className="space-y-1.5 pt-3 border-t border-slate-100">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <Calendar size={11} />
                      <span className="w-16 flex-shrink-0 text-slate-400">Created:</span>
                      <span>{formatDate(post.created_at)}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <Clock size={11} className={post.scheduled_for ? 'text-emerald-500' : 'text-slate-400'} />
                      <span className="w-16 flex-shrink-0 text-slate-400">Scheduled:</span>
                      <span className={post.scheduled_for ? 'text-slate-700' : 'text-slate-400 italic'}>
                        {post.scheduled_for ? formatDate(post.scheduled_for) : 'Not scheduled'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <CheckCheck size={11} className={post.posted_at ? 'text-emerald-500' : 'text-slate-400'} />
                      <span className="w-16 flex-shrink-0 text-slate-400">Posted:</span>
                      <span className={post.posted_at ? 'text-slate-700 font-medium' : 'text-slate-400 italic'}>
                        {post.posted_at ? formatDate(post.posted_at) : 'Not posted'}
                      </span>
                    </div>
                  </div>

                  {/* Additional Info */}
                  {post.product_name && (
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <FileText size={11} />
                      <span className="w-16 flex-shrink-0 text-slate-400">Product:</span>
                      <span>{post.product_name}</span>
                    </div>
                  )}

                  {/* Edit + regenerate actions */}
                  {editable && (
                    <div className="space-y-2.5 pt-3 border-t border-slate-100">
                      {!isEditingThis && (
                        <button
                          onClick={() => handleStartInlineEdit(post)}
                          className="w-full py-2 bg-slate-50 text-slate-600 border border-slate-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 hover:bg-slate-100 transition-all"
                        >
                          <Edit3 size={12} /> Edit text
                        </button>
                      )}

                      <div>
                        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Regenerate image</p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleRegenerateImageWeb(post.id, post.product_name || post.topic, post.day_angle)}
                            disabled={regeneratingPostId === post.id}
                            className="flex-1 py-2 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 hover:bg-emerald-100 transition-all disabled:opacity-50"
                          >
                            {regeneratingPostId === post.id ? (
                              <RefreshCw size={11} className="animate-spin" />
                            ) : (
                              <Globe size={11} />
                            )}
                            Web
                          </button>
                          <button
                            onClick={() => handleRegenerateImageAI(post.id, post.product_name || post.topic, post.day_angle, post.day_number)}
                            disabled={regeneratingPostId === post.id}
                            className="flex-1 py-2 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 hover:bg-amber-100 transition-all disabled:opacity-50"
                          >
                            {regeneratingPostId === post.id ? (
                              <RefreshCw size={11} className="animate-spin" />
                            ) : (
                              <Sparkles size={11} />
                            )}
                            AI
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Footer decision row */}
                  <div className="flex items-center justify-end pt-3 border-t border-slate-100 mt-auto">
                    <div className="flex gap-1.5">
                      {post.status === 'pending' && (
                        <>
                          <button
                            onClick={() => handleQuickApprove(post.id)}
                            disabled={isUpdating}
                            className="p-2 text-emerald-500 hover:bg-emerald-50 rounded-lg transition-colors"
                            title="Approve"
                          >
                            <CheckCircle size={18} />
                          </button>
                          <button
                            onClick={() => handleQuickReject(post.id)}
                            disabled={isUpdating}
                            className="p-2 text-red-400 hover:bg-red-50 rounded-lg transition-colors"
                            title="Reject"
                          >
                            <XCircle size={18} />
                          </button>
                        </>
                      )}
                      {post.status === 'approved' && (
                        <span className="text-emerald-600 font-semibold text-xs">✓ Approved</span>
                      )}
                      {post.status === 'posted' && (
                        <span className="text-blue-600 font-semibold text-xs">Published</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Review modal */}
      {activePost && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-200 flex justify-between items-center bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white">
              <h3 className="text-lg font-bold">Review · Post #{activePost.id}</h3>
              <button onClick={() => setActivePost(null)} className="text-white/70 hover:text-white transition-colors">
                <XCircle size={20} />
              </button>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">LinkedIn post content</p>
                <textarea
                  value={editingText}
                  onChange={(e) => setEditingText(e.target.value)}
                  className="w-full h-56 text-sm p-4 bg-slate-50 border border-slate-200 rounded-xl resize-none outline-none focus:ring-2 focus:ring-[#0A66C2]"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleSave}
                  disabled={isUpdating}
                  className="flex-1 py-3 bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white rounded-xl text-sm font-bold hover:shadow-lg transition-all disabled:opacity-50"
                >
                  {isUpdating ? 'Saving...' : 'Approve & Save'}
                </button>
                <button
                  onClick={() => handleReject(activePost.id)}
                  disabled={isUpdating}
                  className="px-8 py-3 bg-white text-slate-600 border border-slate-200 rounded-xl text-sm font-semibold hover:border-red-300 hover:text-red-500 transition-all"
                >
                  Reject
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Posts;