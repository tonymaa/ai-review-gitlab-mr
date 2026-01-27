/**
 * API 客户端
 */

import axios from 'axios';
import type {
  AxiosError,
} from 'axios';
import type {
  AppConfig,
  Project,
  MergeRequest,
  RelatedMR,
  DiffFile,
  Note,
  ReviewResponse,
  CommentRequest,
} from '../types';

class APIClient {
  private client: ReturnType<typeof axios.create>;

  constructor() {
    this.client = axios.create({
      baseURL: '/api',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // ==================== Health ====================

  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // ==================== Config ====================

  async getConfig(): Promise<AppConfig> {
    const response = await this.client.get('/config/config');
    return response.data;
  }

  async updateConfig(config: Partial<AppConfig>): Promise<{ status: string; message: string }> {
    const response = await this.client.post('/config/config', config);
    return response.data;
  }

  // ==================== GitLab ====================

  async connectGitLab(url: string, token: string): Promise<{
    status: string;
    message: string;
    user: { id: number; name: string; username: string; avatar_url?: string } | null;
  }> {
    const response = await this.client.post('/gitlab/connect', { url, token });
    return response.data;
  }

  async listProjects(search?: string): Promise<Project[]> {
    const response = await this.client.get('/gitlab/projects', {
      params: { search, membership: true },
    });
    return response.data;
  }

  async getProject(projectId: string): Promise<Project> {
    const response = await this.client.get(`/gitlab/projects/${projectId}`);
    return response.data;
  }

  async listMergeRequests(projectId: string, state: 'opened' | 'closed' | 'merged' | 'all' = 'opened'): Promise<MergeRequest[]> {
    const response = await this.client.get(`/gitlab/projects/${projectId}/merge-requests`, {
      params: { state },
    });
    return response.data;
  }

  async getMergeRequest(projectId: string, mrIid: number): Promise<MergeRequest> {
    const response = await this.client.get(`/gitlab/projects/${projectId}/merge-requests/${mrIid}`);
    return response.data;
  }

  async getMergeRequestDiffs(projectId: string, mrIid: number): Promise<DiffFile[]> {
    const response = await this.client.get(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/diffs`);
    return response.data;
  }

  async getMergeRequestNotes(projectId: string, mrIid: number): Promise<Note[]> {
    const response = await this.client.get(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/notes`);
    return response.data;
  }

  async createMergeRequestNote(
    projectId: string,
    mrIid: number,
    request: CommentRequest
  ): Promise<{ status: string; message: string }> {
    const response = await this.client.post(
      `/gitlab/projects/${projectId}/merge-requests/${mrIid}/notes`,
      request
    );
    return response.data;
  }

  async deleteMergeRequestNote(projectId: string, mrIid: number, noteId: number): Promise<{ status: string; message: string }> {
    const response = await this.client.delete(
      `/gitlab/projects/${projectId}/merge-requests/${mrIid}/notes/${noteId}`
    );
    return response.data;
  }

  async approveMergeRequest(projectId: string, mrIid: number): Promise<{ status: string; message: string }> {
    const response = await this.client.post(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/approve`);
    return response.data;
  }

  async unapproveMergeRequest(projectId: string, mrIid: number): Promise<{ status: string; message: string }> {
    const response = await this.client.post(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/unapprove`);
    return response.data;
  }

  async listRelatedMergeRequests(state: 'opened' | 'closed' | 'merged' | 'all' = 'opened'): Promise<RelatedMR[]> {
    const response = await this.client.get('/gitlab/merge-requests/related', {
      params: { state },
    });
    return response.data;
  }

  // ==================== AI ====================

  async startReview(projectId: string, mrIid: number, provider: string = 'openai'): Promise<{
    status: string;
    task_id: string;
  }> {
    const response = await this.client.post('/ai/review', {
      project_id: projectId,
      mr_iid: mrIid,
      provider,
    });
    return response.data;
  }

  async getReviewStatus(taskId: string): Promise<ReviewResponse | { status: string }> {
    const response = await this.client.get(`/ai/review/${taskId}`);
    return response.data;
  }

  async reviewSingleFile(projectId: string, mrIid: number, filePath: string, provider: string = 'openai'): Promise<ReviewResponse> {
    const response = await this.client.post('/ai/review/file', {
      project_id: projectId,
      mr_iid: mrIid,
      file_path: filePath,
      provider,
    });
    return response.data;
  }

  async getAIConfig(): Promise<{
    provider: string;
    openai: {
      model: string;
      base_url?: string;
      api_key: string;
      temperature: number;
      max_tokens: number;
    };
    ollama: {
      base_url: string;
      model: string;
    };
    review_rules: string[];
  }> {
    const response = await this.client.get('/ai/config');
    return response.data;
  }
}

// 单例实例
export const api = new APIClient();
