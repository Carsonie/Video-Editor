/**
 * metadata.json read/write helpers.
 *
 * metadata.json is the single source of truth for per-video state. Each
 * stage updates its own slice as it completes, so re-running one stage
 * never clobbers another's record. Plain JSON, version-control friendly.
 */

import * as fs from 'node:fs';
import { METADATA_FILE } from './paths';

export type StageStatus = 'pending' | 'done' | 'error';

export interface StageRecord {
  status: StageStatus;
  /** Output path produced by the stage, or null until done. */
  audio?: string | null;
  final?: string | null;
  /** ISO date of the last change to this stage. */
  updated: string | null;
}

export interface VideoRecord {
  title: string;
  script_version: number;
  voice_id: string;
  stages: {
    voiceover: StageRecord;
    combine: StageRecord;
  };
  /** Audio duration in seconds, captured from the HeyGen TTS response. */
  duration?: number | null;
  created: string;
  last_updated: string;
}

export interface Metadata {
  videos: Record<string, VideoRecord>;
}

const EMPTY: Metadata = { videos: {} };

/** Today's date as YYYY-MM-DD. */
export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Read metadata.json, returning an empty shell if missing or blank. */
export function readMetadata(): Metadata {
  try {
    const raw = fs.readFileSync(METADATA_FILE, 'utf8').trim();
    if (!raw) return structuredClone(EMPTY);
    return JSON.parse(raw) as Metadata;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
      return structuredClone(EMPTY);
    }
    throw err;
  }
}

/** Write metadata.json with stable 2-space formatting + trailing newline. */
export function writeMetadata(meta: Metadata): void {
  fs.writeFileSync(METADATA_FILE, JSON.stringify(meta, null, 2) + '\n', 'utf8');
}

/** Get one video's record, or undefined if it doesn't exist yet. */
export function getVideo(slug: string): VideoRecord | undefined {
  return readMetadata().videos[slug];
}

/**
 * Apply a mutation to one video's record and persist it.
 * Creates the record from `init` if it doesn't exist yet.
 */
export function updateVideo(
  slug: string,
  mutate: (record: VideoRecord) => void,
  init?: () => VideoRecord
): VideoRecord {
  const meta = readMetadata();
  let record = meta.videos[slug];

  if (!record) {
    if (!init) {
      throw new Error(
        `No metadata record for "${slug}" and no initializer provided.`
      );
    }
    record = init();
    meta.videos[slug] = record;
  }

  mutate(record);
  record.last_updated = today();
  writeMetadata(meta);
  return record;
}

/** Build a fresh, all-pending record for a new video. */
export function newVideoRecord(title: string, voiceId: string): VideoRecord {
  const date = today();
  return {
    title,
    script_version: 1,
    voice_id: voiceId,
    stages: {
      voiceover: { status: 'pending', audio: null, updated: null },
      combine: { status: 'pending', final: null, updated: null },
    },
    duration: null,
    created: date,
    last_updated: date,
  };
}
