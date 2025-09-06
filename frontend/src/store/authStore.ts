import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthStore, User } from '../types';
import { apiClient } from '../services/api';

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (email: string, password: string) => {
        try {
          const response = await apiClient.login({ email, password });
          
          set({
            user: response.user,
            token: response.token,
            isAuthenticated: true,
          });
        } catch (error) {
          console.error('Login error:', error);
          throw error;
        }
      },

      logout: () => {
        try {
          // Вызываем API logout (может быть асинхронным, но не ждем)
          apiClient.logout().catch(console.error);
        } catch (error) {
          console.error('Logout error:', error);
        } finally {
          // Очищаем состояние - persist автоматически обновит localStorage
          set({
            user: null,
            token: null,
            isAuthenticated: false,
          });
        }
      },

      setUser: (user: User) => {
        set({ user });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
