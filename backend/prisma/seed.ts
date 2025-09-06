import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

const SALT_ROUNDS = 12; // Согласно ТЗ - НЕ МЕНЬШЕ 12!

async function main() {
  console.log('🌱 Starting seed...');

  try {
    // Create admin user
    const adminPasswordHash = await bcrypt.hash('Admin123!', SALT_ROUNDS);
    
    const admin = await prisma.user.upsert({
      where: { email: 'admin@test.com' },
      update: {},
      create: {
        email: 'admin@test.com',
        fullName: 'System Administrator',
        passwordHash: adminPasswordHash,
        accessLevel: 100, // Максимальный уровень доступа
        role: 'ADMIN',
      },
    });

    console.log('✅ Admin user created:', {
      id: admin.id,
      email: admin.email,
      fullName: admin.fullName,
      accessLevel: admin.accessLevel,
      role: admin.role
    });

    // Create test user with medium access level
    const userPasswordHash = await bcrypt.hash('User123!', SALT_ROUNDS);
    
    const user = await prisma.user.upsert({
      where: { email: 'user@test.com' },
      update: {},
      create: {
        email: 'user@test.com',
        fullName: 'Test User',
        passwordHash: userPasswordHash,
        accessLevel: 50, // Средний уровень доступа
        role: 'USER',
      },
    });

    console.log('✅ Test user created:', {
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      accessLevel: user.accessLevel,
      role: user.role
    });

    // Create low-level test user
    const lowUserPasswordHash = await bcrypt.hash('LowUser123!', SALT_ROUNDS);
    
    const lowUser = await prisma.user.upsert({
      where: { email: 'lowuser@test.com' },
      update: {},
      create: {
        email: 'lowuser@test.com',
        fullName: 'Low Access User',
        passwordHash: lowUserPasswordHash,
        accessLevel: 10, // Низкий уровень доступа
        role: 'USER',
      },
    });

    console.log('✅ Low access user created:', {
      id: lowUser.id,
      email: lowUser.email,
      fullName: lowUser.fullName,
      accessLevel: lowUser.accessLevel,
      role: lowUser.role
    });

    console.log('🎉 Seed completed successfully!');
    console.log('📋 Created users:');
    console.log('   Admin: admin@test.com / Admin123! (access level: 100)');
    console.log('   User:  user@test.com / User123! (access level: 50)');
    console.log('   Low:   lowuser@test.com / LowUser123! (access level: 10)');

  } catch (error) {
    console.error('❌ Error during seed:', error);
    throw error;
  }
}

main()
  .catch((e) => {
    console.error('❌ Seed failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
