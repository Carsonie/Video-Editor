/**
 * Stage 1 — Generate voiceover from script (HeyGen Starfish TTS).
 *
 *   Input:  config/<slug>.json   (script text + voice settings)
 *   Output: audio/<slug>.mp3   +   metadata.json updated
 *
 * Run:
 *   npm run voiceover <slug>
 *   e.g. npm run voiceover first-time-ordering
 *
 * Standalone, manual stage — does not chain into Stage 2.
 */

import * as path from 'node:path';
import * as dotenv from 'dotenv';
dotenv.config({ path: path.resolve(__dirname, '..', '.env.local') });

import * as fs from 'node:fs';
import { clientFromEnv } from './lib/heygen';
import { audioPath, configPath, DIRS } from './lib/paths';
import {
  updateVideo,
  newVideoRecord,
  today,
  type VideoRecord,
} from './lib/metadata';

interface VideoConfig {
  slug: string;
  title: string;
  script: string;
  voice: {
    voice_id: string;
    speed?: number;
  };
  audio_out?: string;
}

function loadConfig(slug: string): VideoConfig {
  const file = configPath(slug);
  if (!fs.existsSync(file)) {
    throw new Error(`Config not found: ${file}`);
  }
  const raw = fs.readFileSync(file, 'utf8').trim();
  if (!raw) {
    throw new Error(`Config is empty: ${file}`);
  }
  const cfg = JSON.parse(raw) as VideoConfig;

  if (cfg.slug !== slug) {
    throw new Error(
      `Config slug "${cfg.slug}" does not match requested slug "${slug}".`
    );
  }
  if (!cfg.script?.trim()) throw new Error('Config `script` is empty.');
  if (!cfg.voice?.voice_id) throw new Error('Config `voice.voice_id` is required.');

  return cfg;
}

async function main(): Promise<void> {
  const slug = process.argv[2];
  if (!slug) {
    console.error('Usage: npm run voiceover <slug>');
    process.exit(1);
  }

  const cfg = loadConfig(slug);
  const outPath = cfg.audio_out
    ? cfg.audio_out
    : audioPath(slug);

  console.log(`[Stage 1] Generating voiceover for "${cfg.title}" (${slug})`);
  console.log(`          voice_id=${cfg.voice.voice_id} speed=${cfg.voice.speed ?? 1.0}`);

  const client = clientFromEnv();

  let result;
  try {
    result = await client.generateSpeech({
      text: cfg.script,
      voiceId: cfg.voice.voice_id,
      speed: cfg.voice.speed,
    });
  } catch (err) {
    // Record the failure in metadata, then surface it.
    updateVideo(
      slug,
      (r: VideoRecord) => {
        r.stages.voiceover.status = 'error';
        r.stages.voiceover.updated = today();
      },
      () => newVideoRecord(cfg.title, cfg.voice.voice_id)
    );
    throw err;
  }

  console.log(`          TTS ready: ${result.duration}s — downloading audio...`);

  const audio = await client.downloadAudio(result.audio_url);
  fs.mkdirSync(DIRS.audio, { recursive: true });
  fs.writeFileSync(outPath, audio);

  updateVideo(
    slug,
    (r: VideoRecord) => {
      r.voice_id = cfg.voice.voice_id;
      r.title = cfg.title;
      r.duration = result.duration;
      r.stages.voiceover.status = 'done';
      r.stages.voiceover.audio = outPath;
      r.stages.voiceover.updated = today();
    },
    () => newVideoRecord(cfg.title, cfg.voice.voice_id)
  );

  console.log(`[Stage 1] Done. Audio saved to ${outPath}`);
  console.log(`          metadata.json updated (duration=${result.duration}s).`);
}

main().catch((err) => {
  console.error('[Stage 1] Failed:', err instanceof Error ? err.message : err);
  process.exit(1);
});
