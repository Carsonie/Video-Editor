package db

import (
	"time"
)

// Video represents a video record in the database
type Video struct {
	ID                  string    `json:"id"`
	Name                string    `json:"name"`
	Description         string    `json:"description"`
	MuxAssetID          string    `json:"mux_asset_id"`
	MuxPlaybackID       string    `json:"mux_playback_id"`
	MuxSignedPlaybackID string    `json:"mux_signed_playback_id"`
	Duration            int       `json:"duration"`
	Status              string    `json:"status"` // encoding, ready, error
	ThumbnailUrl        string    `json:"thumbnail_url"`
	CreatedAt           time.Time `json:"created_at"`
	UpdatedAt           time.Time `json:"updated_at"`
}

// PlaybackToken represents a playback token record in the database
type PlaybackToken struct {
	ID        string    `json:"id"`
	VideoID   string    `json:"video_id"`
	JWTToken  string    `json:"jwt_token"`
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
}

// Role represents a role record in the database
type Role struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	CreatedAt time.Time `json:"created_at"`
}

// User represents a user record in the database
type User struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Password  string    `json:"-"` // Never expose password in JSON
	RoleID    string    `json:"role_id"`
	RoleName  string    `json:"role_name"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// Session represents a user session record in the database
type Session struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	Token     string    `json:"token"`
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
}

// Schema SQL statements for database tables
const (
	// CreateVideosTableSQL creates the videos table
	CreateVideosTableSQL = `
		CREATE TABLE IF NOT EXISTS videos (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL,
			description TEXT,
			mux_asset_id TEXT NOT NULL,
			mux_playback_id TEXT NOT NULL,
			mux_signed_playback_id TEXT NOT NULL,
			duration INTEGER DEFAULT 0,
			status TEXT NOT NULL DEFAULT 'encoding',
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
		);
	`

	// CreatePlaybackTokensTableSQL creates the playback_tokens table
	CreatePlaybackTokensTableSQL = `
		CREATE TABLE IF NOT EXISTS playback_tokens (
			id TEXT PRIMARY KEY,
			video_id TEXT NOT NULL,
			jwt_token TEXT NOT NULL,
			expires_at TIMESTAMP NOT NULL,
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
		);
	`

	// CreateIndexesSQL creates indexes for performance
	CreateIndexesSQL = `
		CREATE INDEX IF NOT EXISTS idx_videos_mux_asset_id ON videos(mux_asset_id);
		CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
		CREATE INDEX IF NOT EXISTS idx_playback_tokens_video_id ON playback_tokens(video_id);
		CREATE INDEX IF NOT EXISTS idx_playback_tokens_expires_at ON playback_tokens(expires_at);
	`

	// CreateRolesTableSQL creates the roles table
	CreateRolesTableSQL = `
		CREATE TABLE IF NOT EXISTS roles (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL UNIQUE,
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
		);
	`

	// CreateUsersTableSQL creates the users table
	CreateUsersTableSQL = `
		CREATE TABLE IF NOT EXISTS users (
			id TEXT PRIMARY KEY,
			name TEXT NOT NULL UNIQUE,
			password TEXT NOT NULL,
			role_id TEXT NOT NULL,
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
		);
	`

	// InsertDefaultRolesSQL inserts the default roles
	InsertDefaultRolesSQL = `
		INSERT OR IGNORE INTO roles (id, name) VALUES
			('role_bcp_admin', 'BCP-Admin'),
			('role_visitor', 'Visitor');
	`

	// InsertDefaultUsersSQL inserts the default users
	InsertDefaultUsersSQL = `
		INSERT OR IGNORE INTO users (id, name, password, role_id) VALUES
			('user_harry', 'Harry', '1234', 'role_bcp_admin'),
			('user_sam', 'Sam', '1234', 'role_visitor');
	`

	// InsertDefaultVideosSQL inserts the default Knot video
	InsertDefaultVideosSQL = `
		INSERT OR IGNORE INTO videos (id, name, description, mux_asset_id, mux_playback_id, mux_signed_playback_id, duration, status, created_at, updated_at)
		VALUES (
			'video_knot_001',
			'Knot Tutorial',
			'Learn how to tie the perfect knot - UHD 4K video demonstration',
			'gUeDK959B2j019DyEJO4c3600m6IgNCPFc9OA6NIYP2CE',
			'2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo',
			'2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo',
			12,
			'ready',
			CURRENT_TIMESTAMP,
			CURRENT_TIMESTAMP
		);
	`

	// CreateSessionsTableSQL creates the sessions table
	CreateSessionsTableSQL = `
		CREATE TABLE IF NOT EXISTS sessions (
			id TEXT PRIMARY KEY,
			user_id TEXT NOT NULL,
			token TEXT NOT NULL UNIQUE,
			expires_at TIMESTAMP NOT NULL,
			created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
			FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
		);
	`

	// CreateSessionIndexesSQL creates indexes for sessions table
	CreateSessionIndexesSQL = `
		CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
		CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
		CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
	`
)
