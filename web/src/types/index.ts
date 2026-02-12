/**
 * API 响应类型定义
 */

/** 用户信息 */
export interface User {
  id: number;
  username: string;
  created_at: string;
  is_active: boolean;
}

/** 认证响应 */
export interface AuthResponse {
  status: string;
  message: string;
  user: User;
  token: string;
}

/** GitLab 配置 */
export interface GitLabConfig {
  url: string;
  token: string;
  default_project_id?: string;
}

/** OpenAI 配置 */
export interface OpenAIConfig {
  api_key: string;
  base_url?: string;
  model: string;
  temperature: number;
  max_tokens: number;
}

/** Ollama 配置 */
export interface OllamaConfig {
  base_url: string;
  model: string;
}

/** AI 配置 */
export interface AIConfig {
  provider: 'openai' | 'ollama';
  openai: OpenAIConfig;
  ollama: OllamaConfig;
  review_rules: string[];
  summary_prompt?: string;
}

/** 应用配置 */
export interface AppConfig {
  gitlab?: GitLabConfig | null;
  ai?: AIConfig | null;
  allow_registration?: boolean;
}

/** 项目信息 */
export interface Project {
  id: number;
  name: string;
  path: string;
  path_with_namespace: string;
  description?: string;
  default_branch?: string;
  web_url: string;
}

/** Merge Request 信息 */
export interface MergeRequest {
  iid: number;
  id: number;
  project_id: number;
  title: string;
  description?: string;
  source_branch: string;
  target_branch: string;
  state: 'opened' | 'closed' | 'merged';
  author_name: string;
  author_avatar?: string;
  web_url: string;
  created_at: string;
  updated_at: string;
  user_notes_count: number;
  approved_by_current_user: boolean;
  assignees: Array<{ id: number; name: string; avatar_url?: string }>;
  reviewers: Array<{ id: number; name: string; avatar_url?: string }>;
  /** 合并状态 */
  merge_status?: 'can_be_merged' | 'cannot_be_merged' | 'checking' | 'unchecked';
  /** 是否有冲突 */
  has_conflicts?: boolean;
  /** 是否可以合并 */
  can_merge?: boolean;
  approved_by?: Array<{ id: number; username: string; name: string; avatar_url?: string }>;
}

/** 相关 MR 和项目 */
export interface RelatedMR {
  mr: MergeRequest;
  project: Project | null;
}

/** Diff 文件 */
export interface DiffFile {
  old_path: string;
  new_path: string;
  new_file: boolean;
  renamed_file: boolean;
  deleted_file: boolean;
  diff: string;
  additions: number;
  deletions: number;
}

/** 评论 */
export interface Note {
  id: number;
  author_name: string;
  author_avatar?: string;
  body: string;
  created_at: string;
  system: boolean;
  type: 'note' | 'discussion';
  file_path?: string;
  line_number?: number;
}

/** 讨论中的单个笔记 */
export interface DiscussionNote {
  id: number;
  type: string;
  author: {
    id: number;
    username: string;
    name: string;
    avatar_url?: string;
  };
  created_at: string;
  updated_at: string;
  system: boolean;
  noteable_id: number;
  noteable_type: string;
  noteable_iid: number;
  body: string;
  position?: {
    base_sha: string;
    start_sha: string;
    head_sha: string;
    old_path: string;
    new_path: string;
    position_type: string;
    old_line?: number;
    new_line?: number;
  };
  resolvable: boolean;
  resolved: boolean;
}

/** 讨论（包含主评论和回复） */
export interface Discussion {
  id: string;
  created_at: string;
  updated_at: string;
  notes: DiscussionNote[];
}

/** AI 评论 */
export interface ReviewComment {
  file_path: string;
  line_number?: number;
  content: string;
  severity: 'critical' | 'warning' | 'suggestion';
}

/** AI 审查响应 */
export interface ReviewResponse {
  status: string;
  summary: string;
  overall_score: number;
  issues_count: number;
  suggestions_count: number;
  comments: ReviewComment[];
}

/** AI 审查错误响应 */
export interface ReviewErrorResponse {
  status: 'error';
  error: string;
}

/** 评论请求 */
export interface CommentRequest {
  body: string;
  file_path?: string;
  line_number?: number;
  line_type?: 'new' | 'old';
}
