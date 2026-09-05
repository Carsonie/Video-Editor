import { Box } from '@mantine/core';

import { audioUrl, frameUrl } from '../api';

/**
 * The frame you are looking at.
 *
 * Every position shown is a REAL DECODED FRAME, not a player's seek. This
 * project has hit more than one bug caused by trusting a video element's seek
 * instead of extracting the actual frame and looking at it, which is the whole
 * reason the tool works this way.
 *
 * The audio element is here rather than in the playback hook because it has to
 * be in the tree to have a src — but it drives the frame clock, so the hook
 * holds the ref.
 */
export function Stage({
  slug,
  frame,
  ext,
  ver,
  w,
  h,
  marked,
  hasAudio,
  audioRef,
}: {
  slug: string;
  frame: number;
  ext: string;
  ver: number;
  w: number;
  h: number;
  marked: boolean;
  hasAudio: boolean;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}) {
  return (
    <Box className="stage" w={w} h={h}>
      <img src={frameUrl(slug, frame, ext, ver)} width={w} height={h} alt="" />
      {marked && <div className="markOverlay" />}
      {hasAudio && <audio ref={audioRef} src={audioUrl(slug)} preload="auto" />}
    </Box>
  );
}
