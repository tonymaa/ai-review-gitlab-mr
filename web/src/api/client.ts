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
  User,
  Discussion,
} from '../types';

// Token 管理 key
const TOKEN_STORAGE_KEY = 'gitlab-ai-review-token';

class APIClient {
  private client: ReturnType<typeof axios.create>;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: '/api',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 从 localStorage 加载 token
    this.loadToken();

    // 请求拦截器 - 添加 token
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
          console.log('[Request] Adding Authorization header, token length:', this.token.length);
          console.log('[Request] URL:', config.url);
        } else {
          console.log('[Request] No token available for URL:', config.url);
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 响应拦截器
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        console.error('API Error:', error.response?.data || error.message);
        return Promise.reject(error);
      }
    );
  }

  // ==================== Token 管理 ====================

  private loadToken() {
    console.log('[APIClient] loadToken called');
    console.log('[APIClient] Storage key:', TOKEN_STORAGE_KEY);
    try {
      const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
      console.log('[APIClient] localStorage.getItem result:', stored ? `found (${stored.length} chars, starts with: ${stored.substring(0, 20)}...)` : 'not found');
      if (stored) {
        this.token = stored;
        console.log('[APIClient] Token loaded successfully into memory');
      }
    } catch (err) {
      console.error('[APIClient] Failed to load token from localStorage:', err);
    }
  }

  setToken(token: string | null) {
    this.token = token;
    try {
      if (token) {
        localStorage.setItem(TOKEN_STORAGE_KEY, token);
        console.log('[APIClient] Token saved to localStorage');
      } else {
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        console.log('[APIClient] Token removed from localStorage');
      }
    } catch (err) {
      console.error('Failed to save token to localStorage:', err);
    }
  }

  getToken(): string | null {
    return this.token;
  }

  clearToken() {
    console.log('[APIClient] clearToken called');
    console.log('[APIClient] Token before clear:', this.token ? `exists (${this.token.length} chars)` : 'null');
    console.log('[APIClient] localStorage before clear:', localStorage.getItem(TOKEN_STORAGE_KEY) ? 'exists' : 'null');
    this.setToken(null);
    console.log('[APIClient] Token after clear:', this.token ? `exists (${this.token.length} chars)` : 'null');
    console.log('[APIClient] localStorage after clear:', localStorage.getItem(TOKEN_STORAGE_KEY) ? 'exists' : 'null');
  }

  // ==================== Auth ====================

  async register(username: string, password: string): Promise<{ status: string; message: string; user: User; token: string }> {
    const response = await this.client.post('/auth/register', { username, password });
    const data = response.data;
    // 自动登录，保存 token
    this.setToken(data.token);
    return data;
  }

  async login(username: string, password: string): Promise<{ status: string; message: string; user: User; token: string }> {
    const response = await this.client.post('/auth/login', { username, password });
    const data = response.data;
    // 保存 token
    this.setToken(data.token);
    return data;
  }

  async logout(): Promise<{ status: string; message: string }> {
    const response = await this.client.post('/auth/logout');
    // 清除 token
    this.clearToken();
    return response.data;
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  async verifyToken(): Promise<{ status: string; message: string; user: User }> {
    const response = await this.client.post('/auth/verify-token');
    return response.data;
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

  async getMergeRequestDiscussions(projectId: string, mrIid: number): Promise<Discussion[]> {
    const response = await this.client.get(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/discussions`);
    return response.data;
  }

  async addDiscussionNote(
    projectId: string,
    mrIid: number,
    discussionId: string,
    body: string
  ): Promise<{ status: string; message: string }> {
    const response = await this.client.post(
      `/gitlab/projects/${projectId}/merge-requests/${mrIid}/discussions/${discussionId}/notes`,
      { body }
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

  async getMergeRequestApprovalState(projectId: string, mrIid: number): Promise<{
    approved: boolean;
    approved_by: Array<{ id: number; name: string; username: string; avatar_url?: string }>;
    approvers_required: number;
    approvals_left: number;
  }> {
    const response = await this.client.get(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/approval-state`);
    return response.data;
  }

  async acceptMergeRequest(
    projectId: string,
    mrIid: number,
    options?: {
      merge_commit_message?: string;
      should_remove_source_branch?: boolean;
      merge_when_pipeline_succeeds?: boolean;
    }
  ): Promise<{ status: string; message: string }> {
    const response = await this.client.put(`/gitlab/projects/${projectId}/merge-requests/${mrIid}/merge`, options);
    return response.data;
  }

  async listRelatedMergeRequests(state: 'opened' | 'closed' | 'merged' | 'all' = 'opened'): Promise<RelatedMR[]> {
    const response = await this.client.get('/gitlab/merge-requests/related', {
      params: { state },
    });
    return response.data;
  }

  async listAuthoredMergeRequests(state: 'opened' | 'closed' | 'merged' | 'all' = 'opened'): Promise<RelatedMR[]> {
    const response = await this.client.get('/gitlab/merge-requests/authored', {
      params: { state },
    });
    return response.data;
  }

  async listUsers(search?: string): Promise<{
    id: number;
    name: string;
    username: string;
    avatar_url?: string;
  }[]> {
    const response = await this.client.get('/gitlab/users', {
      params: search ? { search } : {},
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
    }, { timeout: 0 });
    return response.data;
  }

  async getReviewStatus(taskId: string): Promise<ReviewResponse | { status: string } | { status: 'error'; error: string }> {
    const response = await this.client.get(`/ai/review/${taskId}`, { timeout: 0 });
    return response.data;
  }

  async reviewSingleFile(projectId: string, mrIid: number, filePath: string, provider: string = 'openai'): Promise<ReviewResponse> {
    const response = await this.client.post('/ai/review/file', {
      project_id: projectId,
      mr_iid: mrIid,
      file_path: filePath,
      provider,
    }, { timeout: 0 });
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

  /**
   * AI 生成回复
   * @param projectId 项目 ID
   * @param mrIid MR IID
   * @param parentComment 父评论内容
   * @param provider AI 提供商
   */
  async generateAIReply(
    projectId: string,
    mrIid: number,
    parentComment: string,
    provider: string = 'openai'
  ): Promise<{ reply: string }> {
    const response = await this.client.post('/ai/reply', {
      project_id: projectId,
      mr_iid: mrIid,
      parent_comment: parentComment,
      provider,
    }, { timeout: 0 });
    return response.data;
  }

  // ==================== AI Summary ====================

  /**
   * 流式总结 MR 的所有 diff 改动
   * @param projectId 项目 ID
   * @param mrIid MR IID
   * @param onChunk 每次接收到数据时的回调
   * @param provider AI 提供商
   */
  async summarizeChanges(
    projectId: string,
    mrIid: number,
    onChunk: (chunk: string) => void,
    provider: string = 'openai'
  ): Promise<void> {
    const response = await fetch(`/api/ai/summarize?project_id=${projectId}&mr_iid=${mrIid}&provider=${provider}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.token}`,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '请求失败' }));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('无法读取响应流');
    }

    const decoder = new TextDecoder();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        onChunk(chunk);
      }
    } finally {
      reader.releaseLock();
    }
  }
}

// 单例实例
console.log('[api module] Creating APIClient singleton...');
export const api = new APIClient();
console.log('[api module] APIClient singleton created, token:', api.getToken() ? 'exists' : 'null');
