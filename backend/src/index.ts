import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import dotenv from 'dotenv';
import { checkDatabaseConnection, disconnectDatabase, logger } from './config/database';
import { 
  errorHandler, 
  notFoundHandler, 
  uncaughtExceptionHandler, 
  unhandledRejectionHandler 
} from './middlewares/errorHandler';
import authRoutes from './routes/auth';
import documentRoutes from './routes/documents';
import { AppError } from './types';

// Load environment variables
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// ОБЯЗАТЕЛЬНО: Обработчики для неперехваченных ошибок согласно ТЗ
process.on('uncaughtException', uncaughtExceptionHandler);
process.on('unhandledRejection', unhandledRejectionHandler);

// Graceful shutdown
const gracefulShutdown = async (signal: string) => {
  logger.info(`Received ${signal}. Starting graceful shutdown...`);
  
  try {
    await disconnectDatabase();
    logger.info('Database disconnected successfully');
    process.exit(0);
  } catch (error) {
    logger.error('Error during graceful shutdown', { error });
    process.exit(1);
  }
};

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));

// ОБЯЗАТЕЛЬНО: Middleware согласно ТЗ
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      scriptSrc: ["'self'"],
      imgSrc: ["'self'", "data:", "https:"],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true
  }
}));

app.use(cors({
  origin: [
    process.env.FRONTEND_URL || 'http://localhost:3000',
    'http://localhost:3020',
    'http://localhost:8015',
    'http://89.169.150.113:3000'
  ],
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json({ 
  limit: process.env.MAX_FILE_SIZE || '10mb',
  verify: (req: express.Request, res, buf) => {
    // Логируем большие запросы
    if (buf.length > 1024 * 1024) { // > 1MB
      logger.info('Large request received', {
        size: buf.length,
        path: req.path,
        ip: req.ip
      });
    }
  }
}));

app.use(express.urlencoded({ 
  extended: true, 
  limit: process.env.MAX_FILE_SIZE || '10mb' 
}));

// Request logging middleware
app.use((req, res, next) => {
  const startTime = Date.now();
  
  res.on('finish', () => {
    const duration = Date.now() - startTime;
    
    logger.info('Request completed', {
      method: req.method,
      url: req.url,
      statusCode: res.statusCode,
      duration,
      ip: req.ip,
      userAgent: req.get('User-Agent'),
      userId: (req as any).user?.id
    });
  });
  
  next();
});

// Health check endpoint
app.get('/health', async (req, res) => {
  try {
    const dbConnected = await checkDatabaseConnection();
    
    const healthStatus = {
      status: 'OK',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      database: dbConnected ? 'connected' : 'disconnected',
      memory: process.memoryUsage(),
      version: process.version,
      environment: process.env.NODE_ENV || 'development'
    };
    
    if (!dbConnected) {
      return res.status(503).json({
        ...healthStatus,
        status: 'ERROR'
      });
    }
    
    res.json(healthStatus);
  } catch (error) {
    logger.error('Health check failed', { error });
    res.status(503).json({
      status: 'ERROR',
      timestamp: new Date().toISOString(),
      error: 'Health check failed'
    });
  }
});

// API base endpoint
app.get('/api', (req, res) => {
  res.json({ 
    message: 'Knowledge Base API is running',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    endpoints: {
      auth: '/api/auth',
      documents: '/api/documents',
      health: '/health'
    }
  });
});

// КРИТИЧНО: API routes с аутентификацией согласно ТЗ
app.use('/api/auth', authRoutes);
app.use('/api/documents', documentRoutes);

// RAG Chat routes
import chatRoutes from './routes/chat';
app.use('/api/chat', chatRoutes);

// Calendar routes
import calendarRoutes from './routes/calendar';
app.use('/api/calendar', calendarRoutes);

// ОБЯЗАТЕЛЬНО: Обработчики ошибок должны быть в конце согласно ТЗ
app.use('*', notFoundHandler);
app.use(errorHandler);

// Запуск сервера
const startServer = async () => {
  try {
    // Проверяем подключение к базе данных
    const dbConnected = await checkDatabaseConnection();
    if (!dbConnected) {
      throw new AppError('Database connection failed', 500);
    }
    
    // Проверяем обязательные переменные окружения
    const requiredEnvVars = ['JWT_SECRET', 'DATABASE_URL'];
    const missingVars = requiredEnvVars.filter(varName => !process.env[varName]);
    
    if (missingVars.length > 0) {
      throw new AppError(`Missing required environment variables: ${missingVars.join(', ')}`, 500);
    }

    // Инициализация CalDAV сервиса для календаря
    if (process.env.CALDAV_EMAIL && process.env.CALDAV_PASSWORD) {
      try {
        const { caldavCalendarService } = await import('./services/caldavCalendarService');
        await caldavCalendarService.setupSystemCredentials(
          process.env.CALDAV_EMAIL,
          process.env.CALDAV_PASSWORD
        );
        logger.info('CalDAV calendar service initialized successfully', {
          email: process.env.CALDAV_EMAIL
        });
      } catch (error) {
        logger.warn('Failed to initialize CalDAV calendar service', { error });
      }
    } else {
      logger.warn('CalDAV credentials not configured - calendar creation will not work');
    }
    
    app.listen(PORT, () => {
      logger.info('Server started successfully', {
        port: PORT,
        environment: process.env.NODE_ENV || 'development',
        nodeVersion: process.version,
        timestamp: new Date().toISOString()
      });
      
      console.log(`🚀 Server running on port ${PORT}`);
      console.log(`📚 Knowledge Base API ready`);
      console.log(`🔐 Authentication endpoints available at /api/auth`);
      console.log(`🏥 Health check available at /health`);
      
      if (process.env.NODE_ENV === 'development') {
        console.log(`📊 Prisma Studio: http://localhost:5555`);
        console.log(`🔍 API Base: http://localhost:${PORT}/api`);
      }
    });
    
  } catch (error) {
    logger.error('Failed to start server', { error });
    console.error('❌ Failed to start server:', error);
    process.exit(1);
  }
};

// Запускаем сервер
startServer();
