import { useLayoutEffect, useRef, useState } from 'react';
import { Box, Tooltip } from '@mantine/core';

export interface Segment {
  n: number;
  start: number;
  end: number;
  frames: number;
  dur: number;
}

/**
 * The timeline: what Cut would write, the position, and the break points.
 *
 * Three strips, in the order you read them:
 *
 *   segbar   one band per segment Cut would produce, drawn over the frames it
 *            covers. Says the same thing the segment list says, in a shape you
 *            can point at.
 *   slider   the position. A native range input, kept rather than replaced
 *            because it already does keyboard, drag, click-to-position and
 *            accessibility correctly — and this control needs all four.
 *   ticks    the break points, clickable. Checking a cut means visiting every
 *            boundary in turn, and without these that is a manual scrub
 *            through thousands of frames.
 *
 * It has a ROW TO ITSELF. The durations drawn over the bar are only readable
 * if the bar is wide, and a slider sharing a row with eight step buttons is not.
 */
export function Timeline({
  frame,
  total,
  segments,
  marks,
  onFrame,
  fmtTime,
}: {
  frame: number;
  total: number;
  segments: Segment[];
  marks: number[];
  onFrame: (n: number) => void;
  fmtTime: (n: number) => string;
}) {
  const barRef = useRef<HTMLDivElement>(null);
  const [barW, setBarW] = useState(0);

  // The "does this label fit?" test is measured in PIXELS, so it has to be
  // re-run whenever the bar's width changes.
  useLayoutEffect(() => {
    const el = barRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setBarW(el.clientWidth));
    ro.observe(el);
    setBarW(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // A frame's position as a fraction. Frame 1 sits at 0 and frame N at 1,
  // matching where the slider's own thumb lands, so a tick and the thumb agree.
  const pos = (f: number) => (total <= 1 ? 0 : (f - 1) / (total - 1));

  const here = segments.find((s) => frame >= s.start && frame <= s.end);

  return (
    <div className="sliderWrap">
      <div className="segbar" ref={barRef}>
        {segments.map((s) => {
          const left = pos(s.start) * barW;
          const right = pos(s.end) * barW;
          const width = Math.max(3, right - left);
          const label = `${s.n} · ${s.dur.toFixed(2)}s`;
          // ~5.6px per character at 10px. A label that does not fit is dropped
          // rather than clipped: half a number is worse than none.
          const fits = width > label.length * 5.6 + 8;
          return (
            <Tooltip
              key={s.n}
              label={`Segment ${s.n}: frames ${s.start}–${s.end} · ${s.frames} frames · ${s.dur.toFixed(3)}s`}
            >
              <div
                className={`segband${here?.n === s.n ? ' here' : ''}`}
                style={{ left, width }}
                onClick={() => onFrame(s.start)}
              >
                {fits ? label : ''}
              </div>
            </Tooltip>
          );
        })}
      </div>

      <div className="sliderRow">
        <input
          className="slider"
          type="range"
          min={1}
          max={Math.max(1, total)}
          step={1}
          value={frame}
          onChange={(e) => onFrame(Number(e.currentTarget.value))}
        />
        <Box className="ticks">
          {marks.map((m) => (
            <Tooltip key={m} label={`break point at frame ${m} · ${fmtTime(m)}`}>
              <div
                className={`tick${m === frame ? ' here' : ''}`}
                style={{ left: `${pos(m) * 100}%` }}
                onClick={() => onFrame(m)}
              />
            </Tooltip>
          ))}
        </Box>
      </div>
    </div>
  );
}
