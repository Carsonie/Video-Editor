/**
 * Shared folder + file path constants.
 *
 * Every stage resolves paths through here so there is a single source of
 * truth for the project layout. Paths are derived from a video's `slug`
 * (e.g. "first-time-ordering"), which is reused across config, source,
 * audio, and final — this is how stages know which files belong together
 * without a database.
 *
 * Layout note: each video's media lives under its own slug-namespaced
 * folder — videos/<slug>/source/ and videos/<slug>/final/. The on-disk
 * video folder uses underscores while config/ and audio/ keep the
 * hyphenated slug (slug "first-time-ordering" -> folder "first_time_ordering").
 */

import * as path from 'node:path';

/** Project root = the HeyGen folder (one level up from /scripts). */
export const ROOT = path.resolve(__dirname, '..', '..');

/** Top-level directories. */
export const DIRS = {
  config: path.join(ROOT, 'config'),
  audio: path.join(ROOT, 'audio'),
  videos: path.join(ROOT, 'videos'),
} as const;

/**
 * The video folder uses underscores even though the slug uses hyphens.
 * Only the video directory is converted; config/ and audio/ keep the slug.
 */
function videoFolder(slug: string): string {
  return slug.replace(/-/g, '_');
}

/** Per-video media directory: videos/<slug_with_underscores> */
export function videoDir(slug: string): string {
  return path.join(DIRS.videos, videoFolder(slug));
}

/** Single source of truth for per-video state. */
export const METADATA_FILE = path.join(ROOT, 'metadata.json');

/** Per-video config file: config/<slug>.json */
export function configPath(slug: string): string {
  return path.join(DIRS.config, `${slug}.json`);
}

/** HeyGen voiceover output: audio/<slug>.mp3 */
export function audioPath(slug: string): string {
  return path.join(DIRS.audio, `${slug}.mp3`);
}

/** OBS capture (Stage 2 input): videos/<slug>/source/<slug>.mp4 */
export function sourceVideoPath(slug: string): string {
  return path.join(videoDir(slug), 'source', `${slug}.mp4`);
}

/** Combined output (Stage 2 output): videos/<slug>/final/<slug>.mp4 */
export function finalVideoPath(slug: string): string {
  return path.join(videoDir(slug), 'final', `${slug}.mp4`);
}
