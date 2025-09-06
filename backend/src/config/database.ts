import { PrismaClient } from '@prisma/client';
import winston from 'winston';

// Создаем логгер согласно ТЗ
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/combined.log' }),
    ...(process.env.NODE_ENV !== 'production' ? [
      new winston.transports.Console({
        format: winston.format.combine(
          winston.format.colorize(),
          winston.format.simple()
        )
      })
    ] : [])
  ]
});

// T1.5: Создаем единственный экземпляр Prisma Client с connection pooling
const prisma = new PrismaClient({
  log: [
    {
      emit: 'event',
      level: 'query',
    },
    {
      emit: 'event',
      level: 'error',
    },
    {
      emit: 'event',
      level: 'info',
    },
    {
      emit: 'event',
      level: 'warn',
    },
  ],
  // T1.5: Настройки connection pooling
  datasources: {
    db: {
      url: process.env.DATABASE_URL + '?connection_limit=20&pool_timeout=20&socket_timeout=60'
    }
  }
});

// ОБЯЗАТЕЛЬНО: Логируем все операции с БД дольше 1 секунды согласно ТЗ
prisma.$on('query', (e) => {
  if (e.duration > 1000) {
    logger.warn('Slow database query detected', {
      query: e.query,
      params: e.params,
      duration: e.duration,
      timestamp: e.timestamp
    });
  }
});

// Логируем ошибки БД
prisma.$on('error', (e) => {
  logger.error('Database error occurred', {
    message: e.message,
    target: e.target,
    timestamp: e.timestamp
  });
});

// Логируем информационные сообщения
prisma.$on('info', (e) => {
  logger.info('Database info', {
    message: e.message,
    target: e.target,
    timestamp: e.timestamp
  });
});

// Логируем предупреждения
prisma.$on('warn', (e) => {
  logger.warn('Database warning', {
    message: e.message,
    target: e.target,
    timestamp: e.timestamp
  });
});

// Функция для проверки подключения к БД
export const checkDatabaseConnection = async (): Promise<boolean> => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    logger.info('Database connection successful');
    return true;
  } catch (error) {
    logger.error('Database connection failed', { error });
    return false;
  }
};

// Функция для graceful shutdown
export const disconnectDatabase = async (): Promise<void> => {
  try {
    await prisma.$disconnect();
    logger.info('Database disconnected successfully');
  } catch (error) {
    logger.error('Error disconnecting from database', { error });
  }
};

export { prisma, logger };
export default prisma;
