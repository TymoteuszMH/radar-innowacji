import { BadRequestException, Controller, Get, HttpException, HttpStatus, Ip, Param, Post, Query } from '@nestjs/common';
import { AssessmentService } from './assessment.service';
import { ProjectsService } from './projects.service';

/** Trasy HTTP katalogu, wyszukiwania, szczegolow i opcjonalnej analizy. */
@Controller()
export class ProjectsController {
  constructor(
    private readonly projects: ProjectsService,
    private readonly assessment: AssessmentService,
  ) {}

  /** Wyszukuje tekst projektu i slowa agenta; matchedTerms nie jest ocena trafnosci. */
  @Get('api/projects/search')
  search(@Query('q') query?: string, @Query('keywords') keywords?: string) {
    if ((query !== undefined && typeof query !== 'string') ||
        (keywords !== undefined && typeof keywords !== 'string')) {
      throw new BadRequestException('q i keywords musza byc tekstem.');
    }
    if ((query?.length ?? 0) > 180 || (keywords?.length ?? 0) > 500) {
      throw new BadRequestException('Zapytanie jest zbyt dlugie.');
    }
    if (!/[\p{L}\p{N}]/u.test(`${query ?? ''} ${keywords ?? ''}`)) {
      throw new BadRequestException('Podaj q lub keywords.');
    }
    return this.projects.search(query ?? '', (keywords ?? '').split(','));
  }

  /** Zwraca katalog, opcjonalnie filtrowany zapytaniem tekstowym. */
  @Get('api/innovations')
  catalog(@Query('q') query?: string) {
    if (query !== undefined && typeof query !== 'string') throw new BadRequestException('q musi byc tekstem.');
    if ((query?.length ?? 0) > 180) throw new BadRequestException('Zapytanie jest zbyt dlugie.');
    return this.projects.catalog(query ?? '');
  }

  /** Zwraca projekt, dowody, podobne rekordy i proponowane dalsze kroki. */
  @Get('api/innovations/:id')
  innovation(@Param('id') id: string) {
    return this.projects.detail(id);
  }

  /** Wywoluje opcjonalna analize OpenAI; nie zmienia zapisanej oceny. */
  @Post('api/innovations/:id/analysis')
  async analyzeInnovation(@Param('id') id: string, @Ip() clientIp: string) {
    const detail = await this.projects.detail(id);
    if (!this.assessment.allowAnalysis(clientIp)) {
      throw new HttpException('Limit analiz AI został osiągnięty. Spróbuj ponownie za 10 minut.', HttpStatus.TOO_MANY_REQUESTS);
    }
    const assessment = detail.assessment as { missing_questions?: unknown };
    const missing = Array.isArray(assessment?.missing_questions)
      ? assessment.missing_questions.filter((item): item is string => typeof item === 'string') : [];
    return this.assessment.analyze(detail.innovation.title, detail.innovation.solution, missing);
  }
}