import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 15000,
})

export const setAuthToken = (token) => {
  if (!token) {
    delete apiClient.defaults.headers.common.Authorization
    return
  }
  apiClient.defaults.headers.common.Authorization = `Bearer ${token}`
}

export const fetchEmails = async ({ intents = [], limit = 500 } = {}) => {
  const params = { limit }
  if (Array.isArray(intents) && intents.length > 0) {
    params.intents = intents.join(',')
  }

  const response = await apiClient.get('/api/emails', { params })
  return response?.data?.emails || []
}

export const fetchAnalytics = async () => {
  const response = await apiClient.get('/api/analytics')
  return response?.data || {}
}

export const createTeamMember = async (payload) => {
  const response = await apiClient.post('/api/team', payload)
  return response?.data
}

export const createAdminUser = async (payload) => {
  const response = await apiClient.post('/api/create-user', payload)
  return response?.data?.user
}

export const inviteUser = async (payload) => {
  const response = await apiClient.post('/api/invite-user', payload)
  return response?.data
}

export const getUserByEmail = async (email) => {
  const response = await apiClient.get('/api/get-user', {
    params: { email },
  })
  return response?.data?.user
}

export const getInviteStatus = async (email) => {
  const response = await apiClient.get('/api/invite-status', {
    params: { email },
  })
  return response?.data
}

export const activateUser = async (payload) => {
  const response = await apiClient.post('/api/activate-user', payload)
  return response?.data?.user
}

export default apiClient
