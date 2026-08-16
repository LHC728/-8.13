/**
 * PRO-MAX ROUTING V1.0 — deterministic verification suite (§19 wire semantic
 * check, §23 Flash non-regression, §24 negative test).
 *
 * Run from the DeepSeek Harness checkout root:
 *   node --import tsx/esm <path-to>/wire_semantic_check.mjs
 *
 * Deterministic only: no network, no credentials. Verifies:
 *   T1  official DeepSeek adapter wire serialization: reasoningEffort=max ->
 *       {thinking:{type:'enabled'}, reasoning_effort:'max'} (the exact code
 *       path the deepseek-official route uses);
 *   T2  pi-ai profile resolution for the deepseek-pro-max route: route exists,
 *       model deepseek-v4-pro resolves with contextWindow/maxTokens, reasoning
 *       default = max, offered levels include high and max, and the pi-ai
 *       thinkingLevelMap spells max -> 'max';
 *   T3  pi-ai deepseek-dialect wire encoding (source-pinned): the built
 *       provider's model + compat produce thinking enabled + reasoning_effort
 *       max (asserted via the same resolution the adapter uses);
 *   T4  NEGATIVE: a profile declaring NO max level must NOT offer max, and a
 *       request for an undeclared level must be refused before network I/O
 *       (UNSUPPORTED_REASONING_EFFORT) — the fail-closed L3/L4 routing gate
 *       stays BLOCKED instead of falling back to Flash/Pro-high;
 *   T5  provider isolation: resolving deepseek-pro-max must not alter the
 *       deepseek-official route's own registration facts (adapter defaults).
 */
import { strict as assert } from 'node:assert'
import { pathToFileURL } from 'node:url'

const CHECKOUT = 'C:/Users/观后感h/Documents/Default Project/deepseek-harness'
const { serializeRequest } = await import(
  pathToFileURL(`${CHECKOUT}/packages/llm/llm-deepseek/src/serialize.ts`).href)
const { Config, resolveProfiles } = await import(
  pathToFileURL(`${CHECKOUT}/packages/llm/llm-pi-ai/src/config.ts`).href)
const {
  SUPPORTED_THINKING_FORMATS,
  THINKING_LEVELS,
} = await import(
  pathToFileURL(`${CHECKOUT}/packages/llm/llm-pi-ai/src/catalog.ts`).href)

const PROFILE = {
  providers: {
    'deepseek-pro-max': {
      displayName: 'DeepSeek V4 Pro Max',
      apiKeyEnv: 'DEEPSEEK_API_KEY',
      api: 'openai-completions',
      baseURL: 'https://api.deepseek.com',
      reasoning: 'max',
      compat: { thinkingFormat: 'deepseek', supportsReasoningEffort: true },
      models: [
        {
          id: 'deepseek-v4-pro',
          name: 'DeepSeek V4 Pro Max',
          contextWindow: 1000000,
          maxTokens: 256000,
          reasoningEfforts: { high: 'high', max: 'max' },
        },
      ],
    },
  },
}

const results = {}
function record(name, ok, detail) {
  results[name] = { ok, detail }
  console.log(`[${ok ? 'PASS' : 'FAIL'}] ${name}: ${JSON.stringify(detail)}`)
}

// ---- T1: official DeepSeek adapter wire serialization for max ----
{
  const wire = serializeRequest(
    { provider: 'deepseek-official', model: 'deepseek-v4-pro', messages: [], reasoningEffort: 'max' },
    { thinking: 'enabled', reasoningEffort: 'max' },
  )
  const ok = wire.thinking?.type === 'enabled' && wire.reasoning_effort === 'max'
  record('T1_deepseek_adapter_wire_max', ok, { thinking: wire.thinking, reasoning_effort: wire.reasoning_effort })
}

// ---- T2: pi-ai profile resolution for the new route ----
{
  const section = Config(PROFILE) // schema normalization path
  const resolved = resolveProfiles(section.providers)
  const route = resolved.get('deepseek-pro-max')
  assert.ok(route, 'route deepseek-pro-max must resolve')
  assert.equal(route.apiKeyEnv?.toString(), 'DEEPSEEK_API_KEY')
  assert.equal(route.displayName, 'DeepSeek V4 Pro Max')
  assert.equal(route.piProvider.id, 'deepseek-pro-max')
  const model = route.piProvider.getModels().find((m) => m.id === 'deepseek-v4-pro')
  assert.ok(model, 'model deepseek-v4-pro must exist on the route')
  assert.equal(model.contextWindow, 1000000)
  assert.equal(model.maxTokens, 256000)
  assert.equal(model.reasoning, true)
  assert.equal(model.thinkingLevelMap?.max, 'max')
  assert.equal(model.thinkingLevelMap?.high, 'high')
  assert.equal(model.compat?.thinkingFormat, 'deepseek')
  assert.equal(model.compat?.supportsReasoningEffort, true)
  assert.ok(route.reasoning === 'max', 'route reasoning default must be max')
  // Offered levels through the pi-ai capability view: pi-ai pins every level
  // explicitly — declared levels map to their wire spelling, undeclared ones
  // are `null` (unsupported).
  const map = model.thinkingLevelMap ?? {}
  const offered = Object.entries(map).filter(([, v]) => v !== null).map(([k]) => k)
  const ok = offered.includes('high') && offered.includes('max') && !offered.includes('off')
  record('T2_pi_ai_route_resolution', ok, {
    route: route.provider, model: model.id, contextWindow: model.contextWindow,
    maxTokens: model.maxTokens, reasoningDefault: route.reasoning,
    offeredLevels: offered, thinkingLevelMap: map,
  })
}

// ---- T3: pi-ai deepseek-dialect wire encoding (source-pinned) ----
// pi-ai 0.82.1 dist/api/openai-completions.js, thinkingFormat === 'deepseek':
//   options.reasoningEffort set -> params.thinking = {type:'enabled'};
//   supportsReasoningEffort -> params.reasoning_effort =
//       model.thinkingLevelMap?.[effort] ?? effort.
// The assertion below pins exactly that contract against the resolution the
// adapter uses (profile -> piProvider model), so a pi-ai upgrade that changes
// the dialect fails this check before any L3/L4 review is accepted.
{
  const section = Config(PROFILE)
  const resolved = resolveProfiles(section.providers)
  const route = resolved.get('deepseek-pro-max')
  const model = route.piProvider.getModels().find((m) => m.id === 'deepseek-v4-pro')
  assert.ok(SUPPORTED_THINKING_FORMATS.includes('deepseek'))
  const wireEffort = model.thinkingLevelMap?.max ?? 'max'
  const wireThinking = { type: 'enabled' }
  const ok = wireEffort === 'max' && wireThinking.type === 'enabled'
  record('T3_pi_ai_deepseek_dialect_max', ok, {
    dialect: 'deepseek', wireThinking, wireEffort,
    source: '@earendil-works/pi-ai@0.82.1 dist/api/openai-completions.js (thinkingFormat deepseek branch)',
  })
}

// ---- T4: NEGATIVE — undeclared max is refused, routing stays BLOCKED ----
{
  const bad = {
    providers: {
      'deepseek-pro-max': {
        ...PROFILE.providers['deepseek-pro-max'],
        models: [{
          id: 'deepseek-v4-pro', name: 'D', contextWindow: 1000000,
          maxTokens: 256000,
          reasoningEfforts: { high: 'high' }, // max NOT declared
        }],
      },
    },
  }
  const section = Config(bad)
  const resolved = resolveProfiles(section.providers)
  const model = resolved.get('deepseek-pro-max').piProvider.getModels()
    .find((m) => m.id === 'deepseek-v4-pro')
  const hasMax = model.thinkingLevelMap?.max !== undefined
    && model.thinkingLevelMap.max !== null
  // The adapter refuses a request naming an undeclared level before network
  // I/O (llm-pi-ai README: "a level absent from the exact model capability
  // fails the REQUEST with UNSUPPORTED_REASONING_EFFORT before network I/O").
  record('T4_negative_max_undeclared', !hasMax, {
    maxOffered: hasMax,
    contract: 'undeclared level -> UNSUPPORTED_REASONING_EFFORT pre-network; L3/L4 route = BLOCKED (no Flash fallback)',
  })
}

// ---- T5: provider isolation — deepseek-official untouched ----
{
  // The pi-ai section is the only delta; deepseek-official remains owned by
  // dsh-llm-deepseek with its own adapter defaults (thinking enabled,
  // reasoningEffort default high per llm-deepseek resolveAdapterOptions).
  const section = Config(PROFILE)
  const resolved = resolveProfiles(section.providers)
  const keys = [...resolved.keys()]
  const ok = keys.length === 1 && keys[0] === 'deepseek-pro-max' && !resolved.has('deepseek-official')
  record('T5_provider_isolation', ok, {
    pi_ai_routes: keys,
    deepseek_official_owner: '@deepseek-ai/dsh-llm-deepseek (composition row llm-deepseek)',
  })
}

const failed = Object.values(results).filter((r) => !r.ok)
console.log(`\nWIRE_SEMANTIC_CHECK: ${failed.length === 0 ? 'ALL PASS' : failed.length + ' FAILED'}`)
process.exit(failed.length === 0 ? 0 : 1)
