import { EmployeeInfo } from '../../types/calendar';
import { logger } from '../../utils/logger';
import { createClient } from 'redis';
import axios from 'axios';

// Типы для Ollama API ответов
interface OllamaResponse {
  response?: string;
  model?: string;
  created_at?: string;
  done?: boolean;
}

export interface EmployeeSearchResult {
  employees: EmployeeInfo[];
  debug?: {
    searchQuery: string;
    ragResultsCount: number;
    llmPrompt: string;
    llmResponse: string;
    processingTime: number;
  };
}

/**
 * Сервис для поиска сотрудников в базе знаний
 * Использует гибридный поиск (векторный + BM25) + LLM для извлечения данных
 */
export class EmployeeSearchService {
  
  /**
   * Основной метод поиска сотрудников
   * @param query - имя сотрудника для поиска
   * @param accessLevel - уровень доступа пользователя
   * @param includeDebug - включить отладочную информацию
   */
  async searchEmployees(
    query: string, 
    accessLevel: number, 
    includeDebug: boolean = false
  ): Promise<EmployeeSearchResult> {
    const startTime = Date.now();
    
    try {
      logger.info('Searching employees', { query, accessLevel, includeDebug });

      // 1. Выполняем гибридный поиск в базе знаний
      const ragResults = await this.performHybridSearch(query, accessLevel);
      
      if (!ragResults.success || !ragResults.sources?.length) {
        logger.warn('No RAG results found for employee search', { query });
        return {
          employees: [],
          debug: includeDebug ? {
            searchQuery: query,
            ragResultsCount: 0,
            llmPrompt: '',
            llmResponse: 'No RAG results',
            processingTime: Date.now() - startTime
          } : undefined
        };
      }

      // 2. Объединяем контент из всех источников
      const combinedContent = ragResults.sources
        .map((source: any) => source.text || '')
        .filter((text: string) => text.trim() !== '')
        .join('\n\n');

      // 3. Используем LLM для извлечения информации о сотрудниках
      const llmResult = await this.extractEmployeesWithLLM(combinedContent, query);
      
      const result: EmployeeSearchResult = {
        employees: llmResult.employees,
        debug: includeDebug ? {
          searchQuery: query,
          ragResultsCount: ragResults.sources.length,
          llmPrompt: llmResult.prompt,
          llmResponse: llmResult.rawResponse,
          processingTime: Date.now() - startTime
        } : undefined
      };

      logger.info('Employee search completed', {
        query,
        foundEmployees: result.employees.length,
        processingTime: Date.now() - startTime
      });

      return result;

    } catch (error) {
      logger.error('Error searching employees', { error, query });
      return {
        employees: [],
        debug: includeDebug ? {
          searchQuery: query,
          ragResultsCount: 0,
          llmPrompt: '',
          llmResponse: `ERROR: ${error instanceof Error ? error.message : 'Unknown error'}`,
          processingTime: Date.now() - startTime
        } : undefined
      };
    }
  }

  /**
   * Выполняет гибридный поиск в базе знаний
   */
  private async performHybridSearch(query: string, accessLevel: number): Promise<any> {
    const redis = createClient({
      url: process.env.CELERY_RESULT_BACKEND || 'redis://localhost:6379/0'
    });

    try {
      await redis.connect();

      const taskId = `employee_search_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      const taskBody = [
        [query, accessLevel, 10, 5, 0.7, 0.3], // query, access_level, topK, rerankTopK, vectorWeight, bm25Weight
        {},
        { callbacks: null, errbacks: null, chain: null, chord: null }
      ];

      const celeryMessage = {
        body: Buffer.from(JSON.stringify(taskBody)).toString('base64'),
        'content-encoding': 'utf-8',
        'content-type': 'application/json',
        headers: {
          lang: 'py',
          task: 'tasks.hybrid_search',
          id: taskId,
          shadow: null,
          eta: null,
          expires: null,
          group: null,
          group_index: null,
          retries: 0,
          timelimit: [null, null],
          root_id: taskId,
          parent_id: null,
          argsrepr: `('${query}', ${accessLevel}, 10, 5, 0.7, 0.3)`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: { exchange: 'queries', routing_key: 'queries' },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      await redis.lPush('queries', JSON.stringify(celeryMessage));
      
      // Ожидаем результат
      let attempts = 0;
      const maxAttempts = 30;

      while (attempts < maxAttempts) {
        const result = await redis.get(`celery-task-meta-${taskId}`);
        
        if (result) {
          const parsedResult = JSON.parse(result);
          
          if (parsedResult.status === 'SUCCESS') {
            await redis.disconnect();
            return parsedResult.result;
          } else if (parsedResult.status === 'FAILURE') {
            await redis.disconnect();
            throw new Error(`Hybrid search failed: ${parsedResult.traceback}`);
          }
        }

        await new Promise(resolve => setTimeout(resolve, 1000));
        attempts++;
      }

      await redis.disconnect();
      throw new Error('Hybrid search timeout');

    } catch (error) {
      await redis.disconnect().catch(() => {});
      throw error;
    }
  }

  /**
   * Использует LLM для извлечения информации о сотрудниках из текста
   */
  private async extractEmployeesWithLLM(content: string, query: string): Promise<{
    employees: EmployeeInfo[];
    prompt: string;
    rawResponse: string;
  }> {
    const prompt = `Найди ВСЕХ сотрудников, которые соответствуют запросу "${query}" в тексте.

ПРАВИЛА:
- Ищи точные и частичные совпадения имени "${query}"
- Для каждого сотрудника ОБЯЗАТЕЛЬНО должен быть email
- Игнорируй людей без email адресов

Текст: "${content}"

Ответь ТОЛЬКО в формате JSON массива:
[
  {
    "name": "Полное имя сотрудника",
    "email": "email@domain.com", 
    "department": "Отдел",
    "position": "Должность"
  }
]

Если никого не найдено: []`;

    try {
      const response = await axios.post(
        `${process.env.OLLAMA_HOST || 'http://localhost:11434'}/api/generate`,
        {
          model: 'qwen-rag-optimized',
          prompt: prompt,
          stream: false,
          options: {
            temperature: 0.1,
            top_p: 0.9,
            num_predict: 500
          }
        },
        { timeout: 30000 }
      );

      const rawResponse = (response.data as OllamaResponse).response?.trim() || '';
      
      try {
        const parsed = JSON.parse(rawResponse);
        
        if (Array.isArray(parsed)) {
          const employees: EmployeeInfo[] = parsed
            .filter(emp => emp.email && emp.email.includes('@'))
            .map(emp => ({
              name: emp.name || query,
              email: emp.email,
              department: emp.department || '',
              position: emp.position || ''
            }));
          
          return { employees, prompt, rawResponse };
        }
        
        return { employees: [], prompt, rawResponse };

      } catch (parseError) {
        logger.warn('Failed to parse LLM response for employee extraction', { 
          rawResponse: rawResponse.substring(0, 200), 
          parseError,
          query 
        });
        return { employees: [], prompt, rawResponse };
      }

    } catch (error) {
      logger.error('Error extracting employees with LLM', { error, query });
      return { 
        employees: [], 
        prompt, 
        rawResponse: `ERROR: ${error instanceof Error ? error.message : 'Unknown error'}` 
      };
    }
  }
}
