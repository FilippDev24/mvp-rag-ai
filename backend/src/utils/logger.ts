import winston from 'winston';

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'knowledge-base-backend' },
  transports: [
    // Основной транспорт - консоль (для всех сред)
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.colorize({ all: true }),
        winston.format.printf(({ timestamp, level, message, service, ...meta }) => {
          const metaStr = Object.keys(meta).length ? JSON.stringify(meta, null, 2) : '';
          return `${timestamp} [${service}] ${level}: ${message} ${metaStr}`;
        })
      )
    })
  ]
});

// Дополнительно в файлы только в development (для локальной отладки)
if (process.env.NODE_ENV === 'development') {
  logger.add(new winston.transports.File({ 
    filename: 'logs/error.log', 
    level: 'error',
    maxsize: 5242880, // 5MB
    maxFiles: 5,
    format: winston.format.json()
  }));
  
  logger.add(new winston.transports.File({ 
    filename: 'logs/combined.log',
    maxsize: 5242880, // 5MB
    maxFiles: 5,
    format: winston.format.json()
  }));
}

export { logger };
