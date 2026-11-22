export interface ProjectSearchResult {
  project: {
    uuid: string;
    project_title: string;
    summary: string;
    source_title: string;
    url: string;
    contact_email: string;
    tags: string[];
    assessment: { score: number | null; coverage: number | null; status: string } | null;
  };
  matchedTerms: string[];
}
export interface DiscoveryState {
  online: ProjectSearchResult[] | null;
  onlineQuery: string;
}
export interface DiscoveryView { state: DiscoveryState; }