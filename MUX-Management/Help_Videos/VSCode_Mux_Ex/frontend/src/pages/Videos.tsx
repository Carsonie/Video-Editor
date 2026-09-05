import { useState } from 'react';
import { Stack, Title, Grid } from '@mantine/core';
import VideoList from '../components/VideoList';
import VideoPlayer from '../components/VideoPlayer';

export default function Videos() {
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);

  return (
    <Stack gap="xl">
      <Title order={1}>Videos</Title>

      <Grid>
        <Grid.Col span={{ base: 12, md: selectedVideoId ? 7 : 12 }}>
          <VideoList onVideoSelect={setSelectedVideoId} />
        </Grid.Col>

        {selectedVideoId && (
          <Grid.Col span={{ base: 12, md: 5 }}>
            <VideoPlayer videoId={selectedVideoId} />
          </Grid.Col>
        )}
      </Grid>
    </Stack>
  );
}
