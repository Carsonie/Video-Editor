import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  Loader,
  Paper,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { IconFolder, IconMovie, IconArrowUp } from '@tabler/icons-react';

import { api } from '../api';
import type { ListResponse } from '../types';

function fmtSize(b: number): string {
  if (b > 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  if (b > 1e3) return `${(b / 1e3).toFixed(0)} KB`;
  return `${b} B`;
}

/**
 * The folder tree, rooted at Customers/ — how a recording is found without
 * already knowing its path.
 *
 * A STORE row is any folder with its own help-videos/raw_mp4/. That is derived
 * by the backend from the real filesystem, not assumed from depth, so it works
 * whether Customers/ is two levels deep or a hundred.
 */
export function Browse() {
  const [params, setParams] = useSearchParams();
  const path = params.get('path') ?? '';
  const [data, setData] = useState<ListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let live = true;
    setError(null);
    api
      .list(path)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [path]);

  const go = useCallback((p: string) => setParams({ path: p }), [setParams]);

  const openFile = useCallback(
    async (p: string) => {
      // Extraction can take a while on a long recording, so the row says what
      // is happening rather than appearing to have done nothing.
      setBusy(`Extracting frames from ${p} — this can take a moment…`);
      try {
        const d = await api.open(p);
        navigate(`/clip/${d.url.split('/')[0]}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(null);
      }
    },
    [navigate],
  );

  return (
    <Box maw={750} mx="auto" px="md">
      <Title order={4} c="dimmed" fz={15} mb={10}>
        Browse Customers/ for a recording
      </Title>
      <Text fz={12} c="dimmed" mb={10} style={{ wordBreak: 'break-all' }}>
        Customers/{data?.path ?? ''}
      </Text>

      {error && (
        <Alert color="red" mb="sm" title="That did not work">
          {error}
        </Alert>
      )}
      {busy && (
        <Group gap="xs" mb="sm">
          <Loader size="xs" />
          <Text fz={13} c="yellow.4">
            {busy}
          </Text>
        </Group>
      )}

      {/* A VIDEO FOLDER is one holding both `sandbox/` and `video/`. Derived
          from what the listing already returned rather than asked for — the
          Segment and Avatar Editor works on a whole video, not on one file, so
          this is the only place it can be entered from. */}
      {data &&
        data.dirs.some((d) => d.name === 'sandbox') &&
        data.dirs.some((d) => d.name === 'video') && (
          <Paper withBorder radius="md" p="sm" mb="sm">
            <Group justify="space-between">
              <Text fz={13}>
                This is a video folder — its scenes can go on one timeline.
              </Text>
              <Button
                size="compact-sm"
                onClick={() => navigate(`/timeline?root=${encodeURIComponent(data.path)}&ns=all`)}
              >
                Open the Segment and Avatar Editor →
              </Button>
            </Group>
          </Paper>
        )}

      <Paper withBorder radius="md" style={{ overflow: 'hidden' }}>
        {!data && !error && (
          <Group p="md" gap="xs">
            <Loader size="xs" />
            <Text fz={13} c="dimmed">
              reading the folder…
            </Text>
          </Group>
        )}

        {data?.parent !== null && data && (
          <Row onClick={() => go(data.parent!)}>
            <Group gap={8}>
              <IconArrowUp size={15} />
              <Text fz={13}>.. (up)</Text>
            </Group>
          </Row>
        )}

        {data?.dirs.map((d) => (
          <Row key={d.path} onClick={() => go(d.jump ?? d.path)}>
            <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
              {d.jump ? <IconMovie size={15} /> : <IconFolder size={15} />}
              <Text fz={13} truncate>
                {d.name}
              </Text>
            </Group>
            {d.jump && (
              <Group gap={6}>
                <Jump label="raw_mp4 →" onClick={() => go(d.jump!)} />
                {d.segments_jump && (
                  <Jump label="segments →" onClick={() => go(d.segments_jump!)} />
                )}
              </Group>
            )}
          </Row>
        ))}

        {data?.files.map((f) => (
          <Row key={f.path} onClick={() => void openFile(f.path)}>
            <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
              <IconMovie size={15} color="#9fd0ff" />
              <Text fz={13} c="#9fd0ff" truncate>
                {f.name}
              </Text>
            </Group>
            <Text fz={13} c="dimmed" className="num">
              {fmtSize(f.size)}
            </Text>
          </Row>
        ))}

        {data && data.dirs.length === 0 && data.files.length === 0 && (
          <Text p="md" fz={13} c="dimmed">
            Nothing here.
          </Text>
        )}
      </Paper>
    </Box>
  );
}

function Row({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <UnstyledButton
      onClick={onClick}
      w="100%"
      px={14}
      py={9}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
        borderBottom: '1px solid var(--line)',
      }}
      __vars={{ '--row-hover': 'var(--panel2)' }}
      className="browseRow"
    >
      {children}
    </UnstyledButton>
  );
}

function Jump({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <Badge
      variant="outline"
      color="gray"
      size="sm"
      // Mantine upper-cases a badge by default. These are FOLDER NAMES, and
      // `RAW_MP4` is not the folder — `raw_mp4` is.
      tt="none"
      style={{ cursor: 'pointer' }}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      {label}
    </Badge>
  );
}
