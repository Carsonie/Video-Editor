package api

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/mux"
	"github.com/yourname/mux-example/internal/auth"
	"github.com/yourname/mux-example/internal/db"
	muxclient "github.com/yourname/mux-example/internal/mux"
	"github.com/yourname/mux-example/z_slog"
)

// Handler manages API endpoints
type Handler struct {
	db           *db.Database
	muxClient    *muxclient.Client
	tokenManager *auth.TokenManager
}

// NewHandler creates a new API handler
func NewHandler(database *db.Database, muxClient *muxclient.Client, tokenManager *auth.TokenManager) *Handler {
	z_slog.FunctionEntry("NewHandler")
	z_slog.Values(map[string]any{
		"database":     database,
		"muxClient":    muxClient,
		"tokenManager": tokenManager,
	})
	handler := &Handler{
		db:           database,
		muxClient:    muxClient,
		tokenManager: tokenManager,
	}
	z_slog.ReturnValues(map[string]any{
		"handler": handler,
	})
	return handler
}

// Video represents a video response
type Video struct {
	ID                   string    `json:"id"`
	Name                 string    `json:"name"`
	Description          string    `json:"description"`
	MuxAssetID           string    `json:"mux_asset_id"`
	MuxPlaybackID        string    `json:"mux_playback_id"`
	MuxSignedPlaybackID  string    `json:"mux_signed_playback_id"`
	Duration             int       `json:"duration"`
	Status               string    `json:"status"`
	ThumbnailUrl         string    `json:"thumbnail_url"`
	CreatedAt            time.Time `json:"created_at"`
	UpdatedAt            time.Time `json:"updated_at"`
}

// CreateVideoRequest represents the request to create a video
type CreateVideoRequest struct {
	URL         string `json:"url"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// CreatePlaybackTokenResponse represents the playback token response
type CreatePlaybackTokenResponse struct {
	Token          string    `json:"token"`
	Thumbnail      string    `json:"thumbnail"`
	Storyboard     string    `json:"storyboard"`
	ExpiresAt      time.Time `json:"expires_at"`
}

// CreateDirectUploadRequest represents the request to create a direct upload
type CreateDirectUploadRequest struct {
	CorsOrigin string `json:"cors_origin"`
}

// CreateDirectUploadResponse represents the direct upload response
type CreateDirectUploadResponse struct {
	UploadID  string `json:"upload_id"`
	UploadURL string `json:"upload_url"`
}

// CompleteDirectUploadRequest represents the request to complete a direct upload
type CompleteDirectUploadRequest struct {
	Name        string `json:"name"`
	Description string `json:"description"`
}

// ErrorResponse represents an error response
type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

// LoginRequest represents the login request
type LoginRequest struct {
	Name     string `json:"name"`
	Password string `json:"password"`
}

// LoginResponse represents the login response
type LoginResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
	Token   string `json:"token"`
	User    struct {
		ID   string `json:"id"`
		Name string `json:"name"`
		Role string `json:"role"`
	} `json:"user"`
}

// ListVideos handles GET /api/videos
func (h *Handler) ListVideos(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("ListVideos")
	z_slog.Values(map[string]any{})
	LogUserAction(r, "ListVideos")
	videos, err := h.db.ListVideos()
	if err != nil {
		log.Printf("Error listing videos: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to retrieve videos",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to retrieve videos")
		return
	}

	z_slog.ReturnValues(map[string]any{
		"status": http.StatusOK,
		"videos": videos,
	})
	respondWithJSON(w, http.StatusOK, videos)
}

// GetVideo handles GET /api/videos/{id}
func (h *Handler) GetVideo(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("GetVideo")
	vars := mux.Vars(r)
	videoID := vars["id"]
	z_slog.Values(map[string]any{
		"videoID": videoID,
	})
	LogUserActionWithDetails(r, "GetVideo", fmt.Sprintf("videoID=%s", videoID))

	video, err := h.db.GetVideo(videoID)
	if err != nil {
		log.Printf("Error getting video %s: %v", videoID, err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusNotFound,
			"error":  "Video not found",
		})
		respondWithError(w, http.StatusNotFound, "Video not found")
		return
	}

	z_slog.ReturnValues(map[string]any{
		"status": http.StatusOK,
		"video":  video,
	})
	respondWithJSON(w, http.StatusOK, video)
}

// CreateVideo handles POST /api/videos
func (h *Handler) CreateVideo(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("CreateVideo")
	LogUserAction(r, "CreateVideo")
	var req CreateVideoRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Invalid request body",
		})
		respondWithError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate request
	if req.URL == "" {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "URL is required",
		})
		respondWithError(w, http.StatusBadRequest, "URL is required")
		return
	}
	if req.Name == "" {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Name is required",
		})
		respondWithError(w, http.StatusBadRequest, "Name is required")
		return
	}

	z_slog.Values(map[string]any{
		"url":         req.URL,
		"name":        req.Name,
		"description": req.Description,
	})

	// Create Mux asset
	log.Printf("Creating Mux asset for URL: %s", req.URL)
	assetID, publicPlaybackID, signedPlaybackID, err := h.muxClient.CreateAssetFromURL(req.URL)
	if err != nil {
		log.Printf("Error creating Mux asset: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to create video asset",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to create video asset")
		return
	}

	// Create video in database
	video := &db.Video{
		Name:                req.Name,
		Description:         req.Description,
		MuxAssetID:          assetID,
		MuxPlaybackID:       publicPlaybackID,
		MuxSignedPlaybackID: signedPlaybackID,
		Status:              "encoding",
		Duration:            0,
	}

	if err := h.db.CreateVideo(video); err != nil {
		log.Printf("Error creating video in database: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to save video",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to save video")
		return
	}

	log.Printf("Video created successfully: %s (Mux Asset: %s)", video.ID, assetID)
	z_slog.ReturnValues(map[string]any{
		"status": http.StatusCreated,
		"video":  video,
	})
	respondWithJSON(w, http.StatusCreated, video)
}

// CreateDirectUpload handles POST /api/uploads/create
func (h *Handler) CreateDirectUpload(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("CreateDirectUpload")
	LogUserAction(r, "CreateDirectUpload")
	var req CreateDirectUploadRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Invalid request body",
		})
		respondWithError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Default to localhost if not provided
	corsOrigin := req.CorsOrigin
	if corsOrigin == "" {
		corsOrigin = "http://localhost:3000"
	}

	z_slog.Values(map[string]any{
		"corsOrigin": corsOrigin,
	})

	// Create direct upload in Mux
	uploadID, uploadURL, err := h.muxClient.CreateDirectUpload(corsOrigin)
	if err != nil {
		log.Printf("Error creating direct upload: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to create upload URL",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to create upload URL")
		return
	}

	response := CreateDirectUploadResponse{
		UploadID:  uploadID,
		UploadURL: uploadURL,
	}

	log.Printf("Direct upload created: %s", uploadID)
	z_slog.ReturnValues(map[string]any{
		"status":   http.StatusOK,
		"response": response,
	})
	respondWithJSON(w, http.StatusOK, response)
}

// CompleteDirectUpload handles POST /api/uploads/{id}/complete
func (h *Handler) CompleteDirectUpload(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("CompleteDirectUpload")
	vars := mux.Vars(r)
	uploadID := vars["id"]
	LogUserActionWithDetails(r, "CompleteDirectUpload", fmt.Sprintf("uploadID=%s", uploadID))

	var req CompleteDirectUploadRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Invalid request body",
		})
		respondWithError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate request
	if req.Name == "" {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Name is required",
		})
		respondWithError(w, http.StatusBadRequest, "Name is required")
		return
	}

	z_slog.Values(map[string]any{
		"uploadID":    uploadID,
		"name":        req.Name,
		"description": req.Description,
	})

	// Get asset from upload
	log.Printf("Completing direct upload: %s", uploadID)
	assetID, publicPlaybackID, signedPlaybackID, err := h.muxClient.GetAssetFromUpload(uploadID)
	if err != nil {
		log.Printf("Error getting asset from upload: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Upload not ready or failed",
		})
		respondWithError(w, http.StatusInternalServerError, "Upload not ready or failed")
		return
	}

	// Create video in database
	video := &db.Video{
		Name:                req.Name,
		Description:         req.Description,
		MuxAssetID:          assetID,
		MuxPlaybackID:       publicPlaybackID,
		MuxSignedPlaybackID: signedPlaybackID,
		Status:              "encoding",
		Duration:            0,
	}

	if err := h.db.CreateVideo(video); err != nil {
		log.Printf("Error creating video in database: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to save video",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to save video")
		return
	}

	log.Printf("Video created from upload: %s (Mux Asset: %s)", video.ID, assetID)
	z_slog.ReturnValues(map[string]any{
		"status": http.StatusCreated,
		"video":  video,
	})
	respondWithJSON(w, http.StatusCreated, video)
}

// Login handles POST /api/auth/login
func (h *Handler) Login(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("Login")
	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Invalid request body",
		})
		respondWithError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Validate request
	if req.Name == "" || req.Password == "" {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Name and password are required",
		})
		respondWithError(w, http.StatusBadRequest, "Name and password are required")
		return
	}

	z_slog.Values(map[string]any{
		"name": req.Name,
		// password intentionally omitted for security
	})

	log.Printf("Login attempt for user: %s", req.Name)

	// Get user from database
	user, err := h.db.GetUserByName(req.Name)
	if err != nil {
		log.Printf("User %s not found: %v", req.Name, err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusUnauthorized,
			"error":  "Invalid credentials",
		})
		respondWithError(w, http.StatusUnauthorized, "Invalid credentials")
		return
	}

	// Check password (plain text comparison for now - should use bcrypt in production)
	if user.Password != req.Password {
		log.Printf("Invalid password for user %s", req.Name)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusUnauthorized,
			"error":  "Invalid credentials",
		})
		respondWithError(w, http.StatusUnauthorized, "Invalid credentials")
		return
	}

	// Generate session token
	token, err := generateSessionToken()
	if err != nil {
		log.Printf("Error generating session token: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to create session",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to create session")
		return
	}

	// Create session in database (expires in 24 hours)
	expiresAt := time.Now().Add(24 * time.Hour)
	_, err = h.db.CreateSession(user.ID, token, expiresAt)
	if err != nil {
		log.Printf("Error creating session: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to create session",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to create session")
		return
	}

	// Start user-specific logging
	if err := z_slog.StartUserLogging(user.Name); err != nil {
		log.Printf("Error starting user logging for %s: %v", user.Name, err)
	}

	// Build response
	response := LoginResponse{
		Success: true,
		Message: "Login successful",
		Token:   token,
	}
	response.User.ID = user.ID
	response.User.Name = user.Name
	response.User.Role = user.RoleName

	log.Printf("User %s logged in successfully with role %s", user.Name, user.RoleName)
	z_slog.ReturnValues(map[string]any{
		"status":   http.StatusOK,
		"response": response,
	})
	respondWithJSON(w, http.StatusOK, response)
}

// Logout handles POST /api/auth/logout
func (h *Handler) Logout(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("Logout")

	// Get user from context before deleting session
	user := GetUserFromContext(r)
	if user != nil {
		z_slog.Values(map[string]any{
			"username": user.Name,
		})
	} else {
		z_slog.Values(map[string]any{})
	}

	// Get token from Authorization header
	token := extractTokenFromRequest(r)
	if token == "" {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusUnauthorized,
			"error":  "No token provided",
		})
		respondWithError(w, http.StatusUnauthorized, "No token provided")
		return
	}

	// Delete session from database
	err := h.db.DeleteSession(token)
	if err != nil {
		log.Printf("Error deleting session: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to logout",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to logout")
		return
	}

	// Stop user-specific logging
	if user != nil {
		// Log the logout action to user's log file before stopping
		LogUserActionWithDetails(r, "Logout", "User session ended")
		z_slog.StopUserLogging(user.Name)
		log.Printf("User %s logged out successfully", user.Name)
	} else {
		log.Printf("User logged out successfully")
	}

	result := map[string]interface{}{
		"success": true,
		"message": "Logged out successfully",
	}
	z_slog.ReturnValues(map[string]any{
		"status": http.StatusOK,
		"result": result,
	})
	respondWithJSON(w, http.StatusOK, result)
}

// generateSessionToken generates a secure random session token
func generateSessionToken() (string, error) {
	z_slog.FunctionEntry("generateSessionToken")
	z_slog.Values(map[string]any{})
	b := make([]byte, 32)
	_, err := rand.Read(b)
	if err != nil {
		z_slog.ReturnValues(map[string]any{
			"token": "",
			"error": err,
		})
		return "", err
	}
	token := base64.URLEncoding.EncodeToString(b)
	z_slog.ReturnValues(map[string]any{
		"token": token,
		"error": nil,
	})
	return token, nil
}

// CreatePlaybackToken handles POST /api/videos/{id}/playback-token
func (h *Handler) CreatePlaybackToken(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("CreatePlaybackToken")
	vars := mux.Vars(r)
	videoID := vars["id"]
	z_slog.Values(map[string]any{
		"videoID": videoID,
	})
	LogUserActionWithDetails(r, "CreatePlaybackToken", fmt.Sprintf("videoID=%s", videoID))

	// Get video from database
	video, err := h.db.GetVideo(videoID)
	if err != nil {
		log.Printf("Error getting video %s: %v", videoID, err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusNotFound,
			"error":  "Video not found",
		})
		respondWithError(w, http.StatusNotFound, "Video not found")
		return
	}

	// Check if video is ready
	if video.Status != "ready" {
		errMsg := fmt.Sprintf("Video is not ready (status: %s)", video.Status)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  errMsg,
		})
		respondWithError(w, http.StatusBadRequest, errMsg)
		return
	}

	// Check if this video has a signed playback ID
	// Public-only videos don't have signed playback IDs and don't need tokens
	if video.MuxSignedPlaybackID == "" {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusNotFound,
			"error":  "This video uses public playback and does not require tokens",
		})
		respondWithError(w, http.StatusNotFound, "This video uses public playback and does not require tokens")
		return
	}

	// Generate JWT tokens (expires in 1 hour)
	expiresIn := time.Hour

	// Generate playback token (audience: "v")
	token, err := h.tokenManager.GeneratePlaybackToken(video.ID, video.MuxSignedPlaybackID, expiresIn)
	if err != nil {
		log.Printf("Error generating playback token: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to generate playback token",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to generate playback token")
		return
	}

	// Generate thumbnail token (audience: "t")
	thumbnailToken, err := h.tokenManager.GenerateThumbnailToken(video.MuxSignedPlaybackID, expiresIn)
	if err != nil {
		log.Printf("Error generating thumbnail token: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to generate thumbnail token",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to generate thumbnail token")
		return
	}

	// Generate storyboard token (audience: "s")
	storyboardToken, err := h.tokenManager.GenerateStoryboardToken(video.MuxSignedPlaybackID, expiresIn)
	if err != nil {
		log.Printf("Error generating storyboard token: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to generate storyboard token",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to generate storyboard token")
		return
	}

	expiresAt := time.Now().Add(expiresIn)

	// Return tokens directly (no database storage needed)
	// Tokens are self-contained and can be regenerated on-demand
	response := CreatePlaybackTokenResponse{
		Token:      token,
		Thumbnail:  thumbnailToken,
		Storyboard: storyboardToken,
		ExpiresAt:  expiresAt,
	}

	z_slog.ReturnValues(map[string]any{
		"status":   http.StatusOK,
		"response": response,
	})
	respondWithJSON(w, http.StatusOK, response)
}

// GetVideoStatus handles GET /api/videos/{id}/status
func (h *Handler) GetVideoStatus(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("GetVideoStatus")
	vars := mux.Vars(r)
	videoID := vars["id"]
	z_slog.Values(map[string]any{
		"videoID": videoID,
	})
	LogUserActionWithDetails(r, "GetVideoStatus", fmt.Sprintf("videoID=%s", videoID))

	// Get video from database
	video, err := h.db.GetVideo(videoID)
	if err != nil {
		log.Printf("Error getting video %s: %v", videoID, err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusNotFound,
			"error":  "Video not found",
		})
		respondWithError(w, http.StatusNotFound, "Video not found")
		return
	}

	// Check status from Mux
	status, duration, err := h.muxClient.GetAssetStatus(video.MuxAssetID)
	if err != nil {
		log.Printf("Error getting asset status from Mux: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusInternalServerError,
			"error":  "Failed to check video status",
		})
		respondWithError(w, http.StatusInternalServerError, "Failed to check video status")
		return
	}

	// Update video status in database if changed
	if video.Status != status || video.Duration != duration {
		video.Status = status
		video.Duration = duration
		if err := h.db.UpdateVideo(video); err != nil {
			log.Printf("Error updating video status: %v", err)
			// Continue anyway, we can still return the status
		}
	}

	result := map[string]interface{}{
		"video_id": video.ID,
		"status":   status,
		"duration": duration,
	}
	z_slog.ReturnValues(map[string]any{
		"status": http.StatusOK,
		"result": result,
	})
	respondWithJSON(w, http.StatusOK, result)
}

// HandleMuxWebhook handles POST /webhooks/mux
func (h *Handler) HandleMuxWebhook(w http.ResponseWriter, r *http.Request) {
	z_slog.FunctionEntry("HandleMuxWebhook")
	var webhook map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&webhook); err != nil {
		log.Printf("Error decoding webhook: %v", err)
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Invalid webhook payload",
		})
		respondWithError(w, http.StatusBadRequest, "Invalid webhook payload")
		return
	}

	// Log webhook for debugging
	log.Printf("Received Mux webhook: %v", webhook)

	// Extract webhook type
	webhookType, ok := webhook["type"].(string)
	if !ok {
		z_slog.ReturnValues(map[string]any{
			"status": http.StatusBadRequest,
			"error":  "Invalid webhook type",
		})
		respondWithError(w, http.StatusBadRequest, "Invalid webhook type")
		return
	}

	z_slog.Values(map[string]any{
		"webhookType": webhookType,
		"webhook":     webhook,
	})

	// Handle different webhook types
	switch webhookType {
	case "video.asset.ready":
		h.handleAssetReady(webhook)
	case "video.asset.errored":
		h.handleAssetErrored(webhook)
	default:
		log.Printf("Unhandled webhook type: %s", webhookType)
	}

	// Acknowledge webhook
	result := map[string]string{"status": "received"}
	z_slog.ReturnValues(map[string]any{
		"status": http.StatusOK,
		"result": result,
	})
	respondWithJSON(w, http.StatusOK, result)
}

// handleAssetReady handles video.asset.ready webhook
func (h *Handler) handleAssetReady(webhook map[string]interface{}) {
	z_slog.FunctionEntry("handleAssetReady")
	z_slog.Values(map[string]any{
		"webhook": webhook,
	})
	data, ok := webhook["data"].(map[string]interface{})
	if !ok {
		log.Println("Invalid webhook data")
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   "Invalid webhook data",
		})
		return
	}

	assetID, ok := data["id"].(string)
	if !ok {
		log.Println("Invalid asset ID in webhook")
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   "Invalid asset ID in webhook",
		})
		return
	}

	// Find video by Mux asset ID
	video, err := h.db.GetVideoByMuxAssetID(assetID)
	if err != nil {
		log.Printf("Error finding video for asset %s: %v", assetID, err)
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   fmt.Sprintf("Error finding video for asset %s", assetID),
		})
		return
	}

	// Update video status
	video.Status = "ready"
	if duration, ok := data["duration"].(float64); ok {
		video.Duration = int(duration)
	}

	if err := h.db.UpdateVideo(video); err != nil {
		log.Printf("Error updating video status: %v", err)
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   "Error updating video status",
		})
	} else {
		log.Printf("Video %s marked as ready", video.ID)
		z_slog.ReturnValues(map[string]any{
			"success": true,
			"videoID": video.ID,
			"status":  "ready",
		})
	}
}

// handleAssetErrored handles video.asset.errored webhook
func (h *Handler) handleAssetErrored(webhook map[string]interface{}) {
	z_slog.FunctionEntry("handleAssetErrored")
	z_slog.Values(map[string]any{
		"webhook": webhook,
	})
	data, ok := webhook["data"].(map[string]interface{})
	if !ok {
		log.Println("Invalid webhook data")
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   "Invalid webhook data",
		})
		return
	}

	assetID, ok := data["id"].(string)
	if !ok {
		log.Println("Invalid asset ID in webhook")
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   "Invalid asset ID in webhook",
		})
		return
	}

	// Find video by Mux asset ID
	video, err := h.db.GetVideoByMuxAssetID(assetID)
	if err != nil {
		log.Printf("Error finding video for asset %s: %v", assetID, err)
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   fmt.Sprintf("Error finding video for asset %s", assetID),
		})
		return
	}

	// Update video status
	video.Status = "error"

	if err := h.db.UpdateVideo(video); err != nil {
		log.Printf("Error updating video status: %v", err)
		z_slog.ReturnValues(map[string]any{
			"success": false,
			"error":   "Error updating video status",
		})
	} else {
		log.Printf("Video %s marked as error", video.ID)
		z_slog.ReturnValues(map[string]any{
			"success": true,
			"videoID": video.ID,
			"status":  "error",
		})
	}
}

// respondWithJSON sends a JSON response
func respondWithJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(data); err != nil {
		z_slog.Failed("Error encoding JSON response", "error", err)
	}
}

// respondWithError sends an error response
func respondWithError(w http.ResponseWriter, status int, message string) {
	response := ErrorResponse{
		Error:   http.StatusText(status),
		Message: message,
	}
	respondWithJSON(w, status, response)
}
