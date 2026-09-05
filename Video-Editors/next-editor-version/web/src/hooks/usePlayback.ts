import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Playback over EXTRACTED FRAMES, with the clip's own audio beside them.
 *
 * Paced against a clock, never incremented per tick, so the timer's own jitter
 * cannot accumulate into drift. A drifting preview is worse than none when the
 * whole point is judging timing.
 *
 * WHICH clock matters. When there IS audio, the AUDIO drives the frame: two
 * independent clocks drift apart, and the one thing this playback exists to
 * judge is whether picture and sound agree — so there must be only one clock,
 * and it has to be the one the ear is listening to. With no audio, or when the
 * browser refuses to advance the track, it falls back to the wall clock.
 *
 * A timer, not requestAnimationFrame: rAF is suspended entirely while a tab is
 * hidden, so playback would silently stall the moment you looked at something
 * else. A timer keeps running, throttled, and because the frame comes from a
 * clock it simply resumes in the right place.
 */
export interface Playback {
  playing: boolean;
  rate: number;
  muted: boolean;
  toggle: () => void;
  stop: () => void;
  setRate: (r: number) => void;
  setMuted: (m: boolean) => void;
  audioRef: React.RefObject<HTMLAudioElement | null>;
}

/** Browsers mute audio outside roughly 0.25x..4x, so below this the sound
 *  would go silent WITHOUT the clip being silent. Since the audio clock is also
 *  the frame clock here, a muted-but-running track is still a correct clock —
 *  but a track the browser refuses to advance is not. */
const AUDIO_RATE_FLOOR = 0.25;

export function usePlayback(opts: {
  frame: number;
  total: number;
  fps: number;
  hasAudio: boolean;
  /** Play only the zone, over and over. Judging a cut point is watching the
   *  same two seconds repeatedly, which is what this is for. */
  loopZone: null | { a: number; b: number };
  onFrame: (n: number) => void;
}): Playback {
  const { total, fps, hasAudio, loopZone, onFrame } = opts;
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [muted, setMuted] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Held in refs, not state: the tick reads them every 16ms and must not be a
  // reason to re-render.
  const t0 = useRef(0);
  const f0 = useRef(1);
  const frameRef = useRef(opts.frame);
  frameRef.current = opts.frame;
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;
  const zoneRef = useRef(loopZone);
  zoneRef.current = loopZone;

  const stop = useCallback(() => {
    setPlaying(false);
    const a = audioRef.current;
    if (a) a.pause();
  }, []);

  const toggle = useCallback(() => setPlaying((p) => !p), []);

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    a.muted = muted;
    // Outside the browser's supported window the rate is clamped rather than
    // refused, so the audio keeps a usable clock even where it goes silent.
    a.playbackRate = Math.max(AUDIO_RATE_FLOOR, Math.min(4, rate));
  }, [rate, muted]);

  useEffect(() => {
    if (!playing) return;
    const start = frameRef.current >= total ? 1 : frameRef.current;
    f0.current = start;
    t0.current = performance.now();
    const a = audioRef.current;
    if (a && hasAudio) {
      a.currentTime = (start - 1) / fps;
      void a.play().catch(() => {
        /* a refused play is not an error worth interrupting for — the wall
           clock takes over below and the picture still runs */
      });
    }

    const id = window.setInterval(() => {
      const zone = zoneRef.current;
      const lo = zone ? zone.a : 1;
      const hi = zone ? zone.b : total;

      let n: number;
      const au = audioRef.current;
      // The audio clock, when it is actually moving. `currentTime` standing
      // still is how a browser says it will not play at this rate.
      if (au && hasAudio && !au.paused && au.currentTime > 0) {
        n = Math.floor(au.currentTime * fps) + 1;
      } else {
        const elapsed = (performance.now() - t0.current) / 1000;
        n = f0.current + Math.floor(elapsed * fps * rate);
      }

      if (n > hi) {
        if (zone) {
          // wrap at the ZONE's edges, not the clip's
          f0.current = lo;
          t0.current = performance.now();
          if (au && hasAudio) au.currentTime = (lo - 1) / fps;
          n = lo;
        } else {
          onFrameRef.current(total);
          setPlaying(false);
          if (au) au.pause();
          return;
        }
      }
      if (n < lo) n = lo;
      onFrameRef.current(n);
    }, 16);

    return () => {
      window.clearInterval(id);
      const au = audioRef.current;
      if (au) au.pause();
    };
  }, [playing, total, fps, rate, hasAudio]);

  return { playing, rate, muted, toggle, stop, setRate, setMuted, audioRef };
}
