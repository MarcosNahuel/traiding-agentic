-- Seed data for development
-- Insert a sample source for testing

INSERT INTO sources (url, title, source_type, status, tags)
VALUES (
  'https://arxiv.org/abs/example-paper',
  'Sample: Bitcoin Trading Strategy Using Moving Averages',
  'paper',
  'pending',
  ARRAY['bitcoin', 'moving-averages', 'sample']
)
ON CONFLICT (url) DO NOTHING;
