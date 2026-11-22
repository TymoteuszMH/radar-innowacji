import { Injectable } from '@nestjs/common';

@Injectable()
export class AssessmentService {
  evaluate(parameters: Record<string, unknown>): {
    status: 'criteria_not_configured';
    score: null;
    parameters: Record<string, unknown>;
  } {
    return { status: 'criteria_not_configured', score: null, parameters };
  }
}