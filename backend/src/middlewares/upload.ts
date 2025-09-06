import multer from 'multer';
import path from 'path';
import { Request } from 'express';
import { AppError } from '../utils/AppError';
import { CONSTANTS } from '../types';

// Настройка хранения файлов
const storage = multer.diskStorage({
  destination: (req: Request, file: Express.Multer.File, cb) => {
    cb(null, 'uploads/');
  },
  filename: (req: Request, file: Express.Multer.File, cb) => {
    // Генерируем уникальное имя файла
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    const ext = path.extname(file.originalname);
    cb(null, `${file.fieldname}-${uniqueSuffix}${ext}`);
  }
});

// Фильтр файлов - разрешенные типы согласно ТЗ
const fileFilter = (req: Request, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
  const allowedMimeTypes = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
    'application/msword', // .doc
    'text/plain', // .txt
    'text/csv', // .csv
    'application/json', // .json
    'text/markdown', // .md
    'application/rtf' // .rtf
  ];

  const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt', '.csv', '.json', '.md', '.rtf'];
  const fileExtension = path.extname(file.originalname).toLowerCase();

  if (allowedMimeTypes.includes(file.mimetype) && allowedExtensions.includes(fileExtension)) {
    cb(null, true);
  } else {
    cb(new AppError(
      `File type not supported. Allowed types: ${allowedExtensions.join(', ')}`, 
      400
    ));
  }
};

// Конфигурация multer
export const uploadConfig = multer({
  storage,
  fileFilter,
  limits: {
    fileSize: CONSTANTS.MAX_FILE_SIZE, // 10MB
    files: 1 // Только один файл за раз
  }
});

// Middleware для обработки ошибок multer
export const handleMulterError = (error: any, req: Request, res: any, next: any) => {
  if (error instanceof multer.MulterError) {
    switch (error.code) {
      case 'LIMIT_FILE_SIZE':
        return res.status(400).json({
          success: false,
          error: `File too large. Maximum size is ${CONSTANTS.MAX_FILE_SIZE / (1024 * 1024)}MB`
        });
      case 'LIMIT_FILE_COUNT':
        return res.status(400).json({
          success: false,
          error: 'Too many files. Only one file allowed per upload'
        });
      case 'LIMIT_UNEXPECTED_FILE':
        return res.status(400).json({
          success: false,
          error: 'Unexpected field name. Use "file" field for upload'
        });
      default:
        return res.status(400).json({
          success: false,
          error: `Upload error: ${error.message}`
        });
    }
  }
  
  if (error instanceof AppError) {
    return res.status(error.statusCode).json({
      success: false,
      error: error.message
    });
  }
  
  next(error);
};

// Middleware для валидации данных загрузки
export const validateUploadData = (req: Request, res: any, next: any) => {
  const { title, accessLevel } = req.body;
  
  if (!title || typeof title !== 'string' || title.trim().length === 0) {
    return res.status(400).json({
      success: false,
      error: 'Title is required and must be a non-empty string'
    });
  }
  
  if (title.length > 255) {
    return res.status(400).json({
      success: false,
      error: 'Title must be less than 255 characters'
    });
  }
  
  if (accessLevel !== undefined) {
    const parsedAccessLevel = parseInt(accessLevel);
    if (isNaN(parsedAccessLevel) || parsedAccessLevel < CONSTANTS.ACCESS_LEVEL_MIN || parsedAccessLevel > CONSTANTS.ACCESS_LEVEL_MAX) {
      return res.status(400).json({
        success: false,
        error: `Access level must be between ${CONSTANTS.ACCESS_LEVEL_MIN} and ${CONSTANTS.ACCESS_LEVEL_MAX}`
      });
    }
  }
  
  next();
};

// Rate limiting для загрузки файлов
export const uploadRateLimit = (req: Request, res: any, next: any) => {
  // Простая реализация rate limiting
  // В продакшене лучше использовать Redis для хранения счетчиков
  const userUploads = (global as any).userUploads || {};
  const userId = (req as any).user?.id;
  
  if (!userId) {
    return next();
  }
  
  const now = Date.now();
  const windowMs = 60 * 1000; // 1 минута
  const maxUploads = 10; // Максимум 10 загрузок в минуту
  
  if (!userUploads[userId]) {
    userUploads[userId] = [];
  }
  
  // Очищаем старые записи
  userUploads[userId] = userUploads[userId].filter((timestamp: number) => 
    now - timestamp < windowMs
  );
  
  if (userUploads[userId].length >= maxUploads) {
    return res.status(429).json({
      success: false,
      error: 'Too many uploads. Please wait before uploading again.'
    });
  }
  
  userUploads[userId].push(now);
  (global as any).userUploads = userUploads;
  
  next();
};
