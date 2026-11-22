export interface Organization {
  id: string;
  name: string;
}

export interface PriorArt {
  status: string;
  matches: { title: string; url: string; type: string; source: string }[];
}