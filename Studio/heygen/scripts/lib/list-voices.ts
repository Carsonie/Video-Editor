/**
 * Utility — list Starfish-compatible voices for standalone TTS.
 *
 * TTS (Stage 1) only works with voices on the "starfish" engine, so use
 * this to pick a `voice_id` to drop into a config file.
 *
 * Run:
 *   npm run voices                      # all starfish voices
 *   npm run voices English              # filter by language
 *   npm run voices English female       # filter by language + gender
 */

import * as path from 'node:path';
import * as dotenv from 'dotenv';
dotenv.config({ path: path.resolve(__dirname, '..', '..', '.env.local') });

import { clientFromEnv } from './heygen';

async function main(): Promise<void> {
  const language = process.argv[2];
  const gender = process.argv[3];

  const client = clientFromEnv();
  const voices = await client.browseVoices({
    engine: 'starfish',
    language,
    gender,
  });

  if (voices.length === 0) {
    console.log('No Starfish-compatible voices found for that filter.');
    return;
  }

  console.log(`Found ${voices.length} Starfish-compatible voice(s):\n`);
  for (const v of voices) {
    const bits = [
      v.voice_id,
      v.name ?? '(unnamed)',
      v.language ?? '',
      v.gender ?? '',
      v.support_pause ? 'ssml' : '',
    ]
      .filter(Boolean)
      .join('  |  ');
    console.log(bits);
  }
}

main().catch((err) => {
  console.error('Failed to list voices:', err instanceof Error ? err.message : err);
  process.exit(1);
});
