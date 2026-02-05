/**
 * 应用全局状态管理
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { ReactNode, Dispatch, SetStateAction } from 'react';
import type { Project, MergeRequest, DiffFile, Note, ReviewComment, User } from '../types';
import { api } from '../api/client';

// LocalStorage keys
const PROJECTS_STORAGE_KEY = 'gitlab-ai-review-projects';
const THEME_STORAGE_KEY = 'gitlab-ai-review-theme';

// 主题类型
export type Theme = 'light' | 'dark';

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

  // 应用配置
  allowRegistration: boolean;
  setAllowRegistration: (allowed: boolean) => void;

  // 主题
  theme: Theme;
  toggleTheme: () => void;

  // 加载状态
  loading: boolean;
  setLoading: (loading: boolean) => void;

  // 错误消息
  error: string | null;
  setError: (error: string | null) => void;

  // MR 列表筛选状态
  mrListFilterRelated: boolean;
  setMrListFilterRelated: (value: boolean) => void;
  mrListFilterState: 'opened' | 'closed' | 'merged' | 'all';
  setMrListFilterState: (value: 'opened' | 'closed' | 'merged' | 'all') => void;
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
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      return (stored === 'light' || stored === 'dark') ? stored : 'dark';
    } catch {
      return 'dark';
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allowRegistration, setAllowRegistration] = useState(true);

  // MR 列表筛选状态
  const [mrListFilterRelated, setMrListFilterRelated] = useState(false);
  const [mrListFilterState, setMrListFilterState] = useState<'opened' | 'closed' | 'merged' | 'all'>('opened');

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
    console.log('[AppContext] logout called');
    try {
      const result = await api.logout();
      console.log('[AppContext] logout API result:', result);
    } catch (err) {
      console.error('[AppContext] Logout error:', err);
    } finally {
      console.log('[AppContext] Clearing app state');
      setIsAuthenticated(false);
      setUser(null);
      // 清除其他状态
      setIsConnected(false);
      setCurrentUser(null);
      setCurrentProject(null);
      setCurrentMR(null);
      setDiffFiles([]);
      setCurrentDiffFile(null);
      console.log('[AppContext] App state cleared');
    }
  }, []);

  // 检查认证状态
  const checkAuth = useCallback(async () => {
    console.log('[checkAuth] Starting auth check...');
    const token = api.getToken();
    console.log('[checkAuth] Token from api.getToken():', token ? `exists (${token.length} chars)` : 'null');
    console.log('[checkAuth] localStorage token:', localStorage.getItem('gitlab-ai-review-token') ? 'exists in localStorage' : 'null in localStorage');
    if (!token) {
      console.log('[checkAuth] No token found, setting authenticated to false');
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
      console.log('[checkAuth] Token invalid, clearing token');
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

  // 切换主题
  const toggleTheme = useCallback(() => {
    setTheme(prev => {
      const newTheme = prev === 'dark' ? 'light' : 'dark';
      // 保存到 localStorage
      try {
        localStorage.setItem(THEME_STORAGE_KEY, newTheme);
      } catch (err) {
        console.error('Failed to save theme to localStorage:', err);
      }
      // 应用主题到 document
      if (newTheme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      return newTheme;
    });
  }, []);

  // 初始化主题
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);

  // 加载应用配置（包括 allowRegistration）
  useEffect(() => {
    const loadAppConfig = async () => {
      if (!isAuthenticated) return;
      try {
        const config = await api.getConfig();
        if (config.allow_registration !== undefined) {
          setAllowRegistration(config.allow_registration);
        }
      } catch (err) {
        console.error('Failed to load app config:', err);
      }
    };
    loadAppConfig();
  }, [isAuthenticated]);

  // 设置当前项目
  const handleSetCurrentProject = useCallback((project: Project | null) => {
    setCurrentProject(project);
    // 清除 MR 和 diff 相关数据
    setCurrentMR(null);
    setDiffFiles([]);
    setCurrentDiffFile(null);
    setHighlightLine(null);
    setNotes([])
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
    // 应用配置
    allowRegistration,
    setAllowRegistration,
    // 主题
    theme,
    toggleTheme,
    // 加载状态和错误
    loading,
    setLoading,
    error,
    setError,

    // MR 列表筛选状态
    mrListFilterRelated,
    setMrListFilterRelated,
    mrListFilterState,
    setMrListFilterState,
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
