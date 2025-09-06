import { createClient } from 'redis';
import { logger } from '../utils/logger';
import { AppError } from '../utils/AppError';

const redis = createClient({
  url: process.env.REDIS_URL || 'redis://localhost:6379'
});

redis.on('error', (err) => {
  console.error('Redis Client Error', err);
});

redis.connect().catch(console.error);

export interface SearchResult {
  id: string;
  content: string;
  metadata: any;
  score: number;
  type: 'vector' | 'bm25' | 'hybrid';
  rank: number;
}

export interface HybridSearchOptions {
  vectorWeight?: number;
  bm25Weight?: number;
  topK?: number;
  rerankTopK?: number;
}

export class SearchService {
  /**
   * ЭТАП 3: Гибридный поиск с векторным поиском + BM25
   * 
   * @param query Поисковый запрос
   * @param userAccessLevel Уровень доступа пользователя
   * @param options Опции поиска
   * @returns Результаты гибридного поиска
   */
  static async hybridSearch(
    query: string,
    userAccessLevel: number,
    options: HybridSearchOptions = {}
  ): Promise<SearchResult[]> {
    try {
      const {
        vectorWeight = 0.7,    // 70% вес векторного поиска
        bm25Weight = 0.3,      // 30% вес BM25
        topK = 30,             // Топ результатов для каждого метода
        rerankTopK = 10        // Финальное количество результатов
      } = options;

      logger.info(`Starting hybrid search for query: "${query.substring(0, 100)}..."`);

      // Формируем задачу для гибридного поиска в worker
      const taskId = `hybrid_search_${Date.now()}`;
      
      const taskBody = [
        [query, userAccessLevel, topK, rerankTopK, vectorWeight, bm25Weight], // args
        {}, // kwargs
        {
          callbacks: null,
          errbacks: null,
          chain: null,
          chord: null
        }
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
          argsrepr: `('${query}', ${userAccessLevel}, ${topK}, ${rerankTopK}, ${vectorWeight}, ${bm25Weight})`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: {
            exchange: 'queries',
            routing_key: 'queries'
          },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      // Отправляем в очередь queries
      await redis.lPush('queries', JSON.stringify(celeryMessage));
      
      logger.info(`Hybrid search queued: ${taskId}`, { 
        query: query.substring(0, 100),
        userAccessLevel,
        topK,
        rerankTopK,
        vectorWeight,
        bm25Weight,
        queue: 'queries'
      });

      return [{ 
        id: taskId,
        content: '',
        metadata: { status: 'queued' },
        score: 0,
        type: 'hybrid',
        rank: 0
      }];

    } catch (error) {
      logger.error('Error in hybrid search:', error);
      throw new AppError('Failed to perform hybrid search', 500);
    }
  }

  /**
   * T1.6: Batch гибридный поиск для множественных запросов
   */
  static async batchHybridSearch(
    queries: string[],
    userAccessLevel: number,
    options: HybridSearchOptions = {}
  ): Promise<any> {
    try {
      const {
        vectorWeight = 0.7,
        bm25Weight = 0.3,
        topK = 30,
        rerankTopK = 10
      } = options;

      logger.info(`Starting batch hybrid search for ${queries.length} queries`);

      const taskId = `batch_hybrid_search_${Date.now()}`;
      
      const taskBody = [
        [queries, userAccessLevel, topK, rerankTopK, vectorWeight, bm25Weight], // args
        {}, // kwargs
        {
          callbacks: null,
          errbacks: null,
          chain: null,
          chord: null
        }
      ];

      const celeryMessage = {
        body: Buffer.from(JSON.stringify(taskBody)).toString('base64'),
        'content-encoding': 'utf-8',
        'content-type': 'application/json',
        headers: {
          lang: 'py',
          task: 'tasks.batch_hybrid_search',
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
          argsrepr: `([${queries.length} queries], ${userAccessLevel}, ${topK}, ${rerankTopK}, ${vectorWeight}, ${bm25Weight})`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: {
            exchange: 'queries',
            routing_key: 'queries'
          },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      await redis.lPush('queries', JSON.stringify(celeryMessage));
      
      logger.info(`Batch hybrid search queued: ${taskId}`, { 
        queries_count: queries.length,
        userAccessLevel,
        topK,
        rerankTopK,
        vectorWeight,
        bm25Weight,
        queue: 'queries'
      });

      return { taskId, status: 'queued', batch_size: queries.length };

    } catch (error) {
      logger.error('Error in batch hybrid search:', error);
      throw new AppError('Failed to perform batch hybrid search', 500);
    }
  }

  /**
   * Получить результат задачи гибридного поиска
   */
  static async getSearchResult(taskId: string): Promise<any> {
    try {
      const result = await redis.get(`celery-task-meta-${taskId}`);
      
      if (!result) {
        return { status: 'PENDING' };
      }

      const parsedResult = JSON.parse(result);
      return parsedResult;
    } catch (error) {
      logger.error('Error getting search result:', error);
      throw new AppError('Failed to get search result', 500);
    }
  }

  /**
   * Традиционный RAG поиск (для обратной совместимости)
   */
  static async ragSearch(
    query: string,
    userAccessLevel: number,
    topK: number = 30
  ): Promise<any> {
    try {
      const taskId = `rag_${Date.now()}`;
      
      const taskBody = [
        [query, userAccessLevel], // args
        {}, // kwargs
        {
          callbacks: null,
          errbacks: null,
          chain: null,
          chord: null
        }
      ];

      const celeryMessage = {
        body: Buffer.from(JSON.stringify(taskBody)).toString('base64'),
        'content-encoding': 'utf-8',
        'content-type': 'application/json',
        headers: {
          lang: 'py',
          task: 'tasks.rag_query',
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
          argsrepr: `('${query}', ${userAccessLevel})`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: {
            exchange: 'queries',
            routing_key: 'queries'
          },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      await redis.lPush('queries', JSON.stringify(celeryMessage));
      
      logger.info(`RAG search queued: ${taskId}`, { 
        query: query.substring(0, 100),
        userAccessLevel,
        queue: 'queries'
      });

      return { taskId, status: 'queued' };
    } catch (error) {
      logger.error('Error in RAG search:', error);
      throw new AppError('Failed to perform RAG search', 500);
    }
  }
}
