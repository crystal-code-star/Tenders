import { useState, useEffect, useCallback } from 'react';
import * as apiService from '../services/api';

export const useCampaign = () => {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(false);

  const refreshPosts = useCallback(async () => {
    try {
      const res = await apiService.fetchPosts();
      setPosts(res.data);
    } catch (err) {
      console.error("Failed to fetch posts", err);
    }
  }, []);

  useEffect(() => {
    refreshPosts();
    const interval = setInterval(refreshPosts, 5000);
    return () => clearInterval(interval);
  }, [refreshPosts]);

  const generate = async (topic) => {
    setLoading(true);
    try {
      await apiService.generateCampaign(topic);
      refreshPosts();
    } catch (err) {
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const generateProduct = async (productName, language) => {
    setLoading(true);
    try {
      await apiService.generateProductCampaign(productName, language);
      refreshPosts();
    } catch (err) {
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const updateStatus = async (dayId, status, text = null) => {
    try {
      if (text === null) {
        const currentPost = posts.find(p => p.id === dayId);
        if (currentPost) {
          await apiService.updatePost(dayId, { 
            post_text: currentPost.post_text,
            status: status
          });
        }
      } else {
        await apiService.updatePost(dayId, { 
          post_text: text,
          status: status
        });
      }
      refreshPosts();
    } catch (err) {
      throw err;
    }
  };

  const updateSchedule = async (scheduleData) => {
    try {
      await apiService.setSchedule(scheduleData);
      refreshPosts();
    } catch (err) {
      throw err;
    }
  };

  const clear = async () => {
    try {
      await apiService.clearCampaign();
      setPosts([]);
    } catch (err) {
      throw err;
    }
  };

  const stats = {
    total: posts.length,
    pending: posts.filter(p => p.status === 'pending').length,
    approved: posts.filter(p => p.status === 'approved').length,
    posted: posts.filter(p => p.status === 'posted').length,
    failed: posts.filter(p => p.status === 'rejected').length,
  };

  return {
    posts,
    loading,
    generate,
    generateProduct,
    updateStatus,
    updateSchedule,
    clear,
    stats,
    refreshPosts
  };
};