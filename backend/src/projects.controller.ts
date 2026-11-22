import { BadRequestException, Body, Controller, Get, NotFoundException, Param, Post, Query } from '@nestjs/common';
import { AssessmentService } from './assessment.service';
import { ProjectsService } from './projects.service';

@Controller()
export class ProjectsController {
  constructor(
    private readonly projects: ProjectsService,
    private readonly assessment: AssessmentService,
  ) {}

  @Get(['projects/search', 'api/projects/search'])
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

  @Get('api/innovations')
  catalog(@Query('q') query?: string) {
    if (query !== undefined && typeof query !== 'string') throw new BadRequestException('q musi byc tekstem.');
    return this.projects.catalog(query ?? '');
  }

  @Get('api/innovations/:id')
  innovation(@Param('id') id: string) {
    return this.projects.detail(id);
  }

  @Post('api/innovations/:id/analysis')
  async analyzeInnovation(@Param('id') id: string) {
    const detail = await this.projects.detail(id);
    const assessment = detail.assessment as { missing_questions?: unknown };
    const missing = Array.isArray(assessment?.missing_questions)
      ? assessment.missing_questions.filter((item): item is string => typeof item === 'string') : [];
    return this.assessment.analyze(detail.innovation.title, detail.innovation.solution, missing);
  }

  @Get('api/needs')
  needs() {
    return { items: [], organizations: [], total: 0 };
  }

  @Get('api/needs/:id')
  need() {
    throw new NotFoundException('Nie znaleziono potrzeby.');
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