import { useEffect, useState } from 'react';
import { Stack, Title, Grid, Card, Text, Group, Badge, Loader, Alert } from '@mantine/core';
import { getVideos, type Video } from '../api/client';

export default function Reports() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadVideos();
  }, []);

  const loadVideos = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getVideos();
      setVideos(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load videos');
    } finally {
      setLoading(false);
    }
  };

  const getTotalDuration = () => {
    return videos.reduce((sum, video) => sum + video.duration, 0);
  };

  const getStatusCounts = () => {
    return videos.reduce(
      (acc, video) => {
        acc[video.status] = (acc[video.status] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  };

  if (loading) {
    return (
      <Group justify="center" py="xl">
        <Loader size="lg" />
      </Group>
    );
  }

  if (error) {
    return (
      <Alert color="red" title="Error">
        {error}
      </Alert>
    );
  }

  const statusCounts = getStatusCounts();
  const totalDuration = getTotalDuration();

  return (
    <Stack gap="xl">
      <Title order={1}>Video Reports</Title>

      <Grid>
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Card shadow="sm" padding="lg" withBorder>
            <Stack gap="xs">
              <Text size="sm" c="dimmed">
                Total Videos
              </Text>
              <Text size="xl" fw={700}>
                {videos.length}
              </Text>
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Card shadow="sm" padding="lg" withBorder>
            <Stack gap="xs">
              <Text size="sm" c="dimmed">
                Total Duration
              </Text>
              <Text size="xl" fw={700}>
                {Math.floor(totalDuration / 60)}m {totalDuration % 60}s
              </Text>
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Card shadow="sm" padding="lg" withBorder>
            <Stack gap="xs">
              <Text size="sm" c="dimmed">
                Ready Videos
              </Text>
              <Group gap="xs" align="baseline">
                <Text size="xl" fw={700}>
                  {statusCounts.ready || 0}
                </Text>
                <Badge color="green" size="sm">
                  Ready
                </Badge>
              </Group>
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <Card shadow="sm" padding="lg" withBorder>
            <Stack gap="xs">
              <Text size="sm" c="dimmed">
                Processing
              </Text>
              <Group gap="xs" align="baseline">
                <Text size="xl" fw={700}>
                  {statusCounts.encoding || 0}
                </Text>
                <Badge color="blue" size="sm">
                  Encoding
                </Badge>
              </Group>
            </Stack>
          </Card>
        </Grid.Col>
      </Grid>

      <Card shadow="sm" padding="lg" withBorder>
        <Stack gap="md">
          <Text size="lg" fw={600}>
            Video Status Breakdown
          </Text>
          <Stack gap="sm">
            {Object.entries(statusCounts).map(([status, count]) => (
              <Group key={status} justify="space-between">
                <Badge
                  color={
                    status === 'ready' ? 'green' : status === 'encoding' ? 'blue' : 'red'
                  }
                >
                  {status}
                </Badge>
                <Text>
                  {count} video{count !== 1 ? 's' : ''}
                </Text>
              </Group>
            ))}
          </Stack>
        </Stack>
      </Card>
    </Stack>
  );
}
