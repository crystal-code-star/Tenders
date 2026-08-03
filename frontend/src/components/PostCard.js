import React, { useState } from 'react';
import { Share2, Upload, ImageOff, ChevronDown } from 'lucide-react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const STATUS_META = {
  pending: { label: 'Pending', dot: 'bg-amber-400' },
  approved: { label: 'Approved', dot: 'bg-emerald-500' },
  posted: { label: 'Posted', dot: 'bg-blue-500' },
  rejected: { label: 'Rejected', dot: 'bg-red-400' },
};

const Posts = ({ posts = [], loading, onUpdateStatus, onUploadImage }) => {
  const [expandedId, setExpandedId] = useState(null);
  const [filter, setFilter] = useState('all');

  const safePosts = Array.isArray(posts) ? posts : [];

  const stats = {
    pending: safePosts.filter((p) => p?.status === 'pending').length,
    approved: safePosts.filter((p) => p?.status === 'approved').length,
    posted: safePosts.filter((p) => p?.status === 'posted').length,
    rejected: safePosts.filter((p) => p?.status === 'rejected').length,
  };

  const visiblePosts = filter === 'all' ? safePosts : safePosts.filter((p) => p?.status === filter);

  const handleFileChange = (e, postId) => {
    const file = e.target.files?.[0];
    if (file && onUploadImage) onUploadImage(postId, file);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-8 h-8 rounded-full border-2 border-slate-200 border-t-[#0A66C2] animate-spin mb-4" />
        <p className="text-sm text-slate-500">Loading posts...</p>
      </div>
    );
  }

  if (safePosts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="bg-slate-50 p-4 rounded-full mb-4">
          <ImageOff size={32} className="text-slate-300" />
        </div>
        <p className="text-lg font-semibold text-slate-900 mb-1">No posts yet</p>
        <p className="text-sm text-slate-500">Generate some posts to start reviewing.</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Posts</h1>
        <p className="text-sm text-slate-500 mt-1">Review, approve and schedule your LinkedIn posts.</p>
      </div>

      {/* Filter row */}
      <div className="flex gap-2 pb-5 border-b border-slate-200 flex-wrap">
        {[
          { key: 'all', label: 'All', count: safePosts.length },
          { key: 'pending', label: 'Pending', count: stats.pending },
          { key: 'approved', label: 'Approved', count: stats.approved },
          { key: 'posted', label: 'Posted', count: stats.posted },
          { key: 'rejected', label: 'Rejected', count: stats.rejected },
        ].map((f) => {
          const active = filter === f.key;
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                active
                  ? 'bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white shadow-md'
                  : 'bg-white text-slate-600 border border-slate-200 hover:border-slate-300'
              }`}
            >
              {f.label} <span className={`ml-1 font-semibold ${active ? 'text-white/80' : 'text-slate-400'}`}>{f.count}</span>
            </button>
          );
        })}
      </div>

      {/* List */}
      {visiblePosts.length === 0 ? (
        <p className="text-sm text-slate-500 py-6">No posts in this category.</p>
      ) : (
        <div className="space-y-0">
          {visiblePosts.map((post) => {
            const isOpen = expandedId === post?.id;
            const meta = STATUS_META[post?.status] || { label: post?.status || 'Unknown', dot: 'bg-slate-400' };
            const canDecide = post?.status !== 'posted' && post?.status !== 'rejected';

            return (
              <div key={post?.id} className="border-b border-slate-200">
                <button
                  onClick={() => setExpandedId(isOpen ? null : post?.id)}
                  className="w-full flex items-center gap-4 py-4 px-1 text-left hover:bg-slate-50/50 transition-colors rounded-lg"
                >
                  <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${meta.dot}`} />
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm font-semibold text-slate-900 truncate">
                      {post?.topic || 'Untitled'}
                    </span>
                    <span className="text-xs text-slate-400">{meta.label}</span>
                  </span>
                  <ChevronDown size={16} className={`text-slate-400 transition-transform flex-shrink-0 ${isOpen ? 'rotate-180' : ''}`} />
                </button>

                {isOpen && (
                  <div className="pb-7 px-1 space-y-5">
                    {/* Image */}
                    {post?.image_url ? (
                      <div className="relative rounded-lg overflow-hidden border border-slate-200 group">
                        <img
                          src={post.image_url.startsWith('http') ? post.image_url : `${API_URL}${post.image_url}`}
                          alt=""
                          className="w-full h-48 object-cover"
                          onError={(e) => { e.target.style.display = 'none'; }}
                        />
                        <label
                          htmlFor={`file-${post?.id}`}
                          className="absolute inset-0 flex items-center justify-center gap-2 bg-slate-900/0 group-hover:bg-slate-900/50 transition-all cursor-pointer opacity-0 group-hover:opacity-100"
                        >
                          <Upload size={16} className="text-white" />
                          <span className="text-white text-sm font-medium">Replace image</span>
                        </label>
                        <input
                          type="file"
                          id={`file-${post?.id}`}
                          accept="image/*"
                          className="hidden"
                          onChange={(e) => handleFileChange(e, post?.id)}
                        />
                      </div>
                    ) : (
                      <label
                        htmlFor={`file-${post?.id}`}
                        className="flex items-center justify-center gap-2 h-24 border border-dashed border-slate-200 rounded-lg cursor-pointer text-slate-400 hover:border-slate-300 hover:text-slate-500 transition-colors"
                      >
                        <ImageOff size={16} />
                        <span className="text-sm">No image — click to add one</span>
                        <input
                          type="file"
                          id={`file-${post?.id}`}
                          accept="image/*"
                          className="hidden"
                          onChange={(e) => handleFileChange(e, post?.id)}
                        />
                      </label>
                    )}

                    {/* Text */}
                    <div>
                      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Post text</p>
                      <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
                        {post?.post_text}
                      </p>
                    </div>

                    {/* Dates */}
                    {(post?.scheduled_for || post?.posted_at) && (
                      <div className="flex gap-8 flex-wrap">
                        {post?.scheduled_for && (
                          <div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Scheduled for</p>
                            <p className="text-sm text-slate-600">{new Date(post.scheduled_for).toLocaleString()}</p>
                          </div>
                        )}
                        {post?.posted_at && (
                          <div>
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Posted on</p>
                            <p className="text-sm text-slate-600">{new Date(post.posted_at).toLocaleString()}</p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-3 items-center">
                      {canDecide ? (
                        <>
                          <button
                            onClick={() => onUpdateStatus(post?.id, { status: 'approved' })}
                            className="px-5 py-2.5 bg-gradient-to-r from-[#0A66C2] to-[#004182] text-white rounded-lg text-sm font-semibold hover:shadow-md transition-all"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => onUpdateStatus(post?.id, { status: 'rejected' })}
                            className="px-5 py-2.5 bg-white text-slate-600 border border-slate-200 rounded-lg text-sm font-semibold hover:border-red-300 hover:text-red-500 transition-all"
                          >
                            Reject
                          </button>
                        </>
                      ) : (
                        <span className="flex items-center gap-2 text-sm font-medium text-slate-500">
                          {post?.status === 'posted' && <Share2 size={14} />}
                          {post?.status === 'posted' ? 'Live on LinkedIn' : 'Removed from queue'}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default Posts;