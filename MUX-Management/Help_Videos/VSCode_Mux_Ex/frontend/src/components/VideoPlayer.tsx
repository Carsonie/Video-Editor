import { useEffect, useState } from 'react';
import MuxPlayer from '@mux/mux-player-react';
import { Card, Text, Badge, Group, Stack, Loader, Alert } from '@mantine/core';
import { getVideo, getPlaybackToken, type Video } from '../api/client';

interface VideoPlayerProps {
  videoId: string;
}

export default function VideoPlayer({ videoId }: VideoPlayerProps) {
  const [video, setVideo] = useState<Video | null>(null);
  const [tokens, setTokens] = useState<{ playback: string; thumbnail: string; storyboard: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadVideo();
  }, [videoId]);

  const loadVideo = async () => {
    try {
      setLoading(true);
      setError(null);

      // Get video details
      const videoData = await getVideo(videoId);
      setVideo(videoData);

      // If video is ready, try to get playback tokens (for signed playback)
      // If tokens fail, that's okay - the video might be public
      if (videoData.status === 'ready') {
        try {
          const tokenData = await getPlaybackToken(videoId);
          setTokens({
            playback: tokenData.token,
            thumbnail: tokenData.thumbnail,
            storyboard: tokenData.storyboard,
          });
        } catch (tokenErr) {
          // Tokens not available - video is likely public, continue without tokens
          console.log('Tokens not available, playing as public video');
          setTokens(null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load video');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card shadow="sm" padding="lg">
        <Group justify="center" py="xl">
          <Loader size="lg" />
        </Group>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert color="red" title="Error">
        {error}
      </Alert>
    );
  }

  if (!video) {
    return (
      <Alert color="yellow" title="Not Found">
        Video not found
      </Alert>
    );
  }

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

  return (
    <Card shadow="sm" padding="lg">
      <Stack gap="md">
        <Group justify="space-between">
          <Text size="xl" fw={700}>
            {video.name}
          </Text>
          <Badge color={getStatusColor(video.status)}>{video.status}</Badge>
        </Group>

        {video.description && (
          <Text size="sm" c="dimmed">
            {video.description}
          </Text>
        )}

        {video.status === 'ready' ? (
          <MuxPlayer
            playbackId={video.mux_signed_playback_id || video.mux_playback_id}
            tokens={tokens || undefined}
            metadata={{
              video_id: video.id,
              video_title: video.name,
            }}
            streamType="on-demand"
            autoPlay={false}
          />
        ) : video.status === 'encoding' ? (
          <Alert color="blue" title="Encoding">
            Your video is currently being processed. This may take a few minutes.
          </Alert>
        ) : video.status === 'error' ? (
          <Alert color="red" title="Error">
            There was an error encoding your video. Please try uploading again.
          </Alert>
        ) : null}

        <Group gap="xs">
          <Text size="sm" c="dimmed">
            Duration: {video.duration > 0 ? `${video.duration}s` : 'N/A'}
          </Text>
          <Text size="sm" c="dimmed">
            •
          </Text>
          <Text size="sm" c="dimmed">
            Created: {new Date(video.created_at).toLocaleDateString()}
          </Text>
        </Group>
      </Stack>
    </Card>
  );
}
