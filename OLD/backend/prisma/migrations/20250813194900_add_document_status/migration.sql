-- CreateEnum
CREATE TYPE "DocumentStatus" AS ENUM ('pending', 'processing', 'completed', 'error');

-- AlterTable
ALTER TABLE "documents" ADD COLUMN     "processed_at" TIMESTAMP(3),
ADD COLUMN     "status" "DocumentStatus" NOT NULL DEFAULT 'pending';

-- CreateIndex
CREATE INDEX "documents_status_idx" ON "documents"("status");
