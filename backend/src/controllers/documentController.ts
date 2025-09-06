import { Request, Response, NextFunction } from 'express';
import { DocumentService, CreateDocumentData, UpdateChunkData } from '../services/documentService';
import { AppError } from '../utils/AppError';
import { logger } from '../utils/logger';
import { AuthenticatedUser } from '../types';
import path from 'path';
import fs from 'fs/promises';

export class DocumentController {
  static async upload(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      if (!req.file) {
        throw new AppError('No file uploaded', 400);
      }

      const { title, accessLevel } = req.body;

      if (!title) {
        throw new AppError('Title is required', 400);
      }

      const parsedAccessLevel = parseInt(accessLevel) || req.user.accessLevel;

      // Проверяем, что пользователь не устанавливает уровень доступа выше своего
      if (parsedAccessLevel > req.user.accessLevel) {
        throw new AppError('Cannot set access level higher than your own', 403);
      }

      const documentData: CreateDocumentData = {
        title,
        filePath: req.file.path,
        fileType: req.file.mimetype,
        accessLevel: parsedAccessLevel,
        uploadedBy: req.user.id,
        metadata: {
          originalName: req.file.originalname,
          size: req.file.size,
          uploadedAt: new Date().toISOString()
        }
      };

      const document = await DocumentService.createDocument(documentData);

      res.status(201).json({
        success: true,
        data: document,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      // Удаляем загруженный файл в случае ошибки
      if (req.file) {
        try {
          await fs.unlink(req.file.path);
        } catch (unlinkError) {
          logger.warn('Failed to delete uploaded file after error:', unlinkError);
        }
      }
      next(error);
    }
  }

  static async getStats(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const stats = await DocumentService.getStats(req.user.accessLevel);

      res.status(200).json({
        success: true,
        data: stats,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async getDocuments(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const page = parseInt(req.query.page as string) || 1;
      const limit = Math.min(parseInt(req.query.limit as string) || 20, 100); // Максимум 100

      const result = await DocumentService.getDocuments(
        req.user.id,
        req.user.accessLevel,
        page,
        limit
      );

      res.status(200).json({
        success: true,
        data: result.documents,
        metadata: {
          page,
          limit,
          total: result.total,
          totalPages: Math.ceil(result.total / limit),
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async getDocumentById(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const { id } = req.params;

      const document = await DocumentService.getDocumentById(id, req.user.accessLevel);

      if (!document) {
        throw new AppError('Document not found or access denied', 404);
      }

      res.status(200).json({
        success: true,
        data: document,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async deleteDocument(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const { id } = req.params;

      await DocumentService.deleteDocument(
        id,
        req.user.id,
        req.user.accessLevel,
        req.user.role
      );

      res.status(200).json({
        success: true,
        data: { message: 'Document deleted successfully' },
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async getDocumentChunks(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const { id } = req.params;
      const page = parseInt(req.query.page as string) || 1;
      const limit = Math.min(parseInt(req.query.limit as string) || 50, 200); // Максимум 200

      const result = await DocumentService.getDocumentChunks(
        id,
        req.user.accessLevel,
        page,
        limit
      );

      res.status(200).json({
        success: true,
        data: result.chunks,
        metadata: {
          page,
          limit,
          total: result.total,
          totalPages: Math.ceil(result.total / limit),
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async updateChunk(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const { id: documentId, chunkId } = req.params;
      const { content, metadata } = req.body;

      if (!content && !metadata) {
        throw new AppError('Content or metadata is required', 400);
      }

      const updateData: UpdateChunkData = {};
      if (content) updateData.content = content;
      if (metadata) updateData.metadata = metadata;

      const updatedChunk = await DocumentService.updateChunk(
        documentId,
        chunkId,
        updateData,
        req.user.id,
        req.user.accessLevel,
        req.user.role
      );

      res.status(200).json({
        success: true,
        data: updatedChunk,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async deleteChunk(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      const { id: documentId, chunkId } = req.params;

      await DocumentService.deleteChunk(
        documentId,
        chunkId,
        req.user.id,
        req.user.accessLevel,
        req.user.role
      );

      res.status(200).json({
        success: true,
        data: { message: 'Chunk deleted successfully' },
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }

  static async extractKeywords(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      if (!req.user) {
        throw new AppError('Authentication required', 401);
      }

      // Только администраторы могут запускать извлечение ключевых слов
      if (req.user.role !== 'ADMIN') {
        throw new AppError('Admin access required', 403);
      }

      const { id: documentId } = req.params;

      logger.info(`Starting keyword extraction for document: ${documentId || 'all documents'}`);

      const result = await DocumentService.extractKeywords(documentId);

      res.status(200).json({
        success: true,
        data: result,
        metadata: {
          timestamp: new Date().toISOString()
        }
      });
    } catch (error) {
      next(error);
    }
  }
}
