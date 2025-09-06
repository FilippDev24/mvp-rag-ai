import { checkDatabaseConnection, prisma, logger } from './src/config/database';
import { CONSTANTS } from './src/types';

async function verifySetup() {
  console.log('🔍 Verifying Knowledge Base setup...\n');
  
  let allChecks = true;
  
  try {
    // 1. Проверка подключения к БД
    console.log('1️⃣  Checking database connection...');
    const isConnected = await checkDatabaseConnection();
    if (isConnected) {
      console.log('   ✅ Database connection: OK');
    } else {
      console.log('   ❌ Database connection: FAILED');
      allChecks = false;
    }
    
    // 2. Проверка структуры таблиц
    console.log('\n2️⃣  Checking database schema...');
    const expectedTables = ['users', 'documents', 'chunks', 'chat_sessions', 'messages'];
    
    for (const tableName of expectedTables) {
      try {
        const result = await prisma.$queryRaw`
          SELECT COUNT(*) as count 
          FROM information_schema.tables 
          WHERE table_name = ${tableName} AND table_schema = 'public'
        ` as Array<{ count: bigint }>;
        
        if (Number(result[0].count) > 0) {
          console.log(`   ✅ Table '${tableName}': EXISTS`);
        } else {
          console.log(`   ❌ Table '${tableName}': MISSING`);
          allChecks = false;
        }
      } catch (error) {
        console.log(`   ❌ Table '${tableName}': ERROR checking`);
        allChecks = false;
      }
    }
    
    // 3. Проверка пользователей
    console.log('\n3️⃣  Checking seed data...');
    const userCount = await prisma.user.count();
    if (userCount >= 3) {
      console.log(`   ✅ Users seeded: ${userCount} users found`);
      
      // Проверяем админа
      const admin = await prisma.user.findUnique({
        where: { email: 'admin@test.com' }
      });
      
      if (admin && admin.role === 'ADMIN' && admin.accessLevel === 100) {
        console.log('   ✅ Admin user: CONFIGURED CORRECTLY');
      } else {
        console.log('   ❌ Admin user: MISCONFIGURED');
        allChecks = false;
      }
    } else {
      console.log(`   ❌ Users seeded: Only ${userCount} users found (expected 3+)`);
      allChecks = false;
    }
    
    // 4. Проверка индексов
    console.log('\n4️⃣  Checking database indexes...');
    const indexes = await prisma.$queryRaw`
      SELECT 
        schemaname,
        tablename,
        indexname,
        indexdef
      FROM pg_indexes 
      WHERE schemaname = 'public' 
      AND indexname NOT LIKE '%_pkey'
      ORDER BY tablename, indexname
    ` as Array<{ tablename: string; indexname: string }>;
    
    const expectedIndexes = [
      'users_access_level_idx',
      'users_created_at_idx',
      'documents_access_level_idx',
      'documents_uploaded_by_idx',
      'chunks_access_level_idx',
      'chunks_document_id_idx'
    ];
    
    const foundIndexes = indexes.map(idx => idx.indexname);
    let indexesOk = true;
    
    for (const expectedIndex of expectedIndexes) {
      if (foundIndexes.includes(expectedIndex)) {
        console.log(`   ✅ Index '${expectedIndex}': EXISTS`);
      } else {
        console.log(`   ❌ Index '${expectedIndex}': MISSING`);
        indexesOk = false;
      }
    }
    
    if (indexesOk) {
      console.log('   ✅ All critical indexes: PRESENT');
    } else {
      console.log('   ❌ Some indexes: MISSING');
      allChecks = false;
    }
    
    // 5. Проверка констант
    console.log('\n5️⃣  Checking configuration constants...');
    console.log(`   📊 Chunk size: ${CONSTANTS.CHUNK_SIZE}`);
    console.log(`   📊 Chunk overlap: ${CONSTANTS.CHUNK_OVERLAP}`);
    console.log(`   📊 Embedding model: ${CONSTANTS.EMBEDDING_MODEL}`);
    console.log(`   📊 Max file size: ${CONSTANTS.MAX_FILE_SIZE / (1024 * 1024)}MB`);
    console.log(`   📊 Access levels: ${CONSTANTS.ACCESS_LEVEL_MIN}-${CONSTANTS.ACCESS_LEVEL_MAX}`);
    console.log('   ✅ Constants: LOADED');
    
    // 6. Проверка типов
    console.log('\n6️⃣  Checking TypeScript types...');
    try {
      // Простая проверка что типы импортируются
      const { AppError } = await import('./src/types');
      const testError = new AppError('Test error', 400);
      if (testError.statusCode === 400 && testError.isOperational === true) {
        console.log('   ✅ TypeScript types: WORKING');
      } else {
        console.log('   ❌ TypeScript types: MALFORMED');
        allChecks = false;
      }
    } catch (error) {
      console.log('   ❌ TypeScript types: IMPORT ERROR');
      allChecks = false;
    }
    
    // Финальный результат
    console.log('\n' + '='.repeat(50));
    if (allChecks) {
      console.log('🎉 SETUP VERIFICATION: ALL CHECKS PASSED');
      console.log('✅ Knowledge Base database is ready for use!');
      console.log('\n📋 Next steps:');
      console.log('   1. Start backend server: npm run dev');
      console.log('   2. Test authentication endpoints');
      console.log('   3. Test document upload');
      console.log('   4. Configure worker for document processing');
    } else {
      console.log('❌ SETUP VERIFICATION: SOME CHECKS FAILED');
      console.log('🔧 Please fix the issues above before proceeding');
      process.exit(1);
    }
    
  } catch (error) {
    console.error('❌ Verification failed with error:', error);
    logger.error('Setup verification failed', { error });
    process.exit(1);
  } finally {
    await prisma.$disconnect();
  }
}

// Запускаем проверку
verifySetup();
