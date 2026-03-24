import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import toast from 'react-hot-toast'

import { fetchAnalytics, fetchEmails } from '../services/api'
import { useAuth } from './AuthContext'

const DataContext = createContext(null)

const normalizeIntent = (value) => (value || '').trim()

export function DataProvider({ children }) {
  const { profile, isAdmin } = useAuth()
  const [emails, setEmails] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [loadingEmails, setLoadingEmails] = useState(false)

  const visibleEmails = useMemo(() => {
    if (isAdmin) {
      return emails
    }

    const assigned = new Set((profile.assignedIntents || []).map(normalizeIntent))
    return emails.filter((item) => assigned.has(normalizeIntent(item.intent)))
  }, [emails, isAdmin, profile.assignedIntents])

  const refreshEmails = useCallback(async () => {
    setLoadingEmails(true)
    try {
      const data = await fetchEmails({ intents: isAdmin ? [] : profile.assignedIntents || [] })
      setEmails(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error('Unable to load emails from API')
    } finally {
      setLoadingEmails(false)
    }
  }, [isAdmin, profile.assignedIntents])

  const refreshAnalytics = useCallback(async () => {
    try {
      const data = await fetchAnalytics()
      setAnalytics(data)
    } catch (error) {
      setAnalytics(null)
    }
  }, [])

  const value = useMemo(
    () => ({
      emails,
      visibleEmails,
      analytics,
      loadingEmails,
      refreshEmails,
      refreshAnalytics,
    }),
    [emails, visibleEmails, analytics, loadingEmails, refreshEmails, refreshAnalytics],
  )

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>
}

export const useData = () => {
  const context = useContext(DataContext)
  if (!context) {
    throw new Error('useData must be used inside DataProvider')
  }
  return context
}
