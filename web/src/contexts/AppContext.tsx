/**
 * 应用全局状态管理
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { ReactNode, Dispatch, SetStateAction } from 'react';
import type { Project, MergeRequest, DiffFile, Note, ReviewComment, User } from '../types';
import { api } from '../api/client';

// LocalStorage key
const PROJECTS_STORAGE_KEY = 'gitlab-ai-review-projects';

interface AppContextType {
  // 用户认证
  isAuthenticated: boolean;
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;

  // GitLab 连接状态
  isConnected: boolean;
  currentUser: { id: number; name: string; username: string; avatar_url?: string } | null;
  connectGitLab: (url: string, token: string) => Promise<void>;

  // 项目列表和当前项目
  projects: Project[];
  addProject: (project: Project) => void;
  removeProject: (projectId: number) => void;
  currentProject: Project | null;
  setCurrentProject: (project: Project | null) => void;

  // MR 列表和当前 MR
  mergeRequests: MergeRequest[];
  setMergeRequests: (mrs: MergeRequest[]) => void;
  currentMR: MergeRequest | null;
  setCurrentMR: (mr: MergeRequest | null) => void;

  // Diff 文件和当前文件
  diffFiles: DiffFile[];
  setDiffFiles: (files: DiffFile[]) => void;
  currentDiffFile: DiffFile | null;
  setCurrentDiffFile: (file: DiffFile | null) => void;

  // 高亮行跳转
  highlightLine: { filePath: string; lineNumber: number } | null;
  setHighlightLine: (highlight: { filePath: string; lineNumber: number } | null) => void;
  jumpToLine: (filePath: string, lineNumber: number) => void;

  // 评论
  notes: Note[];
  setNotes: (notes: Note[]) => void;

  // AI 评论
  aiComments: ReviewComment[];
  setAiComments: Dispatch<SetStateAction<ReviewComment[]>>;

  // AI 审查状态
  isReviewingAllFiles: boolean;
  setIsReviewingAllFiles: (reviewing: boolean) => void;
  isReviewingSingleFile: boolean;
  setIsReviewingSingleFile: (reviewing: boolean) => void;

  // 加载状态
  loading: boolean;
  setLoading: (loading: boolean) => void;

  // 错误消息
  error: string | null;
  setError: (error: string | null) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // 用户认证状态
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [currentUser, setCurrentUser] = useState<AppContextType['currentUser']>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [mergeRequests, setMergeRequests] = useState<MergeRequest[]>([]);
  const [currentMR, setCurrentMR] = useState<MergeRequest | null>(null);
  const [diffFiles, setDiffFiles] = useState<DiffFile[]>([]);
  const [currentDiffFile, setCurrentDiffFile] = useState<DiffFile | null>(null);
  const [highlightLine, setHighlightLine] = useState<{ filePath: string; lineNumber: number } | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [aiComments, setAiComments] = useState<ReviewComment[]>([]);
  const [isReviewingAllFiles, setIsReviewingAllFiles] = useState(false);
  const [isReviewingSingleFile, setIsReviewingSingleFile] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 标记是否已从 localStorage 加载
  const [loadedFromStorage, setLoadedFromStorage] = useState(false);

  // 从 localStorage 加载项目列表
  useEffect(() => {
    try {
      const stored = localStorage.getItem(PROJECTS_STORAGE_KEY);
      if (stored) {
        const parsedProjects = JSON.parse(stored) as Project[];
        setProjects(parsedProjects);
      }
      setLoadedFromStorage(true);
    } catch (err) {
      console.error('Failed to load projects from localStorage:', err);
      setLoadedFromStorage(true);
    }
  }, []);

  // 当 projects 变化时保存到 localStorage (仅在加载完成后)
  useEffect(() => {
    if (loadedFromStorage) {
      try {
        localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects));
      } catch (err) {
        console.error('Failed to save projects to localStorage:', err);
      }
    }
  }, [projects, loadedFromStorage]);

  // 检查用户登录状态
  useEffect(() => {
    checkAuth();
  }, []);

  // 登录
  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.login(username, password);
      setIsAuthenticated(true);
      setUser(result.user);
      console.log('[login] Login successful, user:', result.user);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '登录失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 注册
  const register = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.register(username, password);
      setIsAuthenticated(true);
      setUser(result.user);
      console.log('[register] Register successful, user:', result.user);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '注册失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 登出
  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setIsAuthenticated(false);
      setUser(null);
      // 清除其他状态
      setIsConnected(false);
      setCurrentUser(null);
      setCurrentProject(null);
      setCurrentMR(null);
      setDiffFiles([]);
      setCurrentDiffFile(null);
    }
  }, []);

  // 检查认证状态
  const checkAuth = useCallback(async () => {
    const token = api.getToken();
    console.log('[checkAuth] Token from api.getToken():', token ? 'exists' : 'null');
    if (!token) {
      setIsAuthenticated(false);
      setUser(null);
      return;
    }

    try {
      console.log('[checkAuth] Calling getCurrentUser...');
      const result = await api.getCurrentUser();
      console.log('[checkAuth] getCurrentUser success:', result);
      setIsAuthenticated(true);
      setUser(result);
    } catch (err) {
      console.error('[checkAuth] Check auth failed:', err);
      // Token 可能已过期，清除它
      api.clearToken();
      setIsAuthenticated(false);
      setUser(null);
    }
  }, []);

  const connectGitLab = useCallback(async (url: string, token: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.connectGitLab(url, token);
      setIsConnected(true);
      setCurrentUser(result.user);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '连接失败');
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 添加项目到列表
  const addProject = useCallback((project: Project) => {
    setProjects(prev => {
      // 检查是否已存在
      const exists = prev.some(p => p.id === project.id);
      if (exists) {
        return prev;
      }
      return [...prev, project];
    });
  }, []);

  // 从列表中移除项目
  const removeProject = useCallback((projectId: number) => {
    setProjects(prev => prev.filter(p => p.id !== projectId));
    // 如果移除的是当前项目，清除当前项目
    setCurrentProject(prev => prev?.id === projectId ? null : prev);
  }, []);

  // 设置当前项目
  const handleSetCurrentProject = useCallback((project: Project | null) => {
    setCurrentProject(project);
    // 清除 MR 和 diff 相关数据
    setCurrentMR(null);
    setDiffFiles([]);
    setCurrentDiffFile(null);
    setHighlightLine(null);
  }, []);

  // 跳转到指定文件的指定行
  const jumpToLine = useCallback((filePath: string, lineNumber: number) => {
    // 查找对应的文件
    const targetFile = diffFiles.find(f => f.new_path === filePath || f.old_path === filePath);
    if (targetFile) {
      // 切换到该文件
      setCurrentDiffFile(targetFile);
      // 设置高亮行
      setHighlightLine({ filePath, lineNumber });
    }
  }, [diffFiles, setCurrentDiffFile, setHighlightLine]);

  const value: AppContextType = {
    // 用户认证
    isAuthenticated,
    user,
    login,
    register,
    logout,
    checkAuth,
    // GitLab 连接
    isConnected,
    currentUser,
    connectGitLab,
    // 项目
    projects,
    addProject,
    removeProject,
    currentProject,
    setCurrentProject: handleSetCurrentProject,
    // MR
    mergeRequests,
    setMergeRequests,
    currentMR,
    setCurrentMR,
    // Diff
    diffFiles,
    setDiffFiles,
    currentDiffFile,
    setCurrentDiffFile,
    // 高亮行跳转
    highlightLine,
    setHighlightLine,
    jumpToLine,
    // 评论
    notes,
    setNotes,
    aiComments,
    setAiComments,
    // AI 审查状态
    isReviewingAllFiles,
    setIsReviewingAllFiles,
    isReviewingSingleFile,
    setIsReviewingSingleFile,
    // 加载状态和错误
    loading,
    setLoading,
    error,
    setError,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
