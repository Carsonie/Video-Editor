import { useEffect, useState } from 'react';
import { Card, Text, Badge, Group, Stack, Grid, Button, Loader, Alert } from '@mantine/core';
import { getVideos, type Video } from '../api/client';

interface VideoListProps {
  onVideoSelect?: (videoId: string) => void;
}

export default function VideoList({ onVideoSelect }: VideoListProps) {
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready':
        return 'green';
      case 'encoding':
        return 'blue';
      case 'error':
        return 'red';
      default:
        return 'gray';
    }
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

  if (videos.length === 0) {
    return (
      <Alert color="blue" title="No Videos">
        No videos found. Upload your first video to get started!
      </Alert>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Text size="xl" fw={700}>
          Videos
        </Text>
        <Button onClick={loadVideos} variant="light">
          Refresh
        </Button>
      </Group>

      <Grid>
        {videos.map((video) => (
          <Grid.Col key={video.id} span={{ base: 12, sm: 6, md: 4 }}>
            <Card shadow="sm" padding="lg" withBorder>
              <Card.Section>
                {video.thumbnail_url ? (
                  <img
                    src={video.thumbnail_url}
                    alt={video.name}
                    style={{
                      height: 200,
                      width: '100%',
                      objectFit: 'cover',
                    }}
                  />
                ) : (
                  <div
                    style={{
                      height: 200,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: video.status === 'ready' ? '#1a1b1e' : '#f0f0f0',
                      color: video.status === 'ready' ? '#ffffff' : '#666666',
                    }}
                  >
                    <Stack align="center" gap="xs">
                      <Text size="xl">🎬</Text>
                      <Text c={video.status === 'ready' ? 'white' : 'dimmed'} size="sm">
                        {video.status === 'ready' ? 'Video Ready' :
                         video.status === 'encoding' ? 'Processing...' : 'No Preview'}
                      </Text>
                    </Stack>
                  </div>
                )}
              </Card.Section>

              <Stack gap="sm" mt="md">
                <Group justify="space-between">
                  <Text fw={600} lineClamp={1}>
                    {video.name}
                  </Text>
                  <Badge color={getStatusColor(video.status)} size="sm">
                    {video.status}
                  </Badge>
                </Group>

                {video.description && (
                  <Text size="sm" c="dimmed" lineClamp={2}>
                    {video.description}
                  </Text>
                )}

                <Group gap="xs">
                  <Text size="xs" c="dimmed">
                    {video.duration > 0 ? `${video.duration}s` : 'N/A'}
                  </Text>
                  <Text size="xs" c="dimmed">
                    •
                  </Text>
                  <Text size="xs" c="dimmed">
                    {new Date(video.created_at).toLocaleDateString()}
                  </Text>
                </Group>

                {onVideoSelect && video.status === 'ready' && (
                  <Button
                    fullWidth
                    variant="light"
                    onClick={() => onVideoSelect(video.id)}
                  >
                    Watch
                  </Button>
                )}
              </Stack>
            </Card>
          </Grid.Col>
        ))}
      </Grid>
    </Stack>
  );
}
