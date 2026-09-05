import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token
apiClient.interceptors.request.use(
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

export interface Video {
  id: string;
  name: string;
  description: string;
  mux_asset_id: string;
  mux_playback_id: string;
  mux_signed_playback_id: string;
  duration: number;
  status: 'encoding' | 'ready' | 'error';
  thumbnail_url?: string;
  created_at: string;
  updated_at: string;
}

export interface PlaybackToken {
  token: string;
  thumbnail: string;
  storyboard: string;
  expires_at: string;
}

export interface VideoStatus {
  video_id: string;
  status: string;
  duration: number;
}

export interface CreateVideoRequest {
  url: string;
  name: string;
  description?: string;
}

export interface DirectUploadResponse {
  upload_id: string;
  upload_url: string;
}

export interface CompleteUploadRequest {
  name: string;
  description?: string;
}

export interface LoginRequest {
  name: string;
  password: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  token: string;
  user: {
    id: string;
    name: string;
    role: string;
  };
}

// Get all videos
export const getVideos = async (): Promise<Video[]> => {
  const response = await apiClient.get<Video[]>('/api/videos');
  return response.data;
};

// Get single video by ID
export const getVideo = async (id: string): Promise<Video> => {
  const response = await apiClient.get<Video>(`/api/videos/${id}`);
  return response.data;
};

// Create new video from URL
export const uploadVideo = async (data: CreateVideoRequest): Promise<Video> => {
  const response = await apiClient.post<Video>('/api/videos', data);
  return response.data;
};

// Get playback token for video
export const getPlaybackToken = async (videoId: string): Promise<PlaybackToken> => {
  const response = await apiClient.post<PlaybackToken>(`/api/videos/${videoId}/playback-token`);
  return response.data;
};

// Get video encoding status
export const getVideoStatus = async (videoId: string): Promise<VideoStatus> => {
  const response = await apiClient.get<VideoStatus>(`/api/videos/${videoId}/status`);
  return response.data;
};

// Create direct upload
export const createDirectUpload = async (corsOrigin?: string): Promise<DirectUploadResponse> => {
  const response = await apiClient.post<DirectUploadResponse>('/api/uploads/create', {
    cors_origin: corsOrigin || 'http://localhost:3000',
  });
  return response.data;
};

// Upload file to Mux
export const uploadFileToMux = async (
  file: File,
  uploadUrl: string,
  onProgress?: (progress: number) => void
): Promise<void> => {
  await axios.put(uploadUrl, file, {
    headers: {
      'Content-Type': file.type,
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onProgress) {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      }
    },
  });
};

// Complete direct upload
export const completeDirectUpload = async (
  uploadId: string,
  data: CompleteUploadRequest
): Promise<Video> => {
  const response = await apiClient.post<Video>(`/api/uploads/${uploadId}/complete`, data);
  return response.data;
};

// Login user
export const loginUser = async (data: LoginRequest): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>('/api/auth/login', data);
  return response.data;
};

export default apiClient;
