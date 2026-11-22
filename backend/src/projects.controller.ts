import { BadRequestException, Body, Controller, Get, Post, Query } from '@nestjs/common';
import { AssessmentService } from './assessment.service';
import { ProjectsService } from './projects.service';

@Controller()
export class ProjectsController {
  constructor(
    private readonly projects: ProjectsService,
    private readonly assessment: AssessmentService,
  ) {}

  @Get('projects/search')
  search(@Query('q') query?: string, @Query('keywords') keywords?: string) {
    if ((query !== undefined && typeof query !== 'string') ||
        (keywords !== undefined && typeof keywords !== 'string')) {
      throw new BadRequestException('q i keywords musza byc tekstem.');
    }
    if (!/[\p{L}\p{N}]/u.test(`${query ?? ''} ${keywords ?? ''}`)) {
      throw new BadRequestException('Podaj q lub keywords.');
    }
    return this.projects.search(query ?? '', (keywords ?? '').split(','));
  }

  @Post('assessment')
  evaluate(@Body() body: unknown) {
    if (!body || typeof body !== 'object' || Array.isArray(body) || !('parameters' in body) ||
        !body.parameters || typeof body.parameters !== 'object' || Array.isArray(body.parameters)) {
      throw new BadRequestException('Podaj obiekt parameters.');
    }
    return this.assessment.evaluate(body.parameters as Record<string, unknown>);
  }
}