package main

import (
	"log/slog"
	"time"

	"github.com/yourname/mux-example/z_slog"
)

// To Run (from backend directory): go run ./z_slog/examples/main.go
// Or from project root: cd backend && go run ./z_slog/examples/main.go

func main() {
	println("\n=== Z_SLOG LOGGING EXAMPLES ===\n")

	println("--- Running with DEBUG=false ---\n")
	z_slog.Init(false)
	defer z_slog.Close() // Ensure log file is closed on exit
	demonstrateLogging()

	println("\n\n--- Running with DEBUG=true ---\n")
	z_slog.Init(true)
	demonstrateLogging()

	println("\n=== END OF EXAMPLES ===\n")
}

func demonstrateLogging() {
	// Standard log levels
	println("Standard Log Levels:")
	slog.Info("This is an INFO message")
	slog.Warn("This is a WARN message")
	slog.Error("This is an ERROR message")
	slog.Debug("This is a DEBUG message (only visible when DEBUG=true)")

	time.Sleep(100 * time.Millisecond)
	println()

	// Status and convenience functions
	println("Status Functions:")
	z_slog.Success("Operation completed successfully")
	z_slog.Failed("Operation failed")
	z_slog.Warning("This is a warning")
	z_slog.Debug("Debug information here")

	time.Sleep(100 * time.Millisecond)
	println()

	// System and server functions
	println("System & Server:")
	z_slog.Server("Server started on port 8080")
	z_slog.Start("Application starting up")
	z_slog.Stop("Application shutting down")
	z_slog.Network("Connected to network")
	z_slog.Config("Configuration loaded", "env", "production")

	time.Sleep(100 * time.Millisecond)
	println()

	// Authentication and security
	println("Authentication & Security:")
	z_slog.Auth("User authenticated successfully")
	z_slog.Token("JWT token generated")
	z_slog.User("User logged in", "username", "john.doe")
	z_slog.Security("Security check passed")
	z_slog.Critical("Critical security alert!")

	time.Sleep(100 * time.Millisecond)
	println()

	// Database operations
	println("Database Operations:")
	z_slog.Database("Connected to database")
	z_slog.Database("Query executed", "table", "videos", "rows", 42)
	z_slog.Database("Transaction committed")

	time.Sleep(100 * time.Millisecond)
	println()

	// API operations
	println("API Operations:")
	z_slog.API("GET /api/videos")
	z_slog.API("POST /api/videos/upload", "status", 201)
	z_slog.API("Request processed", "duration", "125ms")

	time.Sleep(100 * time.Millisecond)
	println()

	// Video and media operations
	println("Video & Media Operations:")
	z_slog.Video("Video uploaded successfully")
	z_slog.Video("Encoding started", "video_id", "video_123456")
	z_slog.Video("Playback ready", "duration", "02:34:56")
	z_slog.Upload("File uploaded", "size", "142MB")
	z_slog.Download("File downloaded", "size", "89MB")

	time.Sleep(100 * time.Millisecond)
	println()

	// Reports and analytics
	println("Reports & Analytics:")
	z_slog.Report("Daily report generated")
	z_slog.Report("Usage statistics", "users", 1523, "videos", 8921)

	time.Sleep(100 * time.Millisecond)
	println()

	// Examples with structured logging
	println("Structured Logging Examples:")
	slog.Info("User action",
		"action", "upload",
		"user_id", "user_789",
		"video_id", "video_456",
		"timestamp", time.Now().Format(time.RFC3339))

	slog.Error("Database connection failed",
		"error", "connection timeout",
		"host", "localhost:5432",
		"retry_count", 3)

	z_slog.Video("Processing complete",
		"video_id", "video_999",
		"duration_seconds", 145,
		"resolution", "1920x1080",
		"format", "mp4")
}
