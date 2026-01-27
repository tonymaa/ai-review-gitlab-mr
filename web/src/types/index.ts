/**
 * API 响应类型定义
 */

/** GitLab 配置 */
export interface GitLabConfig {
  url: string;
  token: string;
  default_project_id?: string;
}

/** AI 配置 */
export interface AIConfig {
  provider: 'openai' | 'ollama';
  openai_api_key: string;
  openai_base_url?: string;
  openai_model: string;
  openai_temperature: number;
  openai_max_tokens: number;
  ollama_base_url: string;
  ollama_model: string;
  review_rules: string[];
}

/** 应用配置 */
export interface AppConfig {
  gitlab: GitLabConfig;
  ai: AIConfig;
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
  approved_by_current_user: boolean;
  assignees: Array<{ id: number; name: string; avatar_url?: string }>;
  reviewers: Array<{ id: number; name: string; avatar_url?: string }>;
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

/** 评论请求 */
export interface CommentRequest {
  body: string;
  file_path?: string;
  line_number?: number;
  line_type?: 'new' | 'old';
}
