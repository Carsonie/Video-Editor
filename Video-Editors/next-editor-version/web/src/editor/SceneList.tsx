import { Badge, Box, Button, Checkbox, Group, Stack, Text, Tooltip } from '@mantine/core';

import type { SeqScene, SiblingRow } from '../types';
import { type Layer, layerName } from './useTimeline';

/**
 * Every scene of the store, with two locks and two counts each.
 *
 * The SEGMENT (the footage) and the OVERLAY (the avatar) get separate controls
 * because they are separate FILES with separate lengths, edited one layer at a
 * time. Unticking one protects that track while you work on the other: ＋/－
 * Frame, ＋/－ Zone, Cut and Save all skip an unticked track.
 *
 * Ticking a scene into the timeline does not rebuild by itself. Rebuilding
 * makes a different set of frames, so it is a NAVIGATION, not an edit —
 * nothing you have changed is lost — and it happens when you say so.
 */
export function SceneList({
  all,
  scenes,
  picked,
  locked,
  currentN,
  onPick,
  onLock,
  onJump,
  onRebuild,
  onSelectAll,
  onBalance,
  onSaveAll,
  busy,
}: {
  all: SiblingRow[];
  scenes: SeqScene[];
  picked: Set<number>;
  locked: Set<string>;
  currentN: number | null;
  onPick: (n: number, on: boolean) => void;
  onLock: (n: number, layer: Layer, unlocked: boolean) => void;
  onJump: (n: number) => void;
  onRebuild: () => void;
  onSelectAll: (on: boolean) => void;
  onBalance: () => void;
  onSaveAll: () => void;
  busy: string | null;
}) {
  const onTimeline = new Set(scenes.map((s) => s.n));
  const changed =
    picked.size !== onTimeline.size || [...picked].some((n) => !onTimeline.has(n));

  return (
    <Stack gap={6}>
      <Text fz={12} fw={600} c="dimmed" tt="uppercase">
        Time Line Scenes
      </Text>

      <Stack gap={2}>
        {all.map((row) => {
          const on = picked.has(row.n);
          const seq = scenes.find((s) => s.n === row.n) ?? null;
          return (
            <Group
              key={row.n}
              gap={6}
              wrap="nowrap"
              px={6}
              py={3}
              style={{
                borderRadius: 4,
                background: row.n === currentN ? 'var(--panel2)' : undefined,
                opacity: on ? 1 : 0.55,
              }}
            >
              <Tooltip
                label={
                  row.missing
                    ? `Scene ${row.n} has no footage, so it cannot go on the timeline.`
                    : `Put scene ${row.n} on the timeline, or take it off. Ticking does not rebuild by itself — press Rebuild underneath once the set is the one you want.`
                }
              >
                <Checkbox
                  size="xs"
                  checked={on}
                  disabled={row.missing}
                  onChange={(e) => onPick(row.n, e.currentTarget.checked)}
                />
              </Tooltip>

              <Box
                style={{ flex: '1 1 0', minWidth: 0, cursor: seq ? 'pointer' : 'default' }}
                onClick={() => seq && onJump(row.n)}
              >
                <Group gap={6} wrap="nowrap">
                  <Text fz={11} c="dimmed" className="num" w={16}>
                    {row.n}
                  </Text>
                  <Text fz={12} truncate>
                    {row.label || row.n}
                  </Text>
                  {row.missing && (
                    <Badge size="xs" color="red" variant="outline" tt="none">
                      missing
                    </Badge>
                  )}
                  {seq && !seq.in_script && (
                    <Tooltip label="A bookend — a real folder with no row in script.json. It can sit on a timeline, which is the point, but it cannot be joined or split, because both rewrite the scene list and it is not in one.">
                      <Badge size="xs" color="gray" variant="outline" tt="none">
                        bookend
                      </Badge>
                    </Tooltip>
                  )}
                  <Text fz={11} c="dimmed" className="num" ml="auto">
                    {row.dur ?? '?'}s
                  </Text>
                </Group>
              </Box>

              {(['base', 'overlay'] as Layer[]).map((layer) => {
                const present =
                  layer === 'base' ? !row.missing : Boolean(row.overlay);
                const count =
                  layer === 'base' ? row.frames : row.overlay_frames;
                const exact =
                  layer === 'base' ? row.frames_exact : row.overlay_frames_exact;
                const live = seq
                  ? layer === 'base'
                    ? seq.base_n
                    : seq.over_n
                  : null;
                const shown = live ?? count;
                return (
                  <Group key={layer} gap={3} wrap="nowrap">
                    <Tooltip
                      label={
                        present
                          ? `Include this scene's ${layer === 'base' ? 'SEGMENT (the footage)' : 'OVERLAY (the avatar)'} in edits. Untick it to protect this track while you work on the other one — ＋/－ Frame, ＋/－ Zone, Cut and Save all skip an unticked track.`
                          : `This scene has no ${layerName(layer)}, so there is nothing to edit.`
                      }
                    >
                      <Checkbox
                        size="xs"
                        color={layer === 'overlay' ? 'grape.6' : 'teal.6'}
                        disabled={!present}
                        checked={present && !locked.has(`${row.n}:${layer}`)}
                        onChange={(e) => onLock(row.n, layer, e.currentTarget.checked)}
                      />
                    </Tooltip>
                    <Tooltip
                      label={
                        shown == null
                          ? `No ${layerName(layer)} on this scene, so there is nothing to count.`
                          : exact || live != null
                            ? `${shown} frames in this scene's ${layerName(layer)}, counted frame by frame. The two tracks are separate files and drift apart as you edit — Update Frame Imbalance evens them up.`
                            : `About ${shown} frames, read from the file header without extracting it. It can be out by one until the scene has been opened.`
                      }
                    >
                      <Text
                        fz={11}
                        w={30}
                        ta="right"
                        className="num"
                        c={layer === 'overlay' ? 'grape.4' : 'teal.4'}
                        style={{ fontStyle: exact || live != null ? undefined : 'italic' }}
                      >
                        {shown == null ? '—' : exact || live != null ? shown : `~${shown}`}
                      </Text>
                    </Tooltip>
                  </Group>
                );
              })}
            </Group>
          );
        })}
      </Stack>

      <Tooltip label="Rebuild the timeline from the ticked scenes. The timeline is a different set of frames afterwards, so this is a NAVIGATION, not an edit — nothing you have changed is lost.">
        <Button
          fullWidth
          disabled={picked.size === 0 || !changed}
          onClick={onRebuild}
        >
          {picked.size === 0
            ? 'Tick at least one scene'
            : changed
              ? `Rebuild — ${picked.size} scene${picked.size === 1 ? '' : 's'}`
              : 'Timeline is up to date'}
        </Button>
      </Tooltip>

      <Group gap={6} grow>
        <Tooltip label="Tick every scene. Pair it with Rebuild to put the whole video on one timeline.">
          <Button size="compact-xs" onClick={() => onSelectAll(true)}>
            Select all
          </Button>
        </Tooltip>
        <Tooltip label="Untick every scene. Then tick just the few you want to compare, and rebuild.">
          <Button size="compact-xs" onClick={() => onSelectAll(false)}>
            Unselect all
          </Button>
        </Tooltip>
      </Group>

      <Tooltip label="Make each ticked scene's two tracks the same length, by repeating the LAST frame of whichever is shorter. The last frame is the settled end of the shot, so the repeat is invisible. Undoable per scene.">
        <Button fullWidth loading={busy === 'balance'} onClick={onBalance}>
          ⇆ Update Frame Imbalance
        </Button>
      </Tooltip>
      <Tooltip label="Write every scene that has unsaved edits back to sandbox/, in one go. Each file is archived to z_History/ first. This is the ONLY way to save once a join has renumbered the scenes.">
        <Button fullWidth loading={busy === 'saveAll'} onClick={onSaveAll}>
          ⤓ Save all scenes
        </Button>
      </Tooltip>
    </Stack>
  );
}
