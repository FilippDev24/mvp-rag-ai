import React, { useState } from 'react';
import './CalendarDebug.css';

interface CalendarDebugInfo {
  originalMessage: string;
  parsedCommand: {
    participants: string[];
    datetime: string;
    title: string;
    duration: number;
  };
  participantSearchResults: ParticipantSearchDebug[];
  calendarCreation?: {
    startTime: string;
    endTime: string;
    attendees: string[];
    organizerEmail: string;
  };
  processingSteps: ProcessingStep[];
}

interface ParticipantSearchDebug {
  searchedFor: string;
  ragResults: {
    resultsCount: number;
    contentPreview: string;
    searchQuery: string;
    taskId: string;
  };
  llmExtraction: {
    prompt: string;
    rawResponse: string;
    parsedResult: any;
    success: boolean;
  };
  finalResult: EmployeeInfo | null;
  processingTime: number;
}

interface ProcessingStep {
  step: string;
  timestamp: string;
  duration: number;
  success: boolean;
  details: any;
  error?: string;
}

interface EmployeeInfo {
  name: string;
  email: string;
  department?: string;
  position?: string;
}

interface CalendarDebugProps {
  debug: CalendarDebugInfo;
  onClose: () => void;
}

export const CalendarDebug: React.FC<CalendarDebugProps> = ({ debug, onClose }) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [expandedParticipants, setExpandedParticipants] = useState<Set<number>>(new Set());

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(section)) {
      newExpanded.delete(section);
    } else {
      newExpanded.add(section);
    }
    setExpandedSections(newExpanded);
  };

  const toggleParticipant = (index: number) => {
    const newExpanded = new Set(expandedParticipants);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedParticipants(newExpanded);
  };

  const formatDateTime = (dateTimeStr: string) => {
    try {
      return new Date(dateTimeStr).toLocaleString('ru-RU', {
        timeZone: 'Europe/Moscow',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateTimeStr;
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}мс`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}с`;
    return `${(ms / 60000).toFixed(1)}мин`;
  };

  const getStepIcon = (step: ProcessingStep) => {
    if (step.success) return '✅';
    if (step.error) return '❌';
    return '⏳';
  };

  const getParticipantIcon = (result: ParticipantSearchDebug) => {
    if (result.finalResult) return '✅';
    if (result.ragResults.resultsCount === 0) return '🔍';
    if (!result.llmExtraction.success) return '🤖❌';
    return '❌';
  };

  return (
    <div className="calendar-debug-overlay">
      <div className="calendar-debug-panel">
        <div className="calendar-debug-header">
          <h2>🔍 Отладка календарного запроса</h2>
          <button className="close-button" onClick={onClose}>✕</button>
        </div>

        <div className="calendar-debug-content">
          {/* Исходный запрос */}
          <div className="debug-section">
            <h3>📝 Исходный запрос</h3>
            <div className="debug-card">
              <code className="original-message">{debug.originalMessage}</code>
            </div>
          </div>

          {/* Извлеченные параметры */}
          <div className="debug-section">
            <h3>⚙️ Извлеченные параметры</h3>
            <div className="debug-card">
              <div className="param-grid">
                <div className="param-item">
                  <strong>Участники:</strong>
                  <span className="param-value">
                    {debug.parsedCommand.participants.length > 0 
                      ? debug.parsedCommand.participants.join(', ')
                      : 'Не указаны'
                    }
                  </span>
                </div>
                <div className="param-item">
                  <strong>Время:</strong>
                  <span className="param-value">
                    {formatDateTime(debug.parsedCommand.datetime)}
                  </span>
                </div>
                <div className="param-item">
                  <strong>Тема:</strong>
                  <span className="param-value">{debug.parsedCommand.title}</span>
                </div>
                <div className="param-item">
                  <strong>Длительность:</strong>
                  <span className="param-value">{debug.parsedCommand.duration} мин</span>
                </div>
              </div>
            </div>
          </div>

          {/* Поиск участников */}
          <div className="debug-section">
            <h3>👥 Поиск участников ({debug.participantSearchResults.length})</h3>
            {debug.participantSearchResults.map((result, index) => (
              <div key={index} className="participant-debug-card">
                <div 
                  className="participant-header"
                  onClick={() => toggleParticipant(index)}
                >
                  <span className="participant-icon">{getParticipantIcon(result)}</span>
                  <span className="participant-name">"{result.searchedFor}"</span>
                  <span className="participant-time">({formatDuration(result.processingTime)})</span>
                  <span className="expand-icon">
                    {expandedParticipants.has(index) ? '▼' : '▶'}
                  </span>
                </div>

                {result.finalResult && (
                  <div className="participant-result">
                    <strong>Найден:</strong> {result.finalResult.name} ({result.finalResult.email})
                    {result.finalResult.department && (
                      <span className="department"> - {result.finalResult.department}</span>
                    )}
                  </div>
                )}

                {expandedParticipants.has(index) && (
                  <div className="participant-details">
                    {/* RAG результаты */}
                    <div className="detail-section">
                      <h4>🔍 RAG поиск</h4>
                      <div className="detail-content">
                        <p><strong>Запрос:</strong> {result.ragResults.searchQuery}</p>
                        <p><strong>Найдено результатов:</strong> {result.ragResults.resultsCount}</p>
                        <p><strong>Task ID:</strong> <code>{result.ragResults.taskId}</code></p>
                        
                        {result.ragResults.contentPreview && (
                          <details className="content-preview">
                            <summary>Контекст из RAG ({result.ragResults.contentPreview.length} символов)</summary>
                            <pre className="rag-content">{result.ragResults.contentPreview}</pre>
                          </details>
                        )}
                      </div>
                    </div>

                    {/* LLM извлечение */}
                    <div className="detail-section">
                      <h4>🤖 LLM извлечение {result.llmExtraction.success ? '✅' : '❌'}</h4>
                      <div className="detail-content">
                        <details className="llm-prompt">
                          <summary>Промпт для LLM</summary>
                          <pre className="llm-text">{result.llmExtraction.prompt}</pre>
                        </details>
                        
                        <details className="llm-response">
                          <summary>Ответ LLM</summary>
                          <pre className="llm-text">{result.llmExtraction.rawResponse}</pre>
                        </details>
                        
                        {result.llmExtraction.parsedResult && (
                          <details className="llm-parsed">
                            <summary>Распарсенный результат</summary>
                            <pre className="json-content">
                              {JSON.stringify(result.llmExtraction.parsedResult, null, 2)}
                            </pre>
                          </details>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Создание встречи */}
          {debug.calendarCreation && (
            <div className="debug-section">
              <h3>📅 Создание встречи</h3>
              <div className="debug-card">
                <div className="param-grid">
                  <div className="param-item">
                    <strong>Начало:</strong>
                    <span className="param-value">
                      {formatDateTime(debug.calendarCreation.startTime)}
                    </span>
                  </div>
                  <div className="param-item">
                    <strong>Конец:</strong>
                    <span className="param-value">
                      {formatDateTime(debug.calendarCreation.endTime)}
                    </span>
                  </div>
                  <div className="param-item">
                    <strong>Организатор:</strong>
                    <span className="param-value">{debug.calendarCreation.organizerEmail}</span>
                  </div>
                  <div className="param-item">
                    <strong>Участники:</strong>
                    <span className="param-value">
                      {debug.calendarCreation.attendees.join(', ')}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Шаги обработки */}
          <div className="debug-section">
            <h3 
              className="collapsible-header"
              onClick={() => toggleSection('steps')}
            >
              ⚡ Шаги обработки ({debug.processingSteps.length})
              <span className="expand-icon">
                {expandedSections.has('steps') ? '▼' : '▶'}
              </span>
            </h3>
            
            {expandedSections.has('steps') && (
              <div className="steps-timeline">
                {debug.processingSteps.map((step, index) => (
                  <div key={index} className={`step-item ${step.success ? 'success' : 'error'}`}>
                    <div className="step-header">
                      <span className="step-icon">{getStepIcon(step)}</span>
                      <span className="step-name">{step.step}</span>
                      <span className="step-duration">({formatDuration(step.duration)})</span>
                    </div>
                    
                    {step.error && (
                      <div className="step-error">
                        <strong>Ошибка:</strong> {step.error}
                      </div>
                    )}
                    
                    {step.details && Object.keys(step.details).length > 0 && (
                      <details className="step-details">
                        <summary>Детали</summary>
                        <pre className="json-content">
                          {JSON.stringify(step.details, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
