package mux

import (
	"context"
	"fmt"
	"log"
	"time"

	muxgo "github.com/muxinc/mux-go"
	"github.com/yourname/mux-example/z_slog"
)

// Client manages Mux API interactions
type Client struct {
	apiClient *muxgo.APIClient
}

// New creates a new Mux client
func New(tokenID, tokenSecret string) (*Client, error) {
	z_slog.FunctionEntry("New")
	if tokenID == "" || tokenSecret == "" {
		z_slog.ReturnValues(map[string]any{"client": nil, "error": "mux token ID and secret are required"})
		return nil, fmt.Errorf("mux token ID and secret are required")
	}

	// Create Mux configuration with basic auth
	config := muxgo.NewConfiguration(
		muxgo.WithBasicAuth(tokenID, tokenSecret),
	)

	// Create API client
	apiClient := muxgo.NewAPIClient(config)

	z_slog.ReturnValues(map[string]any{"client": "Client", "error": nil})
	return &Client{
		apiClient: apiClient,
	}, nil
}

// CreateAssetFromURL creates a Mux asset from a video URL
// Returns: assetID, publicPlaybackID, signedPlaybackID, error
func (c *Client) CreateAssetFromURL(videoURL string) (string, string, string, error) {
	z_slog.FunctionEntry("CreateAssetFromURL")
	log.Printf("Creating Mux asset from URL: %s", videoURL)

	ctx := context.Background()

	// Create asset input
	input := []muxgo.InputSettings{{Url: videoURL}}
	playbackPolicies := []muxgo.PlaybackPolicy{muxgo.SIGNED}

	createAssetRequest := muxgo.CreateAssetRequest{
		Input:          input,
		PlaybackPolicy: playbackPolicies,
	}

	// Create the asset
	asset, err := c.apiClient.AssetsApi.CreateAsset(createAssetRequest)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"assetID": "", "publicPlaybackID": "", "signedPlaybackID": "", "error": err.Error()})
		return "", "", "", fmt.Errorf("failed to create mux asset: %w", err)
	}
	_ = ctx // unused for now

	// Extract asset ID
	assetID := asset.Data.Id

	// Extract playback IDs
	var publicPlaybackID, signedPlaybackID string
	for _, playbackID := range asset.Data.PlaybackIds {
		if playbackID.Policy == muxgo.PUBLIC {
			publicPlaybackID = playbackID.Id
		} else if playbackID.Policy == muxgo.SIGNED {
			signedPlaybackID = playbackID.Id
		}
	}

	// Check that at least one playback ID exists
	if publicPlaybackID == "" && signedPlaybackID == "" {
		z_slog.ReturnValues(map[string]any{"assetID": "", "publicPlaybackID": "", "signedPlaybackID": "", "error": "failed to get playback ID from asset"})
		return "", "", "", fmt.Errorf("failed to get playback ID from asset")
	}

	log.Printf("Mux asset created: %s (public: %s, signed: %s)", assetID, publicPlaybackID, signedPlaybackID)

	// Return actual separate IDs
	z_slog.ReturnValues(map[string]any{"assetID": assetID, "publicPlaybackID": publicPlaybackID, "signedPlaybackID": signedPlaybackID, "error": nil})
	return assetID, publicPlaybackID, signedPlaybackID, nil
}

// CreateDirectUpload creates a direct upload URL for client-side file uploads
// Returns: uploadID, uploadURL, error
func (c *Client) CreateDirectUpload(corsOrigin string) (string, string, error) {
	z_slog.FunctionEntry("CreateDirectUpload")
	log.Printf("Creating Mux direct upload with CORS origin: %s", corsOrigin)

	playbackPolicies := []muxgo.PlaybackPolicy{muxgo.SIGNED}

	createUploadRequest := muxgo.CreateUploadRequest{
		NewAssetSettings: muxgo.CreateAssetRequest{
			PlaybackPolicy: playbackPolicies,
		},
		CorsOrigin: corsOrigin,
	}

	log.Printf("Calling Mux API CreateDirectUpload with request: %+v", createUploadRequest)
	log.Printf("Playback policies: %+v", playbackPolicies)
	upload, err := c.apiClient.DirectUploadsApi.CreateDirectUpload(createUploadRequest)
	if err != nil {
		log.Printf("Mux API error type: %T", err)
		log.Printf("Mux API error details: %#v", err)
		log.Printf("Mux API error string: %s", err.Error())

		z_slog.ReturnValues(map[string]any{"uploadID": "", "uploadURL": "", "error": err.Error()})
		return "", "", fmt.Errorf("failed to create direct upload: %w", err)
	}

	log.Printf("Direct upload created: %s (URL: %s)", upload.Data.Id, upload.Data.Url)

	z_slog.ReturnValues(map[string]any{"uploadID": upload.Data.Id, "uploadURL": "created", "error": nil})
	return upload.Data.Id, upload.Data.Url, nil
}

// GetDirectUpload retrieves information about a direct upload
func (c *Client) GetDirectUpload(uploadID string) (*muxgo.UploadResponse, error) {
	z_slog.FunctionEntry("GetDirectUpload")
	upload, err := c.apiClient.DirectUploadsApi.GetDirectUpload(uploadID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"upload": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get direct upload: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"uploadID": upload.Data.Id, "error": nil})
	return &upload, nil
}

// GetAssetFromUpload gets the asset ID from a completed direct upload
// Returns: assetID, publicPlaybackID, signedPlaybackID, error
func (c *Client) GetAssetFromUpload(uploadID string) (string, string, string, error) {
	z_slog.FunctionEntry("GetAssetFromUpload")
	upload, err := c.GetDirectUpload(uploadID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"assetID": "", "publicPlaybackID": "", "signedPlaybackID": "", "error": err.Error()})
		return "", "", "", err
	}

	if upload.Data.AssetId == "" {
		z_slog.ReturnValues(map[string]any{"assetID": "", "publicPlaybackID": "", "signedPlaybackID": "", "error": "upload not yet associated with an asset"})
		return "", "", "", fmt.Errorf("upload not yet associated with an asset")
	}

	// Get the asset to retrieve playback IDs
	asset, err := c.GetAsset(upload.Data.AssetId)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"assetID": "", "publicPlaybackID": "", "signedPlaybackID": "", "error": err.Error()})
		return "", "", "", err
	}

	// Extract playback IDs
	var publicPlaybackID, signedPlaybackID string
	for _, playbackID := range asset.Data.PlaybackIds {
		if playbackID.Policy == muxgo.PUBLIC {
			publicPlaybackID = playbackID.Id
		} else if playbackID.Policy == muxgo.SIGNED {
			signedPlaybackID = playbackID.Id
		}
	}

	// Check that at least one playback ID exists
	if publicPlaybackID == "" && signedPlaybackID == "" {
		z_slog.ReturnValues(map[string]any{"assetID": "", "publicPlaybackID": "", "signedPlaybackID": "", "error": "failed to get playback ID from asset"})
		return "", "", "", fmt.Errorf("failed to get playback ID from asset")
	}

	log.Printf("Asset from upload: %s (public: %s, signed: %s)", upload.Data.AssetId, publicPlaybackID, signedPlaybackID)

	// Return actual separate IDs
	z_slog.ReturnValues(map[string]any{"assetID": upload.Data.AssetId, "publicPlaybackID": publicPlaybackID, "signedPlaybackID": signedPlaybackID, "error": nil})
	return upload.Data.AssetId, publicPlaybackID, signedPlaybackID, nil
}

// GetAssetStatus checks the encoding status of a Mux asset
// Returns: status (encoding/ready/error), duration, error
func (c *Client) GetAssetStatus(assetID string) (string, int, error) {
	z_slog.FunctionEntry("GetAssetStatus")
	asset, err := c.apiClient.AssetsApi.GetAsset(assetID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"status": "", "duration": 0, "error": err.Error()})
		return "", 0, fmt.Errorf("failed to get asset status: %w", err)
	}

	status := mapMuxStatus(asset.Data.Status)
	duration := int(asset.Data.Duration)

	z_slog.ReturnValues(map[string]any{"status": status, "duration": duration, "error": nil})
	return status, duration, nil
}

// GetAsset retrieves detailed information about a Mux asset
func (c *Client) GetAsset(assetID string) (*muxgo.AssetResponse, error) {
	z_slog.FunctionEntry("GetAsset")
	asset, err := c.apiClient.AssetsApi.GetAsset(assetID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"asset": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get asset: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"assetID": asset.Data.Id, "error": nil})
	return &asset, nil
}

// DeleteAsset deletes a Mux asset
func (c *Client) DeleteAsset(assetID string) error {
	z_slog.FunctionEntry("DeleteAsset")
	err := c.apiClient.AssetsApi.DeleteAsset(assetID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to delete asset: %w", err)
	}

	log.Printf("Mux asset deleted: %s", assetID)
	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// WaitForAssetReady polls the asset status until it's ready or errored
// Returns: final status, duration, error
func (c *Client) WaitForAssetReady(assetID string, timeout time.Duration) (string, int, error) {
	z_slog.FunctionEntry("WaitForAssetReady")
	startTime := time.Now()
	checkInterval := 5 * time.Second

	log.Printf("Waiting for asset %s to be ready (timeout: %s)", assetID, timeout)

	for {
		// Check if timeout exceeded
		if time.Since(startTime) > timeout {
			z_slog.ReturnValues(map[string]any{"status": "", "duration": 0, "error": "timeout waiting for asset to be ready"})
			return "", 0, fmt.Errorf("timeout waiting for asset to be ready")
		}

		// Get asset status
		status, duration, err := c.GetAssetStatus(assetID)
		if err != nil {
			z_slog.ReturnValues(map[string]any{"status": "", "duration": 0, "error": err.Error()})
			return "", 0, err
		}

		// Check if asset is ready or errored
		if status == "ready" {
			log.Printf("Asset %s is ready (duration: %ds)", assetID, duration)
			z_slog.ReturnValues(map[string]any{"status": status, "duration": duration, "error": nil})
			return status, duration, nil
		} else if status == "error" {
			z_slog.ReturnValues(map[string]any{"status": status, "duration": 0, "error": "asset encoding failed"})
			return status, 0, fmt.Errorf("asset encoding failed")
		}

		// Wait before checking again
		log.Printf("Asset %s status: %s, checking again in %s", assetID, status, checkInterval)
		time.Sleep(checkInterval)
	}
}

// GetSignedPlaybackURL generates a signed playback URL for a playback ID
func (c *Client) GetSignedPlaybackURL(playbackID, token string) string {
	z_slog.FunctionEntry("GetSignedPlaybackURL")
	url := fmt.Sprintf("https://stream.mux.com/%s.m3u8?token=%s", playbackID, token)
	z_slog.ReturnValues(map[string]any{"url": "generated"})
	return url
}

// GetPublicPlaybackURL generates a public playback URL
func (c *Client) GetPublicPlaybackURL(playbackID string) string {
	z_slog.FunctionEntry("GetPublicPlaybackURL")
	url := fmt.Sprintf("https://stream.mux.com/%s.m3u8", playbackID)
	z_slog.ReturnValues(map[string]any{"url": url})
	return url
}

// GetThumbnailURL generates a thumbnail URL for a playback ID
func (c *Client) GetThumbnailURL(playbackID string, width int, time float64) string {
	z_slog.FunctionEntry("GetThumbnailURL")
	if width == 0 {
		width = 640
	}
	if time == 0 {
		time = 1.0
	}
	url := fmt.Sprintf("https://image.mux.com/%s/thumbnail.png?width=%d&time=%.1f", playbackID, width, time)
	z_slog.ReturnValues(map[string]any{"url": url})
	return url
}

// GetGifURL generates an animated GIF URL for a playback ID
func (c *Client) GetGifURL(playbackID string, width int, startTime, endTime float64) string {
	z_slog.FunctionEntry("GetGifURL")
	if width == 0 {
		width = 640
	}
	if startTime == 0 {
		startTime = 1.0
	}
	if endTime == 0 {
		endTime = 3.0
	}
	url := fmt.Sprintf("https://image.mux.com/%s/animated.gif?width=%d&start=%.1f&end=%.1f",
		playbackID, width, startTime, endTime)
	z_slog.ReturnValues(map[string]any{"url": url})
	return url
}

// ListAssets lists all assets
func (c *Client) ListAssets(limit int) ([]muxgo.Asset, error) {
	z_slog.FunctionEntry("ListAssets")
	if limit == 0 {
		limit = 25
	}

	assets, err := c.apiClient.AssetsApi.ListAssets()
	if err != nil {
		z_slog.ReturnValues(map[string]any{"assets": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to list assets: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"assetCount": len(assets.Data), "error": nil})
	return assets.Data, nil
}

// CreateSignedPlaybackID creates a new signed playback ID for an existing asset
func (c *Client) CreateSignedPlaybackID(assetID string) (string, error) {
	z_slog.FunctionEntry("CreateSignedPlaybackID")
	log.Printf("Creating signed playback ID for asset: %s", assetID)

	policy := muxgo.SIGNED
	createPlaybackIdRequest := muxgo.CreatePlaybackIdRequest{
		Policy: policy,
	}

	playbackID, err := c.apiClient.AssetsApi.CreateAssetPlaybackId(assetID, createPlaybackIdRequest)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"playbackID": "", "error": err.Error()})
		return "", fmt.Errorf("failed to create signed playback ID: %w", err)
	}

	log.Printf("Signed playback ID created: %s", playbackID.Data.Id)
	z_slog.ReturnValues(map[string]any{"playbackID": playbackID.Data.Id, "error": nil})
	return playbackID.Data.Id, nil
}

// mapMuxStatus maps Mux API status to our internal status
func mapMuxStatus(muxStatus string) string {
	z_slog.FunctionEntry("mapMuxStatus")
	var status string
	switch muxStatus {
	case "preparing":
		status = "encoding"
	case "ready":
		status = "ready"
	case "errored":
		status = "error"
	default:
		status = "encoding"
	}
	z_slog.ReturnValues(map[string]any{"status": status})
	return status
}
