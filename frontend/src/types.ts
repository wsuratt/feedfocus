export interface Insight {
  id: number;
  url: string;
  source_name: string;
  date_crawled: string;
  behavioral_shifts: string[];
  tech_unlocks: string[];
  market_gaps: string[];
  timing_signals: string[];
  convergence: string[];
}

export interface Source {
  id: number;
  url: string;
  source_name: string;
  date_crawled: string;
}

export interface CrossSourcePattern {
  pattern: string;
  supporting_sources: string[];
  opportunity: string;
  why_now: string;
}

export interface EmergingOpportunity {
  opportunity: string;
  evidence: string;
  action: string;
}

export interface AggregateAnalysis {
  cross_source_patterns: CrossSourcePattern[];
  emerging_opportunities: EmergingOpportunity[];
}

export interface Stats {
  total_insights: number;
  unique_sources: number;
  latest_crawl: string;
}
