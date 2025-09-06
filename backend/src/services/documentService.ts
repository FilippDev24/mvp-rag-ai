import { PrismaClient, Document, Chunk } from '@prisma/client';
import { createClient } from 'redis';
import fs from 'fs/promises';
import path from 'path';
import { AppError } from '../utils/AppError';
import { logger } from '../utils/logger';

const prisma = new PrismaClient();
const redis = createClient({
  url: process.env.REDIS_URL || 'redis://localhost:6379'
});

redis.on('error', (err) => {
  console.error('Redis Client Error', err);
});

redis.connect().catch(console.error);

export interface CreateDocumentData {
  title: string;
  filePath: string;
  fileType: string;
  accessLevel: number;
  uploadedBy: string;
  metadata?: any;
}

export interface UpdateChunkData {
  content?: string;
  metadata?: any;
}

export class DocumentService {
  static async createDocument(data: CreateDocumentData): Promise<Document> {
    try {
      const document = await prisma.document.create({
        data: {
          title: data.title,
          filePath: data.filePath,
          fileType: data.fileType,
          accessLevel: data.accessLevel,
          uploadedBy: data.uploadedBy,
          metadata: data.metadata || {}
        },
        include: {
          user: {
            select: {
              id: true,
              email: true,
              fullName: true
            }
          }
        }
      });

      // Отправляем задачу в Redis для обработки документа
      await this.queueDocumentProcessing(document.id, data.filePath, data.accessLevel);

      logger.info(`Document created: ${document.id}`, { documentId: document.id });
      return document;
    } catch (error) {
      logger.error('Error creating document:', error);
      throw new AppError('Failed to create document', 500);
    }
  }

  static async getStats(userAccessLevel: number): Promise<{
    documentsCount: number;
    chunksCount: number;
    messagesCount: number;
  }> {
    try {
      const [documentsCount, chunksCount, messagesCount] = await Promise.all([
        prisma.document.count({
          where: {
            accessLevel: { lte: userAccessLevel }
          }
        }),
        prisma.chunk.count({
          where: {
            accessLevel: { lte: userAccessLevel }
          }
        }),
        prisma.message.count()
      ]);

      return {
        documentsCount,
        chunksCount,
        messagesCount
      };
    } catch (error) {
      logger.error('Error fetching stats:', error);
      throw new AppError('Failed to fetch stats', 500);
    }
  }

  static async getDocuments(
    userId: string, 
    userAccessLevel: number,
    page: number = 1,
    limit: number = 20
  ): Promise<{ documents: Document[]; total: number }> {
    try {
      const skip = (page - 1) * limit;

      const [documents, total] = await Promise.all([
        prisma.document.findMany({
          where: {
            accessLevel: { lte: userAccessLevel }
          },
          include: {
            user: {
              select: {
                id: true,
                email: true,
                fullName: true
              }
            }
          },
          orderBy: { createdAt: 'desc' },
          skip,
          take: limit
        }),
        prisma.document.count({
          where: {
            accessLevel: { lte: userAccessLevel }
          }
        })
      ]);

      return { documents, total };
    } catch (error) {
      logger.error('Error fetching documents:', error);
      throw new AppError('Failed to fetch documents', 500);
    }
  }

  static async getDocumentById(
    id: string, 
    userAccessLevel: number
  ): Promise<Document | null> {
    try {
      const document = await prisma.document.findFirst({
        where: {
          id,
          accessLevel: { lte: userAccessLevel }
        },
        include: {
          user: {
            select: {
              id: true,
              email: true,
              fullName: true
            }
          }
        }
      });

      return document;
    } catch (error) {
      logger.error('Error fetching document:', error);
      throw new AppError('Failed to fetch document', 500);
    }
  }

  static async deleteDocument(
    id: string, 
    userId: string, 
    userAccessLevel: number,
    userRole: string
  ): Promise<void> {
    try {
      const document = await prisma.document.findFirst({
        where: {
          id,
          accessLevel: { lte: userAccessLevel }
        }
      });

      if (!document) {
        throw new AppError('Document not found or access denied', 404);
      }

      // Проверяем права: админ может удалить любой документ, пользователь - только свой
      if (userRole !== 'ADMIN' && document.uploadedBy !== userId) {
        throw new AppError('Access denied', 403);
      }

      // Удаляем файл с диска
      if (document.filePath) {
        try {
          await fs.unlink(document.filePath);
        } catch (fileError) {
          logger.warn(`Failed to delete file: ${document.filePath}`, fileError);
        }
      }

      // Удаляем чанки из ChromaDB через worker
      await this.deleteDocumentFromWorker(id);

      // Удаляем документ из БД (каскадно удалятся и чанки)
      await prisma.document.delete({
        where: { id }
      });

      logger.info(`Document deleted: ${id}`, { documentId: id, userId });
    } catch (error) {
      if (error instanceof AppError) throw error;
      logger.error('Error deleting document:', error);
      throw new AppError('Failed to delete document', 500);
    }
  }

  static async getDocumentChunks(
    documentId: string,
    userAccessLevel: number,
    page: number = 1,
    limit: number = 50
  ): Promise<{ chunks: any[]; total: number }> {
    try {
      // Проверяем доступ к документу
      const document = await this.getDocumentById(documentId, userAccessLevel);
      if (!document) {
        throw new AppError('Document not found or access denied', 404);
      }

      const skip = (page - 1) * limit;

      // ЭТАП 2: Получаем чанки из PostgreSQL с ключевыми словами в метаданных
      const [chunks, total] = await Promise.all([
        prisma.chunk.findMany({
          where: {
            documentId,
            accessLevel: { lte: userAccessLevel }
          },
          orderBy: { chunkIndex: 'asc' },
          skip,
          take: limit
        }),
        prisma.chunk.count({
          where: {
            documentId,
            accessLevel: { lte: userAccessLevel }
          }
        })
      ]);

      // Преобразуем чанки в нужный формат с извлечением ключевых слов из метаданных
      const formattedChunks = chunks.map(chunk => {
        const metadata = chunk.metadata as any || {};
        
        return {
          id: chunk.id,
          content: chunk.content,
          documentId: chunk.documentId,
          documentTitle: document.title,
          chunkIndex: chunk.chunkIndex,
          accessLevel: chunk.accessLevel,
          charCount: chunk.charCount,
          createdAt: chunk.createdAt.toISOString(),
          metadata: metadata,
          // ЭТАП 2: Извлекаем ключевые слова из метаданных PostgreSQL
          keywords: metadata.semantic_keywords || metadata.technical_keywords || metadata.all_keywords ? {
            semantic_keywords: metadata.semantic_keywords || [],
            technical_keywords: metadata.technical_keywords || [],
            all_keywords: metadata.all_keywords || []
          } : null
        };
      });

      return { chunks: formattedChunks, total };
    } catch (error) {
      if (error instanceof AppError) throw error;
      logger.error('Error fetching document chunks:', error);
      throw new AppError('Failed to fetch document chunks', 500);
    }
  }

  static async updateChunk(
    documentId: string,
    chunkId: string,
    data: UpdateChunkData,
    userId: string,
    userAccessLevel: number,
    userRole: string
  ): Promise<Chunk> {
    try {
      // Проверяем доступ к документу
      const document = await this.getDocumentById(documentId, userAccessLevel);
      if (!document) {
        throw new AppError('Document not found or access denied', 404);
      }

      // Проверяем права на редактирование
      if (userRole !== 'ADMIN' && document.uploadedBy !== userId) {
        throw new AppError('Access denied', 403);
      }

      const chunk = await prisma.chunk.findFirst({
        where: {
          id: chunkId,
          documentId,
          accessLevel: { lte: userAccessLevel }
        }
      });

      if (!chunk) {
        throw new AppError('Chunk not found or access denied', 404);
      }

      const updatedChunk = await prisma.chunk.update({
        where: { id: chunkId },
        data: {
          ...(data.content && { 
            content: data.content,
            charCount: data.content.length
          }),
          ...(data.metadata && { metadata: data.metadata })
        }
      });

      logger.info(`Chunk updated: ${chunkId}`, { chunkId, documentId, userId });
      return updatedChunk;
    } catch (error) {
      if (error instanceof AppError) throw error;
      logger.error('Error updating chunk:', error);
      throw new AppError('Failed to update chunk', 500);
    }
  }

  static async deleteChunk(
    documentId: string,
    chunkId: string,
    userId: string,
    userAccessLevel: number,
    userRole: string
  ): Promise<void> {
    try {
      // Проверяем доступ к документу
      const document = await this.getDocumentById(documentId, userAccessLevel);
      if (!document) {
        throw new AppError('Document not found or access denied', 404);
      }

      // Проверяем права на удаление
      if (userRole !== 'ADMIN' && document.uploadedBy !== userId) {
        throw new AppError('Access denied', 403);
      }

      const chunk = await prisma.chunk.findFirst({
        where: {
          id: chunkId,
          documentId,
          accessLevel: { lte: userAccessLevel }
        }
      });

      if (!chunk) {
        throw new AppError('Chunk not found or access denied', 404);
      }

      await prisma.chunk.delete({
        where: { id: chunkId }
      });

      // Обновляем счетчик чанков в документе
      await prisma.document.update({
        where: { id: documentId },
        data: {
          chunkCount: {
            decrement: 1
          }
        }
      });

      logger.info(`Chunk deleted: ${chunkId}`, { chunkId, documentId, userId });
    } catch (error) {
      if (error instanceof AppError) throw error;
      logger.error('Error deleting chunk:', error);
      throw new AppError('Failed to delete chunk', 500);
    }
  }

  private static async queueDocumentProcessing(
    documentId: string,
    filePath: string,
    accessLevel: number,
    documentTitle?: string
  ): Promise<void> {
    try {
      // Правильный формат задачи для Celery согласно протоколу
      const taskId = `doc_${documentId}_${Date.now()}`;
      
      const taskBody = [
        [documentId, filePath, accessLevel, documentTitle || null], // args
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
          task: 'tasks.process_document',
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
          argsrepr: `('${documentId}', '${filePath}', ${accessLevel}, ${documentTitle ? `'${documentTitle}'` : 'None'})`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: {
            exchange: 'document_processing',
            routing_key: 'document_processing'
          },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      // Отправляем в очередь document_processing согласно настройкам worker
      await redis.lPush('document_processing', JSON.stringify(celeryMessage));
      
      // Обновляем статус документа
      await prisma.document.update({
        where: { id: documentId },
        data: { 
          status: 'PROCESSING',
          processedAt: null
        }
      });

      logger.info(`Document processing queued: ${documentId}`, { 
        documentId, 
        filePath, 
        accessLevel,
        queue: 'document_processing'
      });
    } catch (error) {
      logger.error('Error queuing document processing:', error);
      
      // Обновляем статус на ошибку
      try {
        await prisma.document.update({
          where: { id: documentId },
          data: { status: 'ERROR' }
        });
      } catch (updateError) {
        logger.error('Error updating document status to ERROR:', updateError);
      }
      
      throw new AppError('Failed to queue document processing', 500);
    }
  }

  static async queryKnowledgeBase(
    query: string,
    userAccessLevel: number,
    topK: number = 30
  ): Promise<any> {
    try {
      // Формат задачи для поиска в базе знаний
      const task = {
        task: 'tasks.query_knowledge_base',
        args: [query, userAccessLevel, topK],
        kwargs: {},
        id: `query_${Date.now()}`,
        retries: 2,
        eta: null,
        expires: null,
        utc: true
      };

      // Отправляем в очередь queries
      await redis.lPush('queries', JSON.stringify(task));
      
      logger.info(`Knowledge base query queued`, { 
        query: query.substring(0, 100), 
        userAccessLevel,
        topK,
        queue: 'queries'
      });

      // Возвращаем ID задачи для отслеживания
      return { taskId: task.id };
    } catch (error) {
      logger.error('Error queuing knowledge base query:', error);
      throw new AppError('Failed to queue knowledge base query', 500);
    }
  }

  static async getTaskResult(taskId: string): Promise<any> {
    try {
      // Получаем результат задачи из Redis
      const result = await redis.get(`celery-task-meta-${taskId}`);
      
      if (!result) {
        return { status: 'PENDING' };
      }

      const parsedResult = JSON.parse(result);
      return parsedResult;
    } catch (error) {
      logger.error('Error getting task result:', error);
      throw new AppError('Failed to get task result', 500);
    }
  }

  static async deleteDocumentFromWorker(documentId: string): Promise<void> {
    try {
      const taskId = `delete_${documentId}_${Date.now()}`;
      
      const taskBody = [
        [documentId], // args
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
          task: 'tasks.delete_document',
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
          argsrepr: `('${documentId}',)`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: {
            exchange: 'document_processing',
            routing_key: 'document_processing'
          },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      await redis.lPush('document_processing', JSON.stringify(celeryMessage));
      
      logger.info(`Document deletion queued: ${documentId}`, { 
        documentId,
        taskId,
        queue: 'document_processing'
      });
    } catch (error) {
      logger.error('Error queuing document deletion:', error);
      // Не бросаем ошибку, так как документ уже удален из БД
    }
  }

  static async getWorkerHealth(): Promise<any> {
    try {
      const task = {
        task: 'tasks.health_check',
        args: [],
        kwargs: {},
        id: `health_${Date.now()}`,
        retries: 1
      };

      await redis.lPush('document_processing', JSON.stringify(task));
      
      return { status: 'queued', taskId: task.id };
    } catch (error) {
      logger.error('Error queuing health check:', error);
      return { status: 'error', error: error instanceof Error ? error.message : String(error) };
    }
  }

  static async extractKeywords(documentId?: string): Promise<any> {
    try {
      // ЭТАП 2: Извлечение ключевых слов для существующих документов
      const taskId = `keywords_${documentId || 'all'}_${Date.now()}`;
      
      const taskBody = [
        [documentId || null], // args - если documentId не указан, обрабатываем все
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
          task: 'tasks.extract_keywords_for_existing_chunks',
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
          argsrepr: `(${documentId ? `'${documentId}'` : 'None'},)`,
          kwargsrepr: '{}',
          origin: 'gen1@backend'
        },
        properties: {
          correlation_id: taskId,
          reply_to: taskId,
          delivery_mode: 2,
          delivery_info: {
            exchange: 'document_processing',
            routing_key: 'document_processing'
          },
          priority: 0,
          body_encoding: 'base64',
          delivery_tag: taskId
        }
      };

      // Отправляем в очередь document_processing
      await redis.lPush('document_processing', JSON.stringify(celeryMessage));
      
      logger.info(`Keyword extraction queued for document: ${documentId || 'all documents'}`, { 
        documentId,
        taskId,
        queue: 'document_processing'
      });

      return { 
        status: 'queued', 
        taskId,
        message: `Keyword extraction started for ${documentId ? 'document ' + documentId : 'all documents'}`
      };
    } catch (error) {
      logger.error('Error queuing keyword extraction:', error);
      throw new AppError('Failed to queue keyword extraction', 500);
    }
  }
}
