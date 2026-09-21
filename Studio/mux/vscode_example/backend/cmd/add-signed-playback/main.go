package main

import (
	"database/sql"
	"fmt"
	"log"
	"os"

	"github.com/joho/godotenv"
	_ "github.com/mattn/go-sqlite3"
	"github.com/yourname/mux-example/internal/mux"
)

func main() {
	// Load environment variables
	if err := godotenv.Load(".env"); err != nil {
		log.Printf("Warning: .env file not found: %v", err)
	}

	// Get Mux credentials
	tokenID := os.Getenv("MUX_TOKEN_ID")
	tokenSecret := os.Getenv("MUX_TOKEN_SECRET")
	dbPath := os.Getenv("DATABASE_PATH")
	if dbPath == "" {
		dbPath = "./videos.db"
	}

	// Initialize Mux client
	muxClient, err := mux.New(tokenID, tokenSecret)
	if err != nil {
		log.Fatalf("Failed to initialize Mux client: %v", err)
	}

	// Connect to database
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		log.Fatalf("Failed to open database: %v", err)
	}
	defer db.Close()

	// Get the John Deere video
	videoID := "video_1769108394_64666118"
	var assetID, playbackID, signedPlaybackID string
	err = db.QueryRow(`
		SELECT mux_asset_id, mux_playback_id, mux_signed_playback_id
		FROM videos
		WHERE id = ?
	`, videoID).Scan(&assetID, &playbackID, &signedPlaybackID)
	if err != nil {
		log.Fatalf("Failed to get video: %v", err)
	}

	log.Printf("Video: %s", videoID)
	log.Printf("Asset ID: %s", assetID)
	log.Printf("Current public playback ID: %s", playbackID)
	log.Printf("Current signed playback ID: %s", signedPlaybackID)

	// Create signed playback ID if it doesn't exist
	if signedPlaybackID == "" {
		log.Println("Creating new signed playback ID...")
		newSignedID, err := muxClient.CreateSignedPlaybackID(assetID)
		if err != nil {
			log.Fatalf("Failed to create signed playback ID: %v", err)
		}

		// Update database
		_, err = db.Exec(`
			UPDATE videos
			SET mux_signed_playback_id = ?
			WHERE id = ?
		`, newSignedID, videoID)
		if err != nil {
			log.Fatalf("Failed to update database: %v", err)
		}

		log.Printf("Successfully created and saved signed playback ID: %s", newSignedID)
	} else {
		log.Println("Signed playback ID already exists")
	}

	fmt.Println("\nDone!")
}
