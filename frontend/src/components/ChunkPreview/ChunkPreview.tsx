import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useChunkStore } from '../../store/chunkStore';
import { useDocumentStore } from '../../store/documentStore';
import { ChunkWithOverlap } from '../../types';
import './ChunkPreview.css';

interface ChunkEditModalProps {
  chunk: ChunkWithOverlap;
  isOpen: boolean;
  onClose: () => void;
  onSave: (content: string, metadata?: any) => Promise<void>;
}

const ChunkEditModal: React.FC<ChunkEditModalProps> = ({ chunk, isOpen, onClose, onSave }) => {
  const [content, setContent] = useState(chunk.content);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setContent(chunk.content);
  }, [chunk.content]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(content);
      onClose();
    } catch (error) {
      console.error('Failed to save chunk:', error);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="chunk-edit-modal-overlay">
      <div className="chunk-edit-modal">
        <div className="chunk-edit-modal-header">
          <h3>Редактировать чанк #{chunk.chunkIndex + 1}</h3>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        
        <div className="chunk-edit-modal-body">
          <div className="chunk-info">
            <span className="chunk-info-item">Символов: {content.length}</span>
            <span className="chunk-info-item">Уровень доступа: {chunk.accessLevel}</span>
          </div>
          
          <textarea
            className="chunk-content-editor"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Содержимое чанка..."
            rows={15}
          />
        </div>
        
        <div className="chunk-edit-modal-footer">
          <button className="cancel-button" onClick={onClose} disabled={saving}>
            Отмена
          </button>
          <button 
            className="save-button" 
            onClick={handleSave} 
            disabled={saving || content.trim() === ''}
          >
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  );
};

interface ChunkRowProps {
  chunk: ChunkWithOverlap;
  onEdit: (chunk: ChunkWithOverlap) => void;
  onDelete: (chunkId: string) => void;
  deleting: boolean;
}

const ChunkRow: React.FC<ChunkRowProps> = ({ chunk, onEdit, onDelete, deleting }) => {
  const [showFullContent, setShowFullContent] = useState(false);
  
  const truncatedContent = chunk.content.length > 200 
    ? chunk.content.substring(0, 200) + '...'
    : chunk.content;

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  return (
    <tr className={`chunk-row ${chunk.hasOverlapWithPrev ? 'has-overlap-prev' : ''} ${chunk.hasOverlapWithNext ? 'has-overlap-next' : ''}`}>
      <td className="chunk-index">
        <div className="chunk-index-container">
          <span className="chunk-number">#{chunk.chunkIndex + 1}</span>
          {chunk.hasOverlapWithPrev && (
            <div className="overlap-indicator overlap-prev" title="Есть пересечение с предыдущим чанком">
              ↑
            </div>
          )}
          {chunk.hasOverlapWithNext && (
            <div className="overlap-indicator overlap-next" title="Есть пересечение со следующим чанком">
              ↓
            </div>
          )}
        </div>
      </td>
      
      <td className="chunk-content">
        <div className="content-container">
          <div className="content-text">
            {showFullContent ? chunk.content : truncatedContent}
          </div>
          {chunk.content.length > 200 && (
            <button 
              className="toggle-content-button"
              onClick={() => setShowFullContent(!showFullContent)}
            >
              {showFullContent ? 'Свернуть' : 'Показать полностью'}
            </button>
          )}
          {chunk.hasOverlapWithPrev && chunk.overlapStart !== undefined && chunk.overlapEnd !== undefined && (
            <div className="overlap-highlight">
              Пересечение: {chunk.content.substring(chunk.overlapStart, chunk.overlapEnd)}
            </div>
          )}
        </div>
      </td>
      
      <td className="chunk-stats">
        <div className="stat-item">
          <span className="stat-label">Символов:</span>
          <span className="stat-value">{chunk.charCount}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Доступ:</span>
          <span className="stat-value">{chunk.accessLevel}</span>
        </div>
        {chunk.keywords && (
          <div className="keywords-section">
            {chunk.keywords.semantic_keywords.length > 0 && (
              <div className="keywords-group">
                <span className="keywords-label">Семантические:</span>
                <div className="keywords-list">
                  {chunk.keywords.semantic_keywords.slice(0, 3).map((keyword, idx) => (
                    <span key={idx} className="keyword semantic">{keyword}</span>
                  ))}
                  {chunk.keywords.semantic_keywords.length > 3 && (
                    <span className="keyword-more">+{chunk.keywords.semantic_keywords.length - 3}</span>
                  )}
                </div>
              </div>
            )}
            {chunk.keywords.technical_keywords.length > 0 && (
              <div className="keywords-group">
                <span className="keywords-label">Технические:</span>
                <div className="keywords-list">
                  {chunk.keywords.technical_keywords.slice(0, 3).map((keyword, idx) => (
                    <span key={idx} className="keyword technical">{keyword}</span>
                  ))}
                  {chunk.keywords.technical_keywords.length > 3 && (
                    <span className="keyword-more">+{chunk.keywords.technical_keywords.length - 3}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </td>
      
      <td className="chunk-date">
        {formatDate(chunk.createdAt)}
      </td>
      
      <td className="chunk-actions">
        <button 
          className="edit-button"
          onClick={() => onEdit(chunk)}
          title="Редактировать чанк"
        >
          ✏️
        </button>
        <button 
          className="delete-button"
          onClick={() => onDelete(chunk.id)}
          disabled={deleting}
          title="Удалить чанк"
        >
          {deleting ? '⏳' : '🗑️'}
        </button>
      </td>
    </tr>
  );
};

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  loading: boolean;
}

const Pagination: React.FC<PaginationProps> = ({ currentPage, totalPages, onPageChange, loading }) => {
  if (totalPages <= 1) return null;

  const pages: number[] = [];
  const maxVisiblePages = 5;
  
  let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
  let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
  
  if (endPage - startPage + 1 < maxVisiblePages) {
    startPage = Math.max(1, endPage - maxVisiblePages + 1);
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i);
  }

  return (
    <div className="pagination">
      <button 
        className="pagination-button"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1 || loading}
      >
        ← Предыдущая
      </button>
      
      {startPage > 1 && (
        <>
          <button 
            className="pagination-button"
            onClick={() => onPageChange(1)}
            disabled={loading}
          >
            1
          </button>
          {startPage > 2 && <span className="pagination-ellipsis">...</span>}
        </>
      )}
      
      {pages.map(page => (
        <button
          key={page}
          className={`pagination-button ${page === currentPage ? 'active' : ''}`}
          onClick={() => onPageChange(page)}
          disabled={loading}
        >
          {page}
        </button>
      ))}
      
      {endPage < totalPages && (
        <>
          {endPage < totalPages - 1 && <span className="pagination-ellipsis">...</span>}
          <button 
            className="pagination-button"
            onClick={() => onPageChange(totalPages)}
            disabled={loading}
          >
            {totalPages}
          </button>
        </>
      )}
      
      <button 
        className="pagination-button"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages || loading}
      >
        Следующая →
      </button>
    </div>
  );
};

export const ChunkPreview: React.FC = () => {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();
  
  const {
    chunks,
    loading,
    error,
    currentPage,
    totalPages,
    total,
    fetchChunks,
    updateChunk,
    deleteChunk,
    setPage: setStorePage,
    clearChunks
  } = useChunkStore();
  
  const { documents } = useDocumentStore();
  
  const [editingChunk, setEditingChunk] = useState<ChunkWithOverlap | null>(null);
  const [deletingChunkId, setDeletingChunkId] = useState<string | null>(null);

  const currentDocument = documents.find(doc => doc.id === documentId);

  useEffect(() => {
    if (documentId) {
      fetchChunks(documentId);
    }
    
    return () => {
      clearChunks();
    };
  }, [documentId, fetchChunks, clearChunks]);

  const handleEditChunk = (chunk: ChunkWithOverlap) => {
    setEditingChunk(chunk);
  };

  const handleSaveChunk = async (content: string, metadata?: any) => {
    if (!editingChunk) return;
    
    await updateChunk(editingChunk.id, content, metadata);
    setEditingChunk(null);
  };

  const handleDeleteChunk = async (chunkId: string) => {
    if (!confirm('Вы уверены, что хотите удалить этот чанк? Это действие нельзя отменить.')) {
      return;
    }
    
    setDeletingChunkId(chunkId);
    try {
      await deleteChunk(chunkId);
    } catch (error) {
      console.error('Failed to delete chunk:', error);
    } finally {
      setDeletingChunkId(null);
    }
  };

  const handlePageChange = (page: number) => {
    if (documentId) {
      setStorePage(page);
    }
  };

  if (!documentId) {
    return (
      <div className="chunk-preview-container">
        <div className="error-message">Документ не найден</div>
      </div>
    );
  }

  return (
    <div className="chunk-preview-container">
      <div className="chunk-preview-header">
        <button className="back-button" onClick={() => navigate('/documents')}>
          ← Назад к документам
        </button>
        
        <div className="document-info">
          <h1>Чанки документа</h1>
          {currentDocument && (
            <div className="document-details">
              <h2>{currentDocument.title}</h2>
              <div className="document-meta">
                <span>Статус: {currentDocument.status}</span>
                <span>Уровень доступа: {currentDocument.accessLevel}</span>
                <span>Всего чанков: {total}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="error-message">
          Ошибка: {error}
        </div>
      )}

      {loading && chunks.length === 0 ? (
        <div className="loading-message">
          Загрузка чанков...
        </div>
      ) : chunks.length === 0 ? (
        <div className="empty-message">
          Чанки не найдены. Возможно, документ еще обрабатывается.
        </div>
      ) : (
        <>
          <div className="chunks-stats">
            <div className="stat-card">
              <div className="stat-number">{total}</div>
              <div className="stat-label">Всего чанков</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">
                {chunks.filter(c => c.hasOverlapWithNext || c.hasOverlapWithPrev).length}
              </div>
              <div className="stat-label">С пересечениями</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">
                {Math.round(chunks.reduce((sum, c) => sum + c.charCount, 0) / chunks.length)}
              </div>
              <div className="stat-label">Средний размер</div>
            </div>
          </div>

          <div className="chunks-table-container">
            <table className="chunks-table">
              <thead>
                <tr>
                  <th>№</th>
                  <th>Содержимое</th>
                  <th>Статистика</th>
                  <th>Создан</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {chunks.map(chunk => (
                  <ChunkRow
                    key={chunk.id}
                    chunk={chunk}
                    onEdit={handleEditChunk}
                    onDelete={handleDeleteChunk}
                    deleting={deletingChunkId === chunk.id}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={handlePageChange}
            loading={loading}
          />
        </>
      )}

      {editingChunk && (
        <ChunkEditModal
          chunk={editingChunk}
          isOpen={true}
          onClose={() => setEditingChunk(null)}
          onSave={handleSaveChunk}
        />
      )}
    </div>
  );
};
