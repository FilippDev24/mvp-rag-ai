import { create } from 'zustand';
import { DocumentChunk, ChunkWithOverlap } from '../types';
import { apiClient } from '../services/api';

interface ChunkStore {
  chunks: ChunkWithOverlap[];
  loading: boolean;
  error: string | null;
  currentPage: number;
  totalPages: number;
  total: number;
  documentId: string | null;
  
  // Actions
  fetchChunks: (documentId: string, page?: number) => Promise<void>;
  updateChunk: (chunkId: string, content: string, metadata?: any) => Promise<void>;
  deleteChunk: (chunkId: string) => Promise<void>;
  setPage: (page: number) => void;
  clearChunks: () => void;
}

// Функция для вычисления overlap между чанками
const calculateOverlaps = (chunks: DocumentChunk[]): ChunkWithOverlap[] => {
  const OVERLAP_THRESHOLD = 50; // Минимальное количество символов для определения overlap
  
  return chunks.map((chunk, index) => {
    const chunkWithOverlap: ChunkWithOverlap = {
      ...chunk,
      hasOverlapWithNext: false,
      hasOverlapWithPrev: false,
    };

    // Проверяем overlap с предыдущим чанком
    if (index > 0) {
      const prevChunk = chunks[index - 1];
      const currentStart = chunk.content.substring(0, OVERLAP_THRESHOLD);
      const prevEnd = prevChunk.content.substring(prevChunk.content.length - OVERLAP_THRESHOLD);
      
      // Простая проверка на общие слова
      const currentWords = currentStart.toLowerCase().split(/\s+/);
      const prevWords = prevEnd.toLowerCase().split(/\s+/);
      const commonWords = currentWords.filter(word => 
        word.length > 3 && prevWords.includes(word)
      );
      
      if (commonWords.length > 2) {
        chunkWithOverlap.hasOverlapWithPrev = true;
        chunkWithOverlap.overlapStart = 0;
        chunkWithOverlap.overlapEnd = Math.min(currentStart.length, OVERLAP_THRESHOLD);
      }
    }

    // Проверяем overlap со следующим чанком
    if (index < chunks.length - 1) {
      const nextChunk = chunks[index + 1];
      const currentEnd = chunk.content.substring(chunk.content.length - OVERLAP_THRESHOLD);
      const nextStart = nextChunk.content.substring(0, OVERLAP_THRESHOLD);
      
      const currentWords = currentEnd.toLowerCase().split(/\s+/);
      const nextWords = nextStart.toLowerCase().split(/\s+/);
      const commonWords = currentWords.filter(word => 
        word.length > 3 && nextWords.includes(word)
      );
      
      if (commonWords.length > 2) {
        chunkWithOverlap.hasOverlapWithNext = true;
      }
    }

    return chunkWithOverlap;
  });
};

export const useChunkStore = create<ChunkStore>((set, get) => ({
  chunks: [],
  loading: false,
  error: null,
  currentPage: 1,
  totalPages: 0,
  total: 0,
  documentId: null,

  fetchChunks: async (documentId: string, page: number = 1) => {
    set({ loading: true, error: null });
    
    try {
      const result = await apiClient.getDocumentChunks(documentId, page, 50);
      const chunksWithOverlap = calculateOverlaps(result.chunks);
      
      set({
        chunks: chunksWithOverlap,
        currentPage: page,
        totalPages: result.totalPages,
        total: result.total,
        documentId,
        loading: false,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch chunks';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  updateChunk: async (chunkId: string, content: string, metadata?: any) => {
    const { documentId } = get();
    if (!documentId) {
      throw new Error('No document selected');
    }

    set({ loading: true, error: null });
    
    try {
      const updatedChunk = await apiClient.updateChunk(documentId, chunkId, content, metadata);
      
      set(state => ({
        chunks: state.chunks.map(chunk => 
          chunk.id === chunkId 
            ? { ...chunk, content: updatedChunk.content, metadata: updatedChunk.metadata }
            : chunk
        ),
        loading: false,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update chunk';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  deleteChunk: async (chunkId: string) => {
    const { documentId, currentPage } = get();
    if (!documentId) {
      throw new Error('No document selected');
    }

    set({ loading: true, error: null });
    
    try {
      await apiClient.deleteChunk(documentId, chunkId);
      
      // Удаляем чанк из локального состояния
      set(state => ({
        chunks: state.chunks.filter(chunk => chunk.id !== chunkId),
        total: state.total - 1,
        loading: false,
      }));

      // Если на текущей странице не осталось чанков, переходим на предыдущую
      const { chunks, totalPages } = get();
      if (chunks.length === 0 && currentPage > 1) {
        await get().fetchChunks(documentId, currentPage - 1);
      } else if (chunks.length === 0 && totalPages > 0) {
        // Если это была последняя страница, обновляем данные
        await get().fetchChunks(documentId, 1);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete chunk';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  setPage: (page: number) => {
    const state = get();
    if (state.documentId) {
      state.fetchChunks(state.documentId, page);
    }
  },

  clearChunks: () => {
    set({
      chunks: [],
      currentPage: 1,
      totalPages: 0,
      total: 0,
      documentId: null,
      error: null,
      loading: false,
    });
  },
}));
