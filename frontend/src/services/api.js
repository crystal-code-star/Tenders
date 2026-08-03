import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || window.location.origin;

// Create axios instance with auth interceptor
const api = axios.create({
  baseURL: API_BASE,
});

// Add token to every request automatically
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// ============================================
// EXISTING FUNCTIONS (using axios)
// ============================================

export const fetchPosts = () => api.get('/posts');

export const generateCampaign = (topic) => api.post('/generate', { topic });

export const updatePost = (dayId, data) => api.put(`/posts/${dayId}`, data);

export const setSchedule = (scheduleData) => api.post('/schedule', scheduleData);

export const clearCampaign = () => api.delete('/posts');

export const uploadPostImage = (dayId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  return api.post(`/posts/${dayId}/upload-image`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

// Alias for backward compatibility
export const uploadImage = uploadPostImage;

// ============================================
// NEW FUNCTIONS FOR PRODUCT-BASED GENERATION
// ============================================

export const getProducts = () => api.get('/products');

export const searchProducts = (query) => api.get(`/products/search?query=${encodeURIComponent(query)}`);

export const getProductDetails = (productName) => api.get(`/products/${encodeURIComponent(productName)}`);

export const generateProductCampaign = (productName, language = 'english') => 
  api.post('/generate-product', { 
    product_name: productName, 
    language: language 
  });

export default api;