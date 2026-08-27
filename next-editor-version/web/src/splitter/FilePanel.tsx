import { useState } from 'react';
import { Alert, Button, Divider, Stack, Text, Tooltip } from '@mantine/core';
import { useNavigate } from 'react-router';

import { api } from '../api';
import type { ClipMeta } from '../types';

/**
 * The drawer's second tab: this clip, and the three controls that WRITE.
 *
 * They live behind a tab on purpose. Everything touched every few seconds is in
 * the toolbar; anything touched once a session is here, where it cannot be hit
 * by accident. Reset Editor — the most destructive control in the tool — used
 * to sit at the bottom of a scroll with the same weight as Browse.
 */
export function FilePanel({
  meta,
  edited,
  onSaved,
  onCleared,
}: {
  meta: ClipMeta;
  edited: boolean;
  onSaved: (msg: string) => void;
  onCleared: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  async function guarded(what: string, fn: () => Promise<void>) {
    setError(null);
    setBusy(what);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Stack gap={8}>
      <Text fz={11} c="dimmed" tt="uppercase" fw={600}>
        Clip
      </Text>
      <Text fz={12} style={{ wordBreak: 'break-all' }}>
        {meta.source_name}
      </Text>
      <Text fz={12} c="dimmed" className="num">
        {meta.fps}fps · {meta.nb_frames} frames · {meta.ext === '.png' ? 'alpha' : 'opaque'}
      </Text>
      <Tooltip label="Browse the Customers folder for another recording">
        <Button fullWidth onClick={() => navigate('/browse')}>
          📁 Browse…
        </Button>
      </Tooltip>

      <Divider my={4} />
      <Text fz={11} c="dimmed" tt="uppercase" fw={600}>
        Write to disk
      </Text>
      <Tooltip label="Rebuild this clip's edits from the ORIGINAL file and overwrite the file this viewer opened. The file it replaces is archived to z_History/ first.">
        <Button
          fullWidth
          disabled={!edited}
          loading={busy === 'save'}
          onClick={() =>
            void guarded('save', async () => {
              if (
                !window.confirm(
                  `Rebuild ${meta.nb_frames} frames and OVERWRITE:\n\n${meta.source}\n\n` +
                    `The file it replaces is archived to z_History/ first.`,
                )
              )
                return;
              const d = await api.save(meta.slug);
              // The rebuild is time-based per piece, so it CAN come back short
              // of the length that was on screen. A save says so rather than
              // letting it pass — that is the fault this whole tool exists to
              // catch.
              onSaved(
                d.warning
                  ? `⚠ ${d.warning}`
                  : `Saved ${d.nb_frames} frames · archived to ${d.archived_to}`,
              );
            })
          }
        >
          💾 Save edited segment
        </Button>
      </Tooltip>

      <Divider my={4} />
      <Text fz={11} c="red.4" tt="uppercase" fw={600}>
        Discard
      </Text>
      <Tooltip label="Discard every edit and break point in this preview and re-extract clean frames. The SOURCE FILE is never touched — only the cache.">
        <Button
          fullWidth
          loading={busy === 'clear'}
          onClick={() =>
            void guarded('clear', async () => {
              if (!window.confirm('Discard every edit and break point in this preview?')) return;
              await api.clearEdits(meta.slug);
              onCleared();
            })
          }
        >
          ↺ Clear all edits
        </Button>
      </Tooltip>
      <Tooltip label="Delete this video's ENTIRE cache — frames, edits, break points — and return to Browse. The original video FILE is never touched.">
        <Button
          fullWidth
          color="red"
          variant="light"
          loading={busy === 'reset'}
          onClick={() =>
            void guarded('reset', async () => {
              if (
                !window.confirm(
                  'Delete this clip\'s whole cache and go back to Browse?\n\n' +
                    'The original video file is not touched. Reopening it starts over.',
                )
              )
                return;
              await api.resetEditor(meta.slug);
              navigate('/browse');
            })
          }
        >
          🗑️ Reset Editor
        </Button>
      </Tooltip>

      {error && (
        <Alert color="red" p="xs">
          <Text fz={12}>{error}</Text>
        </Alert>
      )}
    </Stack>
  );
}
