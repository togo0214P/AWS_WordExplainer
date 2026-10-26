export interface Category {
  id: number;
  name: string;
}

export interface Entry {
  id: number;
  word: string;
  category_id: number;
  explanation: string;
}

export interface Candidate {
  word: string;
  category_id: number;
  category: string;
  explanation: string;
}
