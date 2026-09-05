import { useState } from 'react';
import { Stack, Title, Grid } from '@mantine/core';
import VideoList from '../components/VideoList';
import Upload from '../components/Upload';

export default function Home() {
  const [refreshKey, setRefreshKey] = useState(0);

  const handleUploadSuccess = () => {
    // Refresh video list after successful upload
    setRefreshKey((prev) => prev + 1);
  };

  return (
    <Stack gap="xl">
      <Title order={1}>Video Platform</Title>

      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Upload onUploadSuccess={handleUploadSuccess} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <VideoList key={refreshKey} />
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
