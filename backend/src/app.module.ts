import { Module } from '@nestjs/common';
import { ProjectsController } from './projects.controller';
import { ProjectsService } from './projects.service';
import { AssessmentService } from './assessment.service';

@Module({
  controllers: [ProjectsController],
  providers: [ProjectsService, AssessmentService],
})
export class AppModule {}