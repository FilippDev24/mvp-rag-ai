import { create } from 'zustand';
import { DocumentStore, Document } from '../types';
import { apiClient } from '../services/api';

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  documents: [],
  loading: false,
  error: null,

  fetchDocuments: async () => {
    set({ loading: true, error: null });
    try {
      const documents = await apiClient.getDocuments();
      set({ documents, loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch documents';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  uploadDocument: async (file: File, title: string, accessLevel: number) => {
    set({ loading: true, error: null });
    try {
      const document = await apiClient.uploadDocument(file, { title, accessLevel });
      const currentDocuments = get().documents;
      set({ 
        documents: [document, ...currentDocuments], 
        loading: false 
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to upload document';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  deleteDocument: async (id: string) => {
    set({ loading: true, error: null });
    try {
      await apiClient.deleteDocument(id);
      const currentDocuments = get().documents;
      set({ 
        documents: currentDocuments.filter(doc => doc.id !== id), 
        loading: false 
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete document';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },
}));
