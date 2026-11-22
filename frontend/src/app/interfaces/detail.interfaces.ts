import type { Organization, PriorArt } from './common.interfaces';

interface Entity {
  id: string;
  title: string;
  organization_id: string;
  problem: string;
  is_demo: boolean;
  domain_tags?: string[];
}
interface Innovation extends Entity {
  solution: string;
  keywords?: string[];
  stage: string;
  target_groups?: string[];
  claimed_impact?: string;
  requirements?: string;
  source_mode?: string;
  source_url?: string;
  source_provider?: string;
  source_published_at?: string;
  source_retrieved_at?: string;
  prior_art?: PriorArt | null;
  people?: { name: string }[];
  contact_email?: string;
}
interface Action { title: string; reason: string; success_check: string; }
interface Assessment {
  score: number | null;
  coverage: number;
  status: string;
  disclaimer: string;
  missing_questions: string[];
  recommendation?: string;
  dimensions: { label: string; weight: number; grade: number | null; reason: string; evidence?: string[] }[];
}
interface Evidence {
  field: string;
  source_name: string;
  line_number?: number;
  quote: string;
  source_url?: string;
}
export type DetailView = {
  kind: 'innovation';
  innovation: Innovation;
  organizations: Organization[];
  assessment: Assessment;
  similar: { innovation: Innovation; similarity_score: number; reasons: string[] }[];
  actions: Action[];
  evidence: { records: Evidence[]; disclaimer: string };
};