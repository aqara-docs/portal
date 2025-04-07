import axios from 'axios';
import { DiscussionFormData, SearchParams, Discussion } from '../types/discussion';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:3001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const saveDiscussion = async (data: DiscussionFormData): Promise<Discussion> => {
  const response = await api.post<Discussion>('/discussions', data);
  return response.data;
};

export const searchDiscussions = async (params: SearchParams): Promise<Discussion[]> => {
  const response = await api.get<Discussion[]>('/discussions', { params });
  return response.data;
};

export const getDiscussion = async (id: number): Promise<Discussion> => {
  const response = await api.get<Discussion>(`/discussions/${id}`);
  return response.data;
};

export const saveMaterial = async (data: {
  book_title: string;
  file_name: string;
  content: string;
  type: 'summary' | 'application';
}) => {
  const response = await api.post('/reading-materials', data);
  return response.data;
};

export const saveDiscussionWithMaterials = async (data: {
  book_title: string;
  summary_file: {
    name: string;
    content: string;
  };
  application_file: {
    name: string;
    content: string;
  };
}) => {
  const response = await api.post('/discussions/with-materials', data);
  return response.data;
}; 