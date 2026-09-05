import client from './client'
import { endpoints } from './endpoints'
import type { ApiResponse, ChatMessage, ChatSession } from '../types/api'

interface SessionsData {
  sessions: ChatSession[]
}

interface SessionMessagesData {
  messages: Pick<ChatMessage, 'id' | 'role' | 'content' | 'created_at'>[]
}

export const sessionsApi = {
  list: async () => {
    const res = await client.get<ApiResponse<SessionsData>>(endpoints.getSessions)
    return res.data
  },

  get: async (id: string) => {
    const res = await client.get<ApiResponse<SessionMessagesData>>(endpoints.getSessionMessages(id))
    return res.data
  },

  delete: async (id: string) => {
    const res = await client.delete<ApiResponse<null>>(endpoints.deleteSession(id))
    return res.data
  },
}
