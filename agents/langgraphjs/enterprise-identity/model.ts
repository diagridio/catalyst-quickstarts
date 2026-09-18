/**
 * A deterministic stand-in for a hosted chat model: a canned two-turn
 * conversation, so the demo is free, offline and identical on every run.
 *
 * Set OPENAI_API_KEY and DIAGRID_QUICKSTART_MODEL=openai for a real provider.
 */

import type { BaseLanguageModelInput } from '@langchain/core/language_models/base';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import type { BindToolsInput } from '@langchain/core/language_models/chat_models';
import { AIMessage, isToolMessage } from '@langchain/core/messages';
import type {
  AIMessageChunk,
  BaseMessage,
  ToolCall,
} from '@langchain/core/messages';
import type { ChatResult } from '@langchain/core/outputs';
import type { Runnable } from '@langchain/core/runnables';

const OPENAI_MODEL = 'gpt-4.1-mini';

/** One canned turn: either a tool request or a final answer, never both. */
interface CannedTurn {
  readonly content: string;
  readonly toolCalls: readonly ToolCall[];
}

/** Returns `firstTurn` until a tool has run, then `finalTurn`. */
class CannedToolCallingChatModel extends BaseChatModel {
  readonly modelName = 'canned-offline';

  readonly #firstTurn: CannedTurn;
  readonly #finalTurn: CannedTurn;

  constructor(firstTurn: CannedTurn, finalTurn: CannedTurn) {
    super({});
    this.#firstTurn = firstTurn;
    this.#finalTurn = finalTurn;
  }

  _llmType(): string {
    return 'canned-tool-calling';
  }

  /** Accepted and ignored: the canned tool call is already decided. */
  override bindTools(
    _tools: BindToolsInput[]
  ): Runnable<BaseLanguageModelInput, AIMessageChunk> {
    return this;
  }

  async _generate(messages: BaseMessage[]): Promise<ChatResult> {
    const toolHasRun = messages.some((message) => isToolMessage(message));
    const turn = toolHasRun ? this.#finalTurn : this.#firstTurn;
    // A fresh message on every call, never the stored turn itself: LangChain
    // stamps an `id` onto the message it returns, mutating it in place.
    const message = new AIMessage({
      content: turn.content,
      tool_calls: [...turn.toolCalls],
    });
    // `text` is required alongside the message, even on a tool-call-only turn.
    return { generations: [{ text: turn.content, message }] };
  }
}

/**
 * The canned two-turn conversation this quickstart runs on.
 *
 * The first turn asks for `someone@example.com`, which is nobody: the `tools`
 * node replaces it with the subject the middleware verified.
 */
export function buildCannedModel({ offline = false } = {}): BaseChatModel {
  const call: ToolCall = offline
    ? {
        name: 'my_bookings',
        args: { subject: 'someone@example.com' },
        id: 'call_my_bookings_1',
        type: 'tool_call',
      }
    : {
        name: 'account_summary',
        args: { account_id: 'ACME-1' },
        id: 'call_account_summary_1',
        type: 'tool_call',
      };
  const answer = offline
    ? 'You have two bookings: the Grand Ballroom on March 15th ' +
      '(9AM-1PM) and the Rooftop Terrace on March 22nd (6PM-11PM).'
    : 'Here is what the CRM returned for ACME-1.';

  return new CannedToolCallingChatModel(
    { content: '', toolCalls: [call] },
    { content: answer, toolCalls: [] }
  );
}

/**
 * Real provider on request, canned model otherwise. `@langchain/openai` is
 * imported dynamically, so the canned path needs no API key.
 */
export async function buildModel(offline: boolean): Promise<BaseChatModel> {
  if (process.env['DIAGRID_QUICKSTART_MODEL'] === 'openai') {
    const { ChatOpenAI } = await import('@langchain/openai');
    console.log(`Using OpenAI (${OPENAI_MODEL}).`);
    return new ChatOpenAI({ model: OPENAI_MODEL });
  }

  console.log(
    'Using the canned offline model: no API key needed and the answer is ' +
      'always the same. Set DIAGRID_QUICKSTART_MODEL=openai for a real provider.'
  );
  return buildCannedModel({ offline });
}
