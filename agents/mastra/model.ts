/**
 * Model selection for the quickstart.
 *
 * Uses OpenAI by default (needs OPENAI_API_KEY). Set OLLAMA_ENDPOINT to run
 * against a local Ollama model instead — no API key or cost required. Both
 * forms are accepted directly by Mastra, so no @ai-sdk/* provider package is
 * needed either way.
 */

export type QuickstartModel = string | { id: `${string}/${string}`; url: string };

const OPENAI_MODEL = 'openai/gpt-4o-mini';
const DEFAULT_OLLAMA_MODEL = 'qwen3:0.6b';

export function resolveModel(): QuickstartModel {
  const ollamaEndpoint = process.env['OLLAMA_ENDPOINT'];
  if (ollamaEndpoint) {
    const model = process.env['OLLAMA_MODEL'] ?? DEFAULT_OLLAMA_MODEL;
    return { id: `ollama/${model}`, url: ollamaEndpoint };
  }
  return OPENAI_MODEL;
}

export function describeModel(model: QuickstartModel): string {
  return typeof model === 'string' ? model : `${model.id} @ ${model.url}`;
}
