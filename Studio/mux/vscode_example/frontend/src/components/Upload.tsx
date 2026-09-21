import { useState, useRef } from 'react';
import {
  Card,
  TextInput,
  Textarea,
  Button,
  Stack,
  Alert,
  Group,
  Text,
  SegmentedControl,
  FileButton,
  Progress,
} from '@mantine/core';
import {
  uploadVideo,
  createDirectUpload,
  uploadFileToMux,
  completeDirectUpload,
  type CreateVideoRequest,
} from '../api/client';

interface UploadProps {
  onUploadSuccess?: () => void;
}

type UploadMode = 'url' | 'file';

export default function Upload({ onUploadSuccess }: UploadProps) {
  const [mode, setMode] = useState<UploadMode>('file');
  const [formData, setFormData] = useState<CreateVideoRequest>({
    url: '',
    name: '',
    description: '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const resetRef = useRef<() => void>(null);

  const handleFileSelect = (selectedFile: File | null) => {
    setFile(selectedFile);
    setError(null);
    setSuccess(false);

    // Auto-populate name from filename if empty
    if (selectedFile && !formData.name) {
      const nameWithoutExt = selectedFile.name.replace(/\.[^/.]+$/, '');
      setFormData((prev) => ({ ...prev, name: nameWithoutExt }));
    }
  };

  const handleSubmitURL = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.url || !formData.name) {
      setError('URL and name are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(false);

      await uploadVideo(formData);

      setSuccess(true);
      setFormData({ url: '', name: '', description: '' });

      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload video');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitFile = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file || !formData.name) {
      setError('File and name are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(false);
      setUploadProgress(0);

      // Step 1: Create direct upload
      const { upload_id, upload_url } = await createDirectUpload();

      // Step 2: Upload file to Mux
      await uploadFileToMux(file, upload_url, (progress) => {
        setUploadProgress(progress);
      });

      // Step 3: Complete upload and create video record
      await completeDirectUpload(upload_id, {
        name: formData.name,
        description: formData.description,
      });

      setSuccess(true);
      setFormData({ url: '', name: '', description: '' });
      setFile(null);
      setUploadProgress(0);

      // Reset file input
      resetRef.current?.();

      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload video');
      setUploadProgress(0);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (field: keyof CreateVideoRequest, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setError(null);
    setSuccess(false);
  };

  const handleClear = () => {
    setFormData({ url: '', name: '', description: '' });
    setFile(null);
    setError(null);
    setSuccess(false);
    setUploadProgress(0);
    resetRef.current?.();
  };

  return (
    <Card shadow="sm" padding="lg">
      <form onSubmit={mode === 'url' ? handleSubmitURL : handleSubmitFile}>
        <Stack gap="md">
          <Text size="xl" fw={700}>
            Upload Video
          </Text>

          <SegmentedControl
            value={mode}
            onChange={(value) => {
              setMode(value as UploadMode);
              handleClear();
            }}
            data={[
              { label: 'Upload File', value: 'file' },
              { label: 'From URL', value: 'url' },
            ]}
          />

          <Text size="sm" c="dimmed">
            {mode === 'url'
              ? 'Create a new video asset by providing a URL to your video file. Mux will process and encode your video for streaming.'
              : 'Upload a video file directly from your computer. Mux will process and encode your video for streaming.'}
          </Text>

          {error && (
            <Alert color="red" title="Error">
              {error}
            </Alert>
          )}

          {success && (
            <Alert color="green" title="Success">
              Video uploaded successfully! It will appear in the list once encoding is complete.
            </Alert>
          )}

          {mode === 'url' ? (
            <TextInput
              label="Video URL"
              placeholder="https://example.com/video.mp4"
              required
              value={formData.url}
              onChange={(e) => handleChange('url', e.target.value)}
              description="Direct URL to your video file (MP4, MOV, etc.)"
            />
          ) : (
            <Stack gap="xs">
              <Group gap="sm">
                <FileButton
                  resetRef={resetRef}
                  onChange={handleFileSelect}
                  accept="video/*"
                >
                  {(props) => (
                    <Button {...props} variant="light" disabled={loading}>
                      {file ? 'Change File' : 'Select Video File'}
                    </Button>
                  )}
                </FileButton>
                {file && (
                  <Text size="sm" c="dimmed">
                    {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </Text>
                )}
              </Group>
              {!file && (
                <Text size="xs" c="dimmed">
                  Supported formats: MP4, MOV, AVI, etc.
                </Text>
              )}
            </Stack>
          )}

          {loading && uploadProgress > 0 && (
            <Stack gap="xs">
              <Progress value={uploadProgress} size="lg" animated />
              <Text size="sm" c="dimmed" ta="center">
                Uploading: {uploadProgress}%
              </Text>
            </Stack>
          )}

          <TextInput
            label="Video Name"
            placeholder="My Awesome Video"
            required
            value={formData.name}
            onChange={(e) => handleChange('name', e.target.value)}
            description="A descriptive name for your video"
          />

          <Textarea
            label="Description"
            placeholder="Optional description..."
            value={formData.description}
            onChange={(e) => handleChange('description', e.target.value)}
            description="Optional description of your video"
            minRows={3}
          />

          <Group justify="flex-end">
            <Button type="button" variant="light" onClick={handleClear} disabled={loading}>
              Clear
            </Button>
            <Button type="submit" loading={loading}>
              {loading ? 'Uploading...' : 'Upload Video'}
            </Button>
          </Group>
        </Stack>
      </form>
    </Card>
  );
}
