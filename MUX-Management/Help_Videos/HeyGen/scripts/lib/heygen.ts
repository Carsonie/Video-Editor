/**
 * Thin HeyGen API client (fetch wrapper).
 *
 * Verified against https://developers.heygen.com/docs/voices/speech (June 2026).
 *
 * Key facts baked in here:
 *  - Auth header is `X-Api-Key` (NOT `Authorization: Bearer`).
 *  - Standalone TTS uses the "Starfish" engine via POST /v3/voices/speech.
 *  - TTS is SYNCHRONOUS: the response carries `audio_url` directly, so no
 *    polling or webhook is needed for Stage 1.
 *  - TTS only works with Starfish-compatible voices. Find one with
 *    GET /v3/voices?engine=starfish before generating.
 *
 * Uses the built-in global `fetch` (Node 18+) — no HTTP dependency.
 */

const BASE_URL = 'https://api.heygen.com';

export interface HeyGenClientOptions {
  apiKey: string;
}

/** A voice as returned by GET /v3/voices. */
export interface Voice {
  voice_id: string;
  name?: string;
  language?: string;
  gender?: string;
  /** Whether the voice supports SSML <break> tags. */
  support_pause?: boolean;
  [key: string]: unknown;
}

/** Word-level timing entry from the TTS response. */
export interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

/** Parsed result of POST /v3/voices/speech. */
export interface SpeechResult {
  audio_url: string;
  duration: number;
  request_id: string | null;
  word_timestamps: WordTimestamp[] | null;
}

export interface GenerateSpeechParams {
  text: string;
  voiceId: string;
  /** 0.5–2.0, default 1.0. */
  speed?: number;
  /** "text" (default) or "ssml". */
  inputType?: 'text' | 'ssml';
  /** Base language code, e.g. "en". Auto-detected when omitted. */
  language?: string;
  /** BCP-47 locale, e.g. "en-US". Overrides `language` when set. */
  locale?: string;
}

export interface BrowseVoicesParams {
  /** Restrict to a TTS engine. Use "starfish" for standalone speech. */
  engine?: string;
  language?: string;
  gender?: string;
}

export class HeyGenError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: string
  ) {
    super(message);
    this.name = 'HeyGenError';
  }
}

export class HeyGenClient {
  private readonly apiKey: string;

  constructor(opts: HeyGenClientOptions) {
    if (!opts.apiKey) {
      throw new Error('HeyGen API key is required (set HEYGEN_API_KEY).');
    }
    this.apiKey = opts.apiKey;
  }

  private async request<T>(
    method: 'GET' | 'POST',
    pathname: string,
    body?: unknown
  ): Promise<T> {
    const res = await fetch(`${BASE_URL}${pathname}`, {
      method,
      headers: {
        'X-Api-Key': this.apiKey,
        'Content-Type': 'application/json',
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    const text = await res.text();
    if (!res.ok) {
      throw new HeyGenError(
        `HeyGen ${method} ${pathname} failed: ${res.status} ${res.statusText}`,
        res.status,
        text
      );
    }

    return (text ? JSON.parse(text) : {}) as T;
  }

  /**
   * Generate a standalone voiceover (Starfish TTS).
   * Returns the audio URL plus duration and word timings.
   */
  async generateSpeech(params: GenerateSpeechParams): Promise<SpeechResult> {
    const { text, voiceId, speed, inputType, language, locale } = params;

    if (!text || text.length < 1 || text.length > 5000) {
      throw new Error('TTS `text` must be 1–5,000 characters.');
    }
    if (speed !== undefined && (speed < 0.5 || speed > 2.0)) {
      throw new Error('TTS `speed` must be between 0.5 and 2.0.');
    }

    const payload: Record<string, unknown> = { text, voice_id: voiceId };
    if (speed !== undefined) payload.speed = speed;
    if (inputType) payload.input_type = inputType;
    if (language) payload.language = language;
    if (locale) payload.locale = locale;

    const json = await this.request<{ data: SpeechResult }>(
      'POST',
      '/v3/voices/speech',
      payload
    );
    return json.data;
  }

  /**
   * Browse voices. Pass `engine: "starfish"` to list only voices that
   * are compatible with standalone TTS.
   */
  async browseVoices(params: BrowseVoicesParams = {}): Promise<Voice[]> {
    const qs = new URLSearchParams();
    if (params.engine) qs.set('engine', params.engine);
    if (params.language) qs.set('language', params.language);
    if (params.gender) qs.set('gender', params.gender);

    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    const json = await this.request<{ data: { voices?: Voice[] } | Voice[] }>(
      'GET',
      `/v3/voices${suffix}`
    );

    // The API has historically nested voices under data.voices; tolerate both.
    const data = json.data as { voices?: Voice[] } | Voice[];
    if (Array.isArray(data)) return data;
    return data.voices ?? [];
  }

  /** Download the generated audio file to a Buffer. */
  async downloadAudio(audioUrl: string): Promise<Buffer> {
    const res = await fetch(audioUrl);
    if (!res.ok) {
      throw new HeyGenError(
        `Failed to download audio: ${res.status} ${res.statusText}`,
        res.status,
        await res.text().catch(() => '')
      );
    }
    const arrayBuffer = await res.arrayBuffer();
    return Buffer.from(arrayBuffer);
  }
}

/** Construct a client from the HEYGEN_API_KEY environment variable. */
export function clientFromEnv(): HeyGenClient {
  const apiKey = process.env.HEYGEN_API_KEY ?? '';
  return new HeyGenClient({ apiKey });
}
