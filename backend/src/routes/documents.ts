import { Router } from 'express';
import { DocumentController } from '../controllers/documentController';
import { authenticate, checkAccessLevel } from '../middlewares/auth';
import { 
  uploadConfig, 
  handleMulterError, 
  validateUploadData, 
  uploadRateLimit 
} from '../middlewares/upload';

const router = Router();

// КРИТИЧНО: Все роуты требуют аутентификации согласно ТЗ

// POST /api/documents/upload - Загрузка документа
router.post('/upload',
  authenticate,                                    // 1. Проверка JWT
  checkAccessLevel(10),                           // 2. Минимальный уровень доступа
  uploadRateLimit,                                // 3. Rate limiting
  uploadConfig.single('file'),                    // 4. Multer для загрузки файла
  handleMulterError,                              // 5. Обработка ошибок multer
  validateUploadData,                             // 6. Валидация данных
  DocumentController.upload                       // 7. Контроллер
);

// GET /api/documents/stats - Получить статистику документов
router.get('/stats',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(1),                           // 2. Минимальный уровень доступа
  DocumentController.getStats                     // 3. Контроллер
);

// GET /api/documents - Получить список документов
router.get('/',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(1),                           // 2. Минимальный уровень доступа
  DocumentController.getDocuments                 // 3. Контроллер
);

// GET /api/documents/:id - Получить документ по ID
router.get('/:id',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(1),                           // 2. Минимальный уровень доступа
  DocumentController.getDocumentById              // 3. Контроллер
);

// DELETE /api/documents/:id - Удалить документ
router.delete('/:id',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(10),                          // 2. Минимальный уровень доступа для удаления
  DocumentController.deleteDocument               // 3. Контроллер
);

// GET /api/documents/:id/chunks - Получить чанки документа
router.get('/:id/chunks',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(1),                           // 2. Минимальный уровень доступа
  DocumentController.getDocumentChunks            // 3. Контроллер
);

// PUT /api/documents/:id/chunks/:chunkId - Обновить чанк
router.put('/:id/chunks/:chunkId',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(20),                          // 2. Повышенный уровень доступа для редактирования
  DocumentController.updateChunk                  // 3. Контроллер
);

// DELETE /api/documents/:id/chunks/:chunkId - Удалить чанк
router.delete('/:id/chunks/:chunkId',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(20),                          // 2. Повышенный уровень доступа для удаления
  DocumentController.deleteChunk                  // 3. Контроллер
);

// POST /api/documents/:id/extract-keywords - Извлечь ключевые слова для конкретного документа
router.post('/:id/extract-keywords',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(90),                          // 2. Только для администраторов
  DocumentController.extractKeywords              // 3. Контроллер
);

// POST /api/documents/extract-keywords - Извлечь ключевые слова для всех документов
router.post('/extract-keywords',
  authenticate,                                   // 1. Проверка JWT
  checkAccessLevel(90),                          // 2. Только для администраторов
  DocumentController.extractKeywords              // 3. Контроллер
);

export default router;
