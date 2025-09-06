ИНСТРУКЦИИ ДЛЯ AI-АГЕНТА: Knowledge Base RAG MVP
🚨 КРИТИЧЕСКИЕ ПРИНЦИПЫ

НЕТ ВАРИАТИВНОСТИ: Каждое решение должно быть однозначным. Не предлагай варианты.
НЕТ КОСТЫЛЯМ: Лучше потратить время на правильное решение сейчас.
БЕЗОПАСНОСТЬ ПРЕВЫШЕ ВСЕГО: Каждый endpoint проверяет права доступа.
ФАКТЫ, НЕ МНЕНИЯ: Используй проверенные решения, не экспериментируй.

📁 СТРУКТУРА ПРОЕКТА
knowledge-base-mvp/
├── backend/
│   ├── src/
│   │   ├── controllers/      # Контроллеры (бизнес-логика)
│   │   ├── routes/           # Роуты Express
│   │   ├── services/         # Сервисы (работа с БД, внешние API)
│   │   ├── middlewares/      # JWT, права доступа, обработка ошибок
│   │   ├── utils/            # Вспомогательные функции
│   │   ├── types/            # TypeScript типы
│   │   ├── config/           # Конфигурация
│   │   └── index.ts          # Точка входа
│   ├── prisma/
│   │   ├── schema.prisma     # Схема БД
│   │   └── seed.ts           # Начальные данные
│   ├── uploads/              # Временные загруженные файлы
│   ├── package.json
│   ├── tsconfig.json
│   └── .env
├── worker/
│   ├── processors/           # Обработчики документов
│   │   ├── base_processor.py
│   │   ├── docx_processor.py
│   │   ├── csv_processor.py
│   │   └── json_processor.py
│   ├── services/
│   │   ├── embedding_service.py
│   │   ├── chunking_service.py
│   │   └── database_service.py
│   ├── celery_app.py        # Конфигурация Celery
│   ├── tasks.py              # Задачи Celery
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/       # Переиспользуемые компоненты
│   │   ├── pages/           # Страницы
│   │   ├── services/        # API клиент
│   │   ├── store/           # Zustand store
│   │   ├── hooks/           # Custom hooks
│   │   ├── types/           # TypeScript типы
│   │   ├── utils/           # Вспомогательные функции
│   │   └── App.tsx
│   ├── package.json
│   └── .env
├── docker-compose.yml
├── .gitignore
└── README.md
🔧 ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ
TypeScript (Backend & Frontend)
typescript// ВСЕГДА используй строгую типизацию
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
Обработка ошибок
typescript// ОБЯЗАТЕЛЬНО: Единый формат ошибок
class AppError extends Error {
  statusCode: number;
  isOperational: boolean;
  
  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
    this.isOperational = true;
  }
}

// ОБЯЗАТЕЛЬНО: Глобальный обработчик ошибок
app.use((err: AppError, req: Request, res: Response, next: NextFunction) => {
  const { statusCode = 500, message } = err;
  logger.error({ err, req });
  res.status(statusCode).json({
    success: false,
    error: message,
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});
Логирование
typescript// ИСПОЛЬЗУЙ winston для backend
import winston from 'winston';

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.json(),
  transports: [
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' })
  ]
});

// ЛОГИРУЙ: Все операции с БД, все ошибки, все обращения к внешним API
🔐 БЕЗОПАСНОСТЬ
1. Аутентификация
typescript// ОБЯЗАТЕЛЬНЫЕ проверки в КАЖДОМ защищенном endpoint
export const authenticate = async (req: Request, res: Response, next: NextFunction) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  
  if (!token) {
    throw new AppError('Unauthorized', 401);
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET!);
    req.user = await prisma.user.findUnique({ where: { id: decoded.id } });
    
    if (!req.user) {
      throw new AppError('User not found', 401);
    }
    
    next();
  } catch (error) {
    throw new AppError('Invalid token', 401);
  }
};
2. Проверка уровня доступа
typescript// КРИТИЧНО: Проверяй access_level ВЕЗДЕ
export const checkAccessLevel = (requiredLevel: number) => {
  return (req: Request, res: Response, next: NextFunction) => {
    if (req.user.accessLevel < requiredLevel) {
      throw new AppError('Insufficient access level', 403);
    }
    next();
  };
};

// В КАЖДОМ запросе к ChromaDB:
const results = await collection.query({
  where: { access_level: { $lte: user.accessLevel } }
});
3. Валидация входных данных
typescript// ИСПОЛЬЗУЙ joi для валидации
import Joi from 'joi';

const uploadSchema = Joi.object({
  title: Joi.string().min(3).max(255).required(),
  accessLevel: Joi.number().min(1).max(100).required()
});

// ВАЛИДИРУЙ ВСЁ
export const validate = (schema: Joi.Schema) => {
  return (req: Request, res: Response, next: NextFunction) => {
    const { error } = schema.validate(req.body);
    if (error) {
      throw new AppError(error.details[0].message, 400);
    }
    next();
  };
};
4. Пароли
typescript// ОБЯЗАТЕЛЬНО
const SALT_ROUNDS = 12;  // НЕ МЕНЬШЕ!
const password_hash = await bcrypt.hash(password, SALT_ROUNDS);

// Проверка сложности пароля
const passwordSchema = Joi.string()
  .min(8)
  .pattern(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])/);
🗄️ БАЗА ДАННЫХ
Prisma схема
prisma// ОБЯЗАТЕЛЬНЫЕ поля для ВСЕХ таблиц
model BaseModel {
  id        String   @id @default(uuid())
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

// ИНДЕКСЫ для производительности
@@index([accessLevel])
@@index([userId])
@@index([createdAt])
Миграции
bash# ВСЕГДА создавай миграцию при изменении схемы
npx prisma migrate dev --name descriptive_name

# НИКОГДА не используй
npx prisma db push  # Это для прототипов, не для продакшена!
🔍 ЭМБЕДДИНГИ И ПОИСК
КРИТИЧЕСКИЕ настройки
python# worker/config.py
class EmbeddingConfig:
    MODEL = 'intfloat/multilingual-e5-large'  # НЕ МЕНЯТЬ!
    DIMENSION = 1024                          # НЕ МЕНЯТЬ!
    MAX_SEQ_LENGTH = 512                      # НЕ МЕНЯТЬ!
    BATCH_SIZE = 32
    
    # ОБЯЗАТЕЛЬНЫЕ префиксы
    DOCUMENT_PREFIX = "passage: "
    QUERY_PREFIX = "query: "
    
    # ChromaDB настройки
    COLLECTION_NAME = "documents"
    DISTANCE_METRIC = "cosine"               # НЕ МЕНЯТЬ!
    
class ChunkingConfig:
    SIZE = 1000
    OVERLAP = 100
    MIN_SIZE = 200
    
    # ВАЖНО: Не обрезать посреди слова
    RESPECT_SENTENCE_BOUNDARY = True
Обработка документов
python# ОБЯЗАТЕЛЬНЫЙ порядок обработки
def process_document(file_path: str, doc_id: str, access_level: int):
    # 1. Извлечение текста
    text = extract_text(file_path)
    
    # 2. Очистка текста
    text = clean_text(text)  # Удаление лишних пробелов, спецсимволов
    
    # 3. Разбивка на чанки
    chunks = create_chunks(text)
    
    # 4. Создание метаданных для КАЖДОГО чанка
    for i, chunk in enumerate(chunks):
        metadata = {
            "doc_id": doc_id,
            "chunk_index": i,
            "access_level": access_level,  # КРИТИЧНО!
            "char_start": chunk.start,
            "char_end": chunk.end,
            "created_at": datetime.now().isoformat()
        }
        
        # 5. Создание эмбеддинга С ПРЕФИКСОМ
        embedding = model.encode(
            DOCUMENT_PREFIX + chunk.text,
            normalize_embeddings=True  # ОБЯЗАТЕЛЬНО!
        )
        
        # 6. Сохранение в ChromaDB
        collection.add(
            ids=[f"{doc_id}_{i}"],
            embeddings=[embedding],
            documents=[chunk.text],
            metadatas=[metadata]
        )
📝 API ENDPOINTS
Стандарты ответов
typescript// ВСЕГДА используй единый формат
interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  metadata?: {
    page?: number;
    total?: number;
    timestamp: string;
  };
}

// Успешный ответ
res.status(200).json({
  success: true,
  data: result,
  metadata: { timestamp: new Date().toISOString() }
});

// Ошибка
res.status(400).json({
  success: false,
  error: "Описание ошибки"
});
Обязательные middleware для КАЖДОГО endpoint
typescriptrouter.post('/documents/upload',
  authenticate,                    // 1. Проверка JWT
  checkAccessLevel(10),            // 2. Проверка прав
  validate(uploadSchema),          // 3. Валидация данных
  rateLimiter,                     // 4. Rate limiting
  uploadController.upload          // 5. Сам контроллер
);
🎨 FRONTEND
Структура компонентов
typescript// КАЖДЫЙ компонент в отдельном файле
// components/DocumentUpload/DocumentUpload.tsx
interface DocumentUploadProps {
  onSuccess: (doc: Document) => void;
  onError: (error: string) => void;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({ 
  onSuccess, 
  onError 
}) => {
  // ОБЯЗАТЕЛЬНО: loading и error states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // ОБЯЗАТЕЛЬНО: cleanup в useEffect
  useEffect(() => {
    return () => {
      // Очистка
    };
  }, []);
  
  return (
    // JSX
  );
};
API клиент
typescript// services/api.ts
class ApiClient {
  private baseURL = process.env.REACT_APP_API_URL;
  
  // ОБЯЗАТЕЛЬНО: Interceptor для токена
  constructor() {
    axios.interceptors.request.use((config) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
    
    // ОБЯЗАТЕЛЬНО: Обработка 401
    axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }
}
📋 ПОРЯДОК РАЗРАБОТКИ
Фаза 1: Инициализация (СТРОГО в этом порядке)

Создать структуру папок
Инициализировать package.json в каждой папке
Создать docker-compose.yml
Создать .env файлы
Проверить: docker-compose up -d

Фаза 2: Backend база

Настроить Prisma
Создать схему БД
Запустить миграции
Создать seed с админом
Проверить: npx prisma studio

Фаза 3: Аутентификация

JWT middleware
Login endpoint
Logout endpoint
Me endpoint
Проверить: Postman коллекция

Фаза 4: Upload документов

Multer настройка
Upload endpoint
Отправка в Redis
List documents endpoint
Проверить: Загрузка файла

Фаза 5: Worker

Celery конфигурация
DocxProcessor
Chunking service
Embedding service
Проверить: Чанки в БД после загрузки

Фаза 6: RAG

Search endpoint
ChromaDB query
Reranking
Ollama integration
Проверить: Ответ на вопрос по документу

Фаза 7: Frontend основа

React setup
Login page
Main layout
Chat interface
Проверить: Можно задать вопрос

Фаза 8: Frontend документы

Upload component
Documents list
Chunks preview
Chunks edit
Проверить: Полный цикл работы

⚠️ ЧАСТЫЕ ОШИБКИ (НЕ ДОПУСКАТЬ!)
❌ НЕ ДЕЛАЙ ТАК:
typescript// Без типов
const processData = (data) => { ... }

// Без обработки ошибок
const result = await prisma.user.findUnique({ where: { id } });
return result;  // А если null?

// Без проверки прав
router.get('/documents/:id', async (req, res) => {
  const doc = await prisma.document.findUnique({ where: { id } });
  res.json(doc);  // А права доступа?
});

// Синхронные операции в event loop
const bigFile = fs.readFileSync('huge.pdf');  // Блокирует!
✅ ДЕЛАЙ ТАК:
typescript// С типами
const processData = (data: DocumentData): ProcessedData => { ... }

// С обработкой ошибок
const result = await prisma.user.findUnique({ where: { id } });
if (!result) {
  throw new AppError('User not found', 404);
}
return result;

// С проверкой прав
router.get('/documents/:id', authenticate, async (req, res) => {
  const doc = await prisma.document.findUnique({ 
    where: { 
      id: req.params.id,
      accessLevel: { lte: req.user.accessLevel }
    } 
  });
  if (!doc) {
    throw new AppError('Document not found or access denied', 404);
  }
  res.json(doc);
});

// Асинхронные операции
const bigFile = await fs.promises.readFile('huge.pdf');
🧪 ТЕСТИРОВАНИЕ
После КАЖДОЙ фазы проверяй:
bash# Backend
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"Admin123!"}'

# Worker
celery -A celery_app worker --loglevel=info

# ChromaDB
curl http://localhost:8000/api/v1/collections

# Ollama
curl http://localhost:11434/api/tags
📊 МОНИТОРИНГ
Обязательные логи:

Все ошибки
Все операции с БД дольше 1 секунды
Все обращения к внешним API
Все операции с файлами
Все неудачные попытки аутентификации

Метрики для отслеживания:

Время обработки документа
Размер чанков
Количество чанков на документ
Время поиска
Качество ответов (добавить thumbs up/down)

🚀 ДЕПЛОЙ ПРОВЕРКИ
Перед каждым коммитом:
bash# TypeScript проверка
npm run type-check

# Линтер
npm run lint

# Тесты безопасности
npm audit

# Python проверка
pylint worker/
mypy worker/

# Docker health check
docker-compose ps
📌 КОНСТАНТЫ ПРОЕКТА
typescript// НЕ ИЗМЕНЯТЬ без согласования
export const CONSTANTS = {
  // Chunking
  CHUNK_SIZE: 1000,
  CHUNK_OVERLAP: 100,
  MIN_CHUNK_SIZE: 200,
  
  // Embedding
  EMBEDDING_MODEL: 'intfloat/multilingual-e5-large',
  EMBEDDING_DIMENSION: 1024,
  
  // Search
  SEARCH_TOP_K: 30,
  RERANK_TOP_K: 10,
  
  // Auth
  JWT_EXPIRY: '7d',
  BCRYPT_ROUNDS: 12,
  
  // Limits
  MAX_FILE_SIZE: 10 * 1024 * 1024,  // 10MB
  MAX_CHUNKS_PER_DOC: 1000,
  
  // Access levels
  ACCESS_LEVEL_MIN: 1,
  ACCESS_LEVEL_MAX: 100,
  ACCESS_LEVEL_DEFAULT: 50
};

ФИНАЛЬНАЯ ПРОВЕРКА: Если хоть один пункт не выполнен - система НЕ ГОТОВА к использованию.