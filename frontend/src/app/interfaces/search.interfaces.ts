/** Typy odpowiedzi wyszukiwarki i stanu wspolne dla ekranu oraz adaptera API. */
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

export interface SearchState {
  results: ProjectSearchResult[] | null;
  query: string;
}

export interface SearchView { state: SearchState; }