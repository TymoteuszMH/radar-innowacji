import type { Organization, PriorArt } from './common.interfaces';

interface CatalogItem {
  id: string;
  organization_id: string;
  title: string;
  solution?: string | null;
  is_demo: boolean;
  domain_tags?: string[];
  stage?: string;
  innovation_type?: string;
  prior_art?: PriorArt | null;
  assessment?: { status: string; score: number | null; coverage: number } | null;
}

export interface CatalogData {
  items: CatalogItem[];
  organizations: Organization[];
  total: number;
}

export interface CatalogView extends CatalogData {
  kind: 'innovations';
}