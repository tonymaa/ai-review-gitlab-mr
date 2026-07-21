/**
 * What's New 相关 localStorage 工具函数
 */

const STORAGE_KEY = 'last_seen_release_id'

export const getLastSeenReleaseId = (): number | null => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return null
    const n = Number.parseInt(stored, 10)
    return Number.isNaN(n) ? null : n
  } catch {
    return null
  }
}

export const markReleaseSeen = (id: number): void => {
  try {
    localStorage.setItem(STORAGE_KEY, String(id))
  } catch {
    // ignore
  }
}
