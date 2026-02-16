-- Fase 0: Initial schema for Trading Agentic
-- Tables: sources, paper_extractions, strategies_found, trading_guides, agent_logs, chat_messages

-- sources
CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  url TEXT NOT NULL UNIQUE,
  title TEXT,
  authors TEXT,
  publication_year INTEGER,
  source_type TEXT CHECK (source_type IN ('paper', 'article', 'repo', 'book', 'video')) NOT NULL,
  relevance_score INTEGER CHECK (relevance_score BETWEEN 1 AND 10),
  credibility_score INTEGER CHECK (credibility_score BETWEEN 1 AND 10),
  applicability_score INTEGER CHECK (applicability_score BETWEEN 1 AND 10),
  overall_score INTEGER CHECK (overall_score BETWEEN 1 AND 10),
  tags TEXT[] DEFAULT '{}',
  summary TEXT,
  evaluation_reasoning TEXT,
  status TEXT CHECK (status IN (
    'pending', 'evaluating', 'approved', 'processing',
    'processed', 'rejected', 'error'
  )) DEFAULT 'pending',
  rejection_reason TEXT,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  evaluated_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_sources_status ON sources(status);
CREATE INDEX idx_sources_overall_score ON sources(overall_score DESC);
CREATE INDEX idx_sources_tags ON sources USING GIN(tags);

-- paper_extractions
CREATE TABLE paper_extractions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  strategies JSONB DEFAULT '[]',
  key_insights TEXT[] DEFAULT '{}',
  risk_warnings TEXT[] DEFAULT '{}',
  market_conditions TEXT[],
  data_period TEXT,
  sample_size TEXT,
  contradicts JSONB DEFAULT '[]',
  supports JSONB DEFAULT '[]',
  raw_summary TEXT,
  executive_summary TEXT,
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  processing_model TEXT,
  processing_tokens INTEGER,
  processed_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_extractions_source ON paper_extractions(source_id);
CREATE INDEX idx_extractions_confidence ON paper_extractions(confidence_score DESC);

-- strategies_found
CREATE TABLE strategies_found (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  extraction_id UUID NOT NULL REFERENCES paper_extractions(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  strategy_type TEXT CHECK (strategy_type IN (
    'momentum', 'mean_reversion', 'breakout', 'trend_following',
    'statistical_arbitrage', 'market_making', 'sentiment',
    'machine_learning', 'hybrid', 'other'
  )),
  market TEXT DEFAULT 'btc',
  timeframe TEXT,
  indicators TEXT[] DEFAULT '{}',
  entry_rules TEXT[] DEFAULT '{}',
  exit_rules TEXT[] DEFAULT '{}',
  position_sizing TEXT,
  backtest_results JSONB DEFAULT '{}',
  limitations TEXT[] DEFAULT '{}',
  best_market_conditions TEXT[],
  worst_market_conditions TEXT[],
  confidence INTEGER CHECK (confidence BETWEEN 1 AND 10),
  evidence_strength TEXT CHECK (evidence_strength IN ('weak', 'moderate', 'strong')),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_strategies_type ON strategies_found(strategy_type);
CREATE INDEX idx_strategies_market ON strategies_found(market);
CREATE INDEX idx_strategies_confidence ON strategies_found(confidence DESC);
CREATE INDEX idx_strategies_indicators ON strategies_found USING GIN(indicators);

-- trading_guides
CREATE TABLE trading_guides (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version INTEGER NOT NULL UNIQUE,
  based_on_sources INTEGER NOT NULL,
  based_on_strategies INTEGER NOT NULL,
  sources_used UUID[] DEFAULT '{}',
  primary_strategy JSONB NOT NULL,
  secondary_strategies JSONB DEFAULT '[]',
  market_conditions_map JSONB DEFAULT '{}',
  avoid_list TEXT[] DEFAULT '{}',
  risk_parameters JSONB DEFAULT '{}',
  full_guide_markdown TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  executive_summary TEXT,
  confidence_score INTEGER CHECK (confidence_score BETWEEN 1 AND 10),
  limitations TEXT[] DEFAULT '{}',
  changes_from_previous TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_guides_version ON trading_guides(version DESC);

-- agent_logs
CREATE TABLE agent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name TEXT NOT NULL CHECK (agent_name IN ('source', 'reader', 'synthesis', 'trading', 'chat')),
  action TEXT NOT NULL,
  source_id UUID REFERENCES sources(id),
  input_summary TEXT,
  output_summary TEXT,
  reasoning TEXT,
  tokens_input INTEGER,
  tokens_output INTEGER,
  tokens_used INTEGER,
  duration_ms INTEGER,
  model_used TEXT,
  estimated_cost_usd NUMERIC(10,6),
  status TEXT CHECK (status IN ('started', 'success', 'error', 'warning')),
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_logs_agent ON agent_logs(agent_name);
CREATE INDEX idx_logs_created ON agent_logs(created_at DESC);
CREATE INDEX idx_logs_source ON agent_logs(source_id);

-- chat_messages
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role TEXT CHECK (role IN ('user', 'assistant', 'system')) NOT NULL,
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chat_created ON chat_messages(created_at DESC);

-- RLS on all tables
ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies_found ENABLE ROW LEVEL SECURITY;
ALTER TABLE trading_guides ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Service role policies (backend full access)
CREATE POLICY "service_role_full_access" ON sources FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON paper_extractions FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON strategies_found FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON trading_guides FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON agent_logs FOR ALL USING (true);
CREATE POLICY "service_role_full_access" ON chat_messages FOR ALL USING (true);
