// Based on the data structure from web_server.py and scraper.py

export interface ProductInfo {
  "title": string;
  "price": string;
  "original_price"?: string;
  "want_count"?: string | number;
  "tags"?: string[];
  "shipping_area"?: string;
  "seller_nickname"?: string;
  "link": string;
  "publish_time"?: string;
  "item_id": string;
  "images"?: string[];
  "main_image"?: string;
  "description"?: string;
  "view_count"?: string | number;
  "status"?: string;
  "sold_count"?: string | number;
  "favorite_count"?: string | number;
  "seller_total_sold"?: string | number;
}

export interface SellerInfo {
  "seller_nickname"?: string;
  "seller_avatar"?: string;
  "seller_bio"?: string;
  "seller_listing_counts"?: string | number;
  "seller_rating_total"?: string;
  "seller_credit_level"?: string;
  "buyer_credit_level"?: string;
  "seller_zhima_credit"?: string;
  "seller_registered_years"?: string;
  "seller_good_ratings"?: string;
  "seller_good_rate"?: string;
  "buyer_good_ratings"?: string;
  "buyer_good_rate"?: string;
  "seller_items"?: any[]; // Define more strictly if needed
  "seller_ratings"?: any[]; // Define more strictly if needed
}

export interface AiAnalysis {
  is_recommended: boolean;
  reason: string;
  analysis_source?: 'ai' | 'keyword';
  keyword_hit_count?: number;
  value_score?: number;
  value_summary?: string;
  prompt_version?: string;
  risk_tags?: string[];
  criteria_analysis?: Record<string, any>;
  matched_keywords?: string[];
  backfilled_at?: string;
  error?: string;
}

export interface PriceInsight {
  observation_count: number;
  current_price?: number | null;
  avg_price?: number | null;
  median_price?: number | null;
  min_price?: number | null;
  max_price?: number | null;
  market_avg_price?: number | null;
  market_median_price?: number | null;
  price_change_amount?: number | null;
  price_change_percent?: number | null;
  deal_score?: number | null;
  deal_label?: string;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface ResultInsights {
  market_summary: {
    sample_count: number;
    avg_price: number | null;
    median_price: number | null;
    min_price: number | null;
    max_price: number | null;
    snapshot_time?: string | null;
  };
  history_summary: {
    unique_items: number;
    sample_count: number;
    avg_price: number | null;
    median_price: number | null;
    min_price: number | null;
    max_price: number | null;
  };
  daily_trend: Array<{
    day: string;
    sample_count: number;
    avg_price: number | null;
    median_price: number | null;
    min_price: number | null;
    max_price: number | null;
  }>;
  latest_snapshot_at?: string | null;
}

export interface ResultItem {
  "crawl_time": string;
  "keyword": string;
  "task_name": string;
  "item_info": ProductInfo;
  "seller_info": SellerInfo;
  ai_analysis: AiAnalysis;
  price_insight?: PriceInsight;
  _meta?: {
    id: number;
    result_filename: string;
    item_id: string;
    is_recommended: boolean;
    analysis_source: string | null;
    status: string | null;
    crawl_time: string | null;
    price?: number | null;
    initial_price?: number | null;
    last_checked_at?: string | null;
  };
  _status?: 'active' | 'hidden' | 'expired';
  _effective_hidden?: boolean;
  _hidden_reason?: 'manual' | 'rule' | 'expired' | null;
  _matched_blacklist_keywords?: string[];
  _initial_price?: number | null;
  _current_price?: number | null;
  _last_checked_at?: string | null;
}
