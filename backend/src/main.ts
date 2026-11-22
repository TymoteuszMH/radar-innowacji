import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);
  const origins = (process.env.CORS_ORIGINS || 'http://localhost:4200,http://127.0.0.1:4200')
    .split(',').map((origin) => origin.trim()).filter(Boolean);
  app.enableCors({ origin: origins });
  await app.listen(process.env.PORT ?? 3000);
}

void bootstrap();