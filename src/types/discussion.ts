export interface Discussion {
  id: number;
  bookTitle: string;
  author: string;
  discussionDate: Date;
  participants: string[];
  mainTopics: string[];
  summary: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface DiscussionFormData {
  bookTitle: string;
  author: string;
  discussionDate: Date;
  participants: string;
  mainTopics: string;
  summary: string;
}

export interface SearchParams {
  keyword?: string;
  startDate?: Date;
  endDate?: Date;
  searchType?: 'title' | 'author' | 'topic' | 'all';
} 