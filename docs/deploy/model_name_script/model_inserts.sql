-- Active: 1763784767296@@117.72.162.89@13306@agentlz
INSERT INTO `model` (`name`, `price`, `description`, `manufacturer`, `tags`) VALUES
('jina-embeddings-v4', '输入价格： ￥0.25 / M tokens输出价格： ￥0.25 / M tokens', '38 亿参数的通用向量模型 (embedding model)，用于多模态和多语言检索，支持单向量和多向量向量模型 (embedding) 输出。', 'Jina', '["向量"]'),
('jina-reranker-m0', '输入价格： ￥1.314 / M tokens输出价格： ￥1.314 / M tokens', '多模态重排序模型 Reranker模型。多模态多语言文档重排序模型，10K Tokens 上下文，2.4B 参数，用于包含图文的文档排序。', 'Jina', '["重排序"]'),
('jina-deepsearch-v1', '输入价格： ￥1.314 / M tokens输出价格： ￥1.314 / M tokens', 'DeepSearch 结合了搜索、阅读和推理能力，直到找到最佳答案。DeepSearch 完全兼容 OpenAI 的 Chat API 格式，最长上下文 1 M Tokens。 它默认的流式调用 (stream) 会返回思考过程，关闭则不输出思考部分。', 'Jina', '["联网搜索"]'),
('jina-embeddings-v2-base-code', '输入价格： ￥1.314 / M tokens输出价格： ￥1.314 / M tokens', '针对代码和文档搜索优化的向量嵌入embedding模型，768 维度，137M 参数。', 'Jina', '["向量"]'),
('jina-clip-v2', '输入价格： ￥1.35 / M tokens输出价格： ￥1.35 / M tokens', '多模态、多语言、1024 维、8K 上下文窗口、865M 参数', 'Jina', '["向量"]'),
('jina-embeddings-v3', '输入价格： ￥1.35 / M tokens输出价格： ￥1.35 / M tokens', '文本模型、多语言、1024 维、8K 上下文窗口、570M 参数', 'Jina', '["向量"]'),
('jina-colbert-v2', '输入价格： ￥1.35 / M tokens输出价格： ￥1.35 / M tokens', '多语言 ColBERT 模型，8K token 上下文，560M 参数，用于嵌入和重排序', 'Jina', '["重排序"]');