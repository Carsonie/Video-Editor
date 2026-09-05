package db

import (
	"database/sql"
	"fmt"
	"math/rand"
	"time"

	_ "github.com/mattn/go-sqlite3"
	"github.com/yourname/mux-example/z_slog"
)

// Database manages the SQLite database connection
type Database struct {
	db *sql.DB
}

// New creates a new database connection
func New(dbPath string) (*Database, error) {
	z_slog.FunctionEntry("New")
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"database": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	// Test connection
	if err := db.Ping(); err != nil {
		z_slog.ReturnValues(map[string]any{"database": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"database": "Database", "error": nil})
	return &Database{db: db}, nil
}

// Close closes the database connection
func (d *Database) Close() error {
	z_slog.FunctionEntry("Close")
	err := d.db.Close()
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
	} else {
		z_slog.ReturnValues(map[string]any{"error": nil})
	}
	return err
}

// Migrate runs database migrations
func (d *Database) Migrate() error {
	z_slog.FunctionEntry("Migrate")
	// Create videos table
	if _, err := d.db.Exec(CreateVideosTableSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create videos table: %w", err)
	}

	// Create playback_tokens table
	if _, err := d.db.Exec(CreatePlaybackTokensTableSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create playback_tokens table: %w", err)
	}

	// Create roles table
	if _, err := d.db.Exec(CreateRolesTableSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create roles table: %w", err)
	}

	// Create users table
	if _, err := d.db.Exec(CreateUsersTableSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create users table: %w", err)
	}

	// Create sessions table
	if _, err := d.db.Exec(CreateSessionsTableSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create sessions table: %w", err)
	}

	// Create indexes
	if _, err := d.db.Exec(CreateIndexesSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create indexes: %w", err)
	}

	// Create session indexes
	if _, err := d.db.Exec(CreateSessionIndexesSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create session indexes: %w", err)
	}

	// Insert default roles
	if _, err := d.db.Exec(InsertDefaultRolesSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to insert default roles: %w", err)
	}

	// Insert default users
	if _, err := d.db.Exec(InsertDefaultUsersSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to insert default users: %w", err)
	}

	// Insert default videos
	if _, err := d.db.Exec(InsertDefaultVideosSQL); err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to insert default videos: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// CreateVideo creates a new video record
func (d *Database) CreateVideo(video *Video) error {
	z_slog.FunctionEntry("CreateVideo")
	video.ID = generateID("video")
	video.CreatedAt = time.Now()
	video.UpdatedAt = time.Now()

	query := `
		INSERT INTO videos (id, name, description, mux_asset_id, mux_playback_id, mux_signed_playback_id, duration, status, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := d.db.Exec(query,
		video.ID,
		video.Name,
		video.Description,
		video.MuxAssetID,
		video.MuxPlaybackID,
		video.MuxSignedPlaybackID,
		video.Duration,
		video.Status,
		video.CreatedAt,
		video.UpdatedAt,
	)

	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create video: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"videoID": video.ID, "error": nil})
	return nil
}

// GetVideo retrieves a video by ID
func (d *Database) GetVideo(id string) (*Video, error) {
	z_slog.FunctionEntry("GetVideo")
	query := `
		SELECT id, name, description, mux_asset_id, mux_playback_id, mux_signed_playback_id, duration, status, thumbnail_url, created_at, updated_at
		FROM videos
		WHERE id = ?
	`

	video := &Video{}
	err := d.db.QueryRow(query, id).Scan(
		&video.ID,
		&video.Name,
		&video.Description,
		&video.MuxAssetID,
		&video.MuxPlaybackID,
		&video.MuxSignedPlaybackID,
		&video.Duration,
		&video.Status,
		&video.ThumbnailUrl,
		&video.CreatedAt,
		&video.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		z_slog.ReturnValues(map[string]any{"video": nil, "error": "video not found"})
		return nil, fmt.Errorf("video not found")
	}
	if err != nil {
		z_slog.ReturnValues(map[string]any{"video": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get video: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"videoID": video.ID, "error": nil})
	return video, nil
}

// GetVideoByMuxAssetID retrieves a video by Mux asset ID
func (d *Database) GetVideoByMuxAssetID(assetID string) (*Video, error) {
	z_slog.FunctionEntry("GetVideoByMuxAssetID")
	query := `
		SELECT id, name, description, mux_asset_id, mux_playback_id, mux_signed_playback_id, duration, status, thumbnail_url, created_at, updated_at
		FROM videos
		WHERE mux_asset_id = ?
	`

	video := &Video{}
	err := d.db.QueryRow(query, assetID).Scan(
		&video.ID,
		&video.Name,
		&video.Description,
		&video.MuxAssetID,
		&video.MuxPlaybackID,
		&video.MuxSignedPlaybackID,
		&video.Duration,
		&video.Status,
		&video.ThumbnailUrl,
		&video.CreatedAt,
		&video.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		z_slog.ReturnValues(map[string]any{"video": nil, "error": "video not found"})
		return nil, fmt.Errorf("video not found")
	}
	if err != nil {
		z_slog.ReturnValues(map[string]any{"video": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get video: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"videoID": video.ID, "error": nil})
	return video, nil
}

// ListVideos retrieves all videos
func (d *Database) ListVideos() ([]*Video, error) {
	z_slog.FunctionEntry("ListVideos")
	query := `
		SELECT id, name, description, mux_asset_id, mux_playback_id, mux_signed_playback_id, duration, status, thumbnail_url, created_at, updated_at
		FROM videos
		ORDER BY created_at DESC
	`

	rows, err := d.db.Query(query)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"videos": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to list videos: %w", err)
	}
	defer rows.Close()

	videos := []*Video{}
	for rows.Next() {
		video := &Video{}
		err := rows.Scan(
			&video.ID,
			&video.Name,
			&video.Description,
			&video.MuxAssetID,
			&video.MuxPlaybackID,
			&video.MuxSignedPlaybackID,
			&video.Duration,
			&video.Status,
			&video.ThumbnailUrl,
			&video.CreatedAt,
			&video.UpdatedAt,
		)
		if err != nil {
			z_slog.ReturnValues(map[string]any{"videos": nil, "error": err.Error()})
			return nil, fmt.Errorf("failed to scan video: %w", err)
		}
		videos = append(videos, video)
	}

	if err := rows.Err(); err != nil {
		z_slog.ReturnValues(map[string]any{"videos": nil, "error": err.Error()})
		return nil, fmt.Errorf("error iterating videos: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"videoCount": len(videos), "error": nil})
	return videos, nil
}

// UpdateVideo updates a video record
func (d *Database) UpdateVideo(video *Video) error {
	z_slog.FunctionEntry("UpdateVideo")
	video.UpdatedAt = time.Now()

	query := `
		UPDATE videos
		SET name = ?, description = ?, mux_asset_id = ?, mux_playback_id = ?, mux_signed_playback_id = ?, duration = ?, status = ?, updated_at = ?
		WHERE id = ?
	`

	result, err := d.db.Exec(query,
		video.Name,
		video.Description,
		video.MuxAssetID,
		video.MuxPlaybackID,
		video.MuxSignedPlaybackID,
		video.Duration,
		video.Status,
		video.UpdatedAt,
		video.ID,
	)

	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to update video: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		z_slog.ReturnValues(map[string]any{"error": "video not found"})
		return fmt.Errorf("video not found")
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// DeleteVideo deletes a video record
func (d *Database) DeleteVideo(id string) error {
	z_slog.FunctionEntry("DeleteVideo")
	query := `DELETE FROM videos WHERE id = ?`

	result, err := d.db.Exec(query, id)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to delete video: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		z_slog.ReturnValues(map[string]any{"error": "video not found"})
		return fmt.Errorf("video not found")
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// CreatePlaybackToken creates a new playback token record
func (d *Database) CreatePlaybackToken(token *PlaybackToken) error {
	z_slog.FunctionEntry("CreatePlaybackToken")
	token.ID = generateID("token")
	token.CreatedAt = time.Now()

	query := `
		INSERT INTO playback_tokens (id, video_id, jwt_token, expires_at, created_at)
		VALUES (?, ?, ?, ?, ?)
	`

	_, err := d.db.Exec(query,
		token.ID,
		token.VideoID,
		token.JWTToken,
		token.ExpiresAt,
		token.CreatedAt,
	)

	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to create playback token: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"tokenID": token.ID, "error": nil})
	return nil
}

// GetPlaybackToken retrieves a playback token by ID
func (d *Database) GetPlaybackToken(id string) (*PlaybackToken, error) {
	z_slog.FunctionEntry("GetPlaybackToken")
	query := `
		SELECT id, video_id, jwt_token, expires_at, created_at
		FROM playback_tokens
		WHERE id = ?
	`

	token := &PlaybackToken{}
	err := d.db.QueryRow(query, id).Scan(
		&token.ID,
		&token.VideoID,
		&token.JWTToken,
		&token.ExpiresAt,
		&token.CreatedAt,
	)

	if err == sql.ErrNoRows {
		z_slog.ReturnValues(map[string]any{"token": nil, "error": "playback token not found"})
		return nil, fmt.Errorf("playback token not found")
	}
	if err != nil {
		z_slog.ReturnValues(map[string]any{"token": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get playback token: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"tokenID": token.ID, "error": nil})
	return token, nil
}

// ListPlaybackTokensByVideoID retrieves all playback tokens for a video
func (d *Database) ListPlaybackTokensByVideoID(videoID string) ([]*PlaybackToken, error) {
	z_slog.FunctionEntry("ListPlaybackTokensByVideoID")
	query := `
		SELECT id, video_id, jwt_token, expires_at, created_at
		FROM playback_tokens
		WHERE video_id = ?
		ORDER BY created_at DESC
	`

	rows, err := d.db.Query(query, videoID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"tokens": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to list playback tokens: %w", err)
	}
	defer rows.Close()

	tokens := []*PlaybackToken{}
	for rows.Next() {
		token := &PlaybackToken{}
		err := rows.Scan(
			&token.ID,
			&token.VideoID,
			&token.JWTToken,
			&token.ExpiresAt,
			&token.CreatedAt,
		)
		if err != nil {
			z_slog.ReturnValues(map[string]any{"tokens": nil, "error": err.Error()})
			return nil, fmt.Errorf("failed to scan playback token: %w", err)
		}
		tokens = append(tokens, token)
	}

	if err := rows.Err(); err != nil {
		z_slog.ReturnValues(map[string]any{"tokens": nil, "error": err.Error()})
		return nil, fmt.Errorf("error iterating playback tokens: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"tokenCount": len(tokens), "error": nil})
	return tokens, nil
}

// CleanupExpiredTokens removes expired playback tokens
func (d *Database) CleanupExpiredTokens() error {
	z_slog.FunctionEntry("CleanupExpiredTokens")
	query := `DELETE FROM playback_tokens WHERE expires_at < ?`

	_, err := d.db.Exec(query, time.Now())
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to cleanup expired tokens: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// GetUserByName retrieves a user by name with their role information
func (d *Database) GetUserByName(name string) (*User, error) {
	z_slog.FunctionEntry("GetUserByName")
	query := `
		SELECT u.id, u.name, u.password, u.role_id, r.name as role_name, u.created_at, u.updated_at
		FROM users u
		JOIN roles r ON u.role_id = r.id
		WHERE u.name = ?
	`

	user := &User{}
	err := d.db.QueryRow(query, name).Scan(
		&user.ID,
		&user.Name,
		&user.Password,
		&user.RoleID,
		&user.RoleName,
		&user.CreatedAt,
		&user.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		z_slog.ReturnValues(map[string]any{"user": nil, "error": "user not found"})
		return nil, fmt.Errorf("user not found")
	}
	if err != nil {
		z_slog.ReturnValues(map[string]any{"user": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"userID": user.ID, "error": nil})
	return user, nil
}

// ListUsers retrieves all users
func (d *Database) ListUsers() ([]*User, error) {
	z_slog.FunctionEntry("ListUsers")
	query := `
		SELECT u.id, u.name, u.password, u.role_id, r.name as role_name, u.created_at, u.updated_at
		FROM users u
		JOIN roles r ON u.role_id = r.id
		ORDER BY u.created_at DESC
	`

	rows, err := d.db.Query(query)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"users": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to list users: %w", err)
	}
	defer rows.Close()

	users := []*User{}
	for rows.Next() {
		user := &User{}
		err := rows.Scan(
			&user.ID,
			&user.Name,
			&user.Password,
			&user.RoleID,
			&user.RoleName,
			&user.CreatedAt,
			&user.UpdatedAt,
		)
		if err != nil {
			z_slog.ReturnValues(map[string]any{"users": nil, "error": err.Error()})
			return nil, fmt.Errorf("failed to scan user: %w", err)
		}
		users = append(users, user)
	}

	if err := rows.Err(); err != nil {
		z_slog.ReturnValues(map[string]any{"users": nil, "error": err.Error()})
		return nil, fmt.Errorf("error iterating users: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"userCount": len(users), "error": nil})
	return users, nil
}

// GetRoleByID retrieves a role by ID
func (d *Database) GetRoleByID(id string) (*Role, error) {
	z_slog.FunctionEntry("GetRoleByID")
	query := `SELECT id, name, created_at FROM roles WHERE id = ?`

	role := &Role{}
	err := d.db.QueryRow(query, id).Scan(
		&role.ID,
		&role.Name,
		&role.CreatedAt,
	)

	if err == sql.ErrNoRows {
		z_slog.ReturnValues(map[string]any{"role": nil, "error": "role not found"})
		return nil, fmt.Errorf("role not found")
	}
	if err != nil {
		z_slog.ReturnValues(map[string]any{"role": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to get role: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"roleID": role.ID, "error": nil})
	return role, nil
}

// ListRoles retrieves all roles
func (d *Database) ListRoles() ([]*Role, error) {
	z_slog.FunctionEntry("ListRoles")
	query := `SELECT id, name, created_at FROM roles ORDER BY name`

	rows, err := d.db.Query(query)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"roles": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to list roles: %w", err)
	}
	defer rows.Close()

	roles := []*Role{}
	for rows.Next() {
		role := &Role{}
		err := rows.Scan(
			&role.ID,
			&role.Name,
			&role.CreatedAt,
		)
		if err != nil {
			z_slog.ReturnValues(map[string]any{"roles": nil, "error": err.Error()})
			return nil, fmt.Errorf("failed to scan role: %w", err)
		}
		roles = append(roles, role)
	}

	if err := rows.Err(); err != nil {
		z_slog.ReturnValues(map[string]any{"roles": nil, "error": err.Error()})
		return nil, fmt.Errorf("error iterating roles: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"roleCount": len(roles), "error": nil})
	return roles, nil
}

// CreateSession creates a new session for a user
func (d *Database) CreateSession(userID string, token string, expiresAt time.Time) (*Session, error) {
	z_slog.FunctionEntry("CreateSession")
	session := &Session{
		ID:        generateID("session"),
		UserID:    userID,
		Token:     token,
		ExpiresAt: expiresAt,
		CreatedAt: time.Now(),
	}

	query := `
		INSERT INTO sessions (id, user_id, token, expires_at, created_at)
		VALUES (?, ?, ?, ?, ?)
	`

	_, err := d.db.Exec(query,
		session.ID,
		session.UserID,
		session.Token,
		session.ExpiresAt,
		session.CreatedAt,
	)

	if err != nil {
		z_slog.ReturnValues(map[string]any{"session": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to create session: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"sessionID": session.ID, "error": nil})
	return session, nil
}

// GetSessionByToken retrieves a session by token
func (d *Database) GetSessionByToken(token string) (*Session, *User, error) {
	z_slog.FunctionEntry("GetSessionByToken")
	query := `
		SELECT s.id, s.user_id, s.token, s.expires_at, s.created_at,
		       u.id, u.name, u.role_id, r.name as role_name, u.created_at, u.updated_at
		FROM sessions s
		JOIN users u ON s.user_id = u.id
		JOIN roles r ON u.role_id = r.id
		WHERE s.token = ? AND s.expires_at > ?
	`

	session := &Session{}
	user := &User{}
	err := d.db.QueryRow(query, token, time.Now()).Scan(
		&session.ID,
		&session.UserID,
		&session.Token,
		&session.ExpiresAt,
		&session.CreatedAt,
		&user.ID,
		&user.Name,
		&user.RoleID,
		&user.RoleName,
		&user.CreatedAt,
		&user.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		z_slog.ReturnValues(map[string]any{"session": nil, "user": nil, "error": "session not found or expired"})
		return nil, nil, fmt.Errorf("session not found or expired")
	}
	if err != nil {
		z_slog.ReturnValues(map[string]any{"session": nil, "user": nil, "error": err.Error()})
		return nil, nil, fmt.Errorf("failed to get session: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"sessionID": session.ID, "userID": user.ID, "error": nil})
	return session, user, nil
}

// DeleteSession deletes a session (logout)
func (d *Database) DeleteSession(token string) error {
	z_slog.FunctionEntry("DeleteSession")
	query := `DELETE FROM sessions WHERE token = ?`

	result, err := d.db.Exec(query, token)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to delete session: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		z_slog.ReturnValues(map[string]any{"error": "session not found"})
		return fmt.Errorf("session not found")
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// DeleteUserSessions deletes all sessions for a user
func (d *Database) DeleteUserSessions(userID string) error {
	z_slog.FunctionEntry("DeleteUserSessions")
	query := `DELETE FROM sessions WHERE user_id = ?`

	_, err := d.db.Exec(query, userID)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to delete user sessions: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// CleanupExpiredSessions removes expired sessions
func (d *Database) CleanupExpiredSessions() error {
	z_slog.FunctionEntry("CleanupExpiredSessions")
	query := `DELETE FROM sessions WHERE expires_at < ?`

	_, err := d.db.Exec(query, time.Now())
	if err != nil {
		z_slog.ReturnValues(map[string]any{"error": err.Error()})
		return fmt.Errorf("failed to cleanup expired sessions: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"error": nil})
	return nil
}

// generateID generates a unique ID with the given prefix
// Format: prefix_timestamp_random (e.g., video_1234567890_abc123)
func generateID(prefix string) string {
	z_slog.FunctionEntry("generateID")
	timestamp := time.Now().Unix()
	random := rand.Intn(99999999)
	id := fmt.Sprintf("%s_%d_%08d", prefix, timestamp, random)
	z_slog.ReturnValues(map[string]any{"id": id})
	return id
}
