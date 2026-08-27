import { Button, Group, Tooltip } from '@mantine/core';

export type Mode = 'nav' | 'frame-editor';
export type Sub = 'add' | 'sub';

/**
 * Row 3 of the toolbar: WHAT YOU CHANGE.
 *
 * Frame Editor REWRITES WHAT THE STEP BUTTONS DO. In nav they move the
 * pointer; in Frame Editor the same buttons insert or delete frames on that
 * side, `count` of them. That is the point of the mode, and it is also why it
 * has to be impossible to miss which mode is on — hence the filled button.
 *
 * A ZONE is the whole span between the break points either side of the
 * playhead, acted on in one go. Trimming a dead patch out of a recording is
 * this tool's job, and one frame at a time made a three-second patch
 * seventy-five clicks.
 */
export function EditRow({
  mode,
  sub,
  marked,
  canUndo,
  onMark,
  onMode,
  onSub,
  onZone,
  onUndo,
  zoneLabel,
}: {
  mode: Mode;
  sub: Sub;
  marked: boolean;
  canUndo: boolean;
  onMark: () => void;
  onMode: (m: Mode) => void;
  onSub: (s: Sub) => void;
  onZone: (kind: 'dup' | 'del') => void;
  onUndo: () => void;
  zoneLabel: string;
}) {
  return (
    <Group className="rowbar" gap={6} wrap="wrap">
      <Tooltip label="Mark or unmark this frame as a break point (M)">
        <Button
          variant={marked ? 'filled' : 'default'}
          color={marked ? 'mark.5' : undefined}
          onClick={onMark}
        >
          <span
            style={{
              width: 9,
              height: 9,
              marginRight: 7,
              borderRadius: 2,
              display: 'inline-block',
              background: marked ? 'var(--markHi)' : 'transparent',
              border: '1px solid var(--mark)',
            }}
          />
          Mark
        </Button>
      </Tooltip>

      <Tooltip label="Frame Editor: the step buttons INSERT or DELETE frames instead of navigating. The preview changes; the source file does not, until you Save.">
        <Button
          variant={mode === 'frame-editor' ? 'filled' : 'default'}
          color={mode === 'frame-editor' ? 'yellow.7' : undefined}
          onClick={() => onMode(mode === 'frame-editor' ? 'nav' : 'frame-editor')}
        >
          ✂️ Edit
        </Button>
      </Tooltip>

      <Button.Group>
        <Tooltip label="Add — the step buttons duplicate this frame on that side">
          <Button
            variant={mode === 'frame-editor' && sub === 'add' ? 'filled' : 'default'}
            color={mode === 'frame-editor' && sub === 'add' ? 'teal.7' : undefined}
            disabled={mode !== 'frame-editor'}
            onClick={() => onSub('add')}
          >
            ＋ Add
          </Button>
        </Tooltip>
        <Tooltip label="Subtract — the step buttons delete frames on that side">
          <Button
            variant={mode === 'frame-editor' && sub === 'sub' ? 'filled' : 'default'}
            color={mode === 'frame-editor' && sub === 'sub' ? 'red.8' : undefined}
            disabled={mode !== 'frame-editor'}
            onClick={() => onSub('sub')}
          >
            － Sub
          </Button>
        </Tooltip>
      </Button.Group>

      <Button.Group>
        <Tooltip label={`Repeat the whole zone — ${zoneLabel}. With no break points the zone is the whole clip.`}>
          <Button onClick={() => onZone('dup')}>＋ Zone</Button>
        </Tooltip>
        <Tooltip label={`Delete the whole zone in one go — ${zoneLabel}. This is how an unwanted patch comes out.`}>
          <Button onClick={() => onZone('del')}>－ Zone</Button>
        </Tooltip>
      </Button.Group>

      <Tooltip label="Step back through this clip's edits, one at a time. Cleared when you save. The source file is never touched either way.">
        <Button disabled={!canUndo} onClick={onUndo}>
          ↶ Undo
        </Button>
      </Tooltip>
    </Group>
  );
}
