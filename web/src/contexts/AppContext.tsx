/**
 * 应用全局状态管理
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { Project, MergeRequest, DiffFile, Note, ReviewComment } from '../types';
import { api } from '../api/client';

interface AppContextType {
  // GitLab 连接状态
  isConnected: boolean;
  currentUser: { id: number; name: string; username: string; avatar_url?: string } | null;
  connectGitLab: (url: string, token: string) => Promise<void>;

  // 当前项目
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

  // 评论
  notes: Note[];
  setNotes: (notes: Note[]) => void;

  // AI 评论
  aiComments: ReviewComment[];
  setAiComments: (comments: ReviewComment[]) => void;

  // 加载状态
  loading: boolean;
  setLoading: (loading: boolean) => void;

  // 错误消息
  error: string | null;
  setError: (error: string | null) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [currentUser, setCurrentUser] = useState<AppContextType['currentUser']>(null);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [mergeRequests, setMergeRequests] = useState<MergeRequest[]>([]);
  const [currentMR, setCurrentMR] = useState<MergeRequest | null>(null);
  const [diffFiles, setDiffFiles] = useState<DiffFile[]>([]);
  const [currentDiffFile, setCurrentDiffFile] = useState<DiffFile | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [aiComments, setAiComments] = useState<ReviewComment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const value: AppContextType = {
    isConnected,
    currentUser,
    connectGitLab,
    currentProject,
    setCurrentProject,
    mergeRequests,
    setMergeRequests,
    currentMR,
    setCurrentMR,
    diffFiles,
    setDiffFiles,
    currentDiffFile,
    setCurrentDiffFile,
    notes,
    setNotes,
    aiComments,
    setAiComments,
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
