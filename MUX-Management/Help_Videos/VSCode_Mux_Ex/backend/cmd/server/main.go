package main

import (
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/gorilla/mux"
	"github.com/joho/godotenv"
	"github.com/yourname/mux-example/internal/api"
	"github.com/yourname/mux-example/internal/auth"
	"github.com/yourname/mux-example/internal/db"
	muxclient "github.com/yourname/mux-example/internal/mux"
	"github.com/yourname/mux-example/z_slog"
)

func main() {
	// Initialize z_slog logger
	z_slog.InitFromEnv()
	defer z_slog.Close()
	defer z_slog.CloseAllUserLogs()

	z_slog.FunctionEntry("main")

	// Load environment variables from .env file
	if err := godotenv.Load(); err != nil {
		log.Println("Warning: .env file not found, using system environment variables")
	}

	// Get configuration from environment
	serverPort := getEnv("SERVER_PORT", "8080")
	databasePath := getEnv("DATABASE_PATH", "./videos.db")
	frontendURL := getEnv("FRONTEND_URL", "http://localhost:3000")
	muxTokenID := getEnv("MUX_TOKEN_ID", "")
	muxTokenSecret := getEnv("MUX_TOKEN_SECRET", "")
	muxSigningKeyID := getEnv("MUX_SIGNING_KEY_ID", "")
	muxSigningPrivateKey := getEnv("MUX_SIGNING_PRIVATE_KEY", "")
	jwtPrivateKey := getEnv("JWT_PRIVATE_KEY", "")
	jwtPublicKey := getEnv("JWT_PUBLIC_KEY", "")

	// Validate required environment variables
	if muxTokenID == "" || muxTokenSecret == "" {
		log.Fatal("Error: MUX_TOKEN_ID and MUX_TOKEN_SECRET must be set")
	}

	if muxSigningKeyID == "" || muxSigningPrivateKey == "" {
		log.Fatal("Error: MUX_SIGNING_KEY_ID and MUX_SIGNING_PRIVATE_KEY must be set")
	}

	if jwtPrivateKey == "" || jwtPublicKey == "" {
		log.Fatal("Error: JWT_PRIVATE_KEY and JWT_PUBLIC_KEY must be set")
	}

	// Initialize database
	log.Println("Initializing database...")
	database, err := db.New(databasePath)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	// Run database migrations
	if err := database.Migrate(); err != nil {
		log.Fatalf("Failed to run database migrations: %v", err)
	}
	log.Println("Database initialized successfully")

	// Initialize Mux client
	log.Println("Initializing Mux client...")
	muxClient, err := muxclient.New(muxTokenID, muxTokenSecret)
	if err != nil {
		log.Fatalf("Failed to initialize Mux client: %v", err)
	}
	log.Println("Mux client initialized successfully")

	// Initialize JWT token manager for Mux playback
	log.Println("Initializing JWT token manager...")
	tokenManager, err := auth.New(muxSigningPrivateKey, muxSigningKeyID)
	if err != nil {
		log.Fatalf("Failed to initialize JWT token manager: %v", err)
	}
	log.Println("JWT token manager initialized successfully")

	// Initialize API handler
	apiHandler := api.NewHandler(database, muxClient, tokenManager)

	// Set up HTTP router
	router := mux.NewRouter()

	// Apply middleware
	router.Use(api.LoggingMiddleware)
	router.Use(api.CORSMiddleware(frontendURL))
	router.Use(api.ErrorHandlingMiddleware)

	// Register API routes
	apiRouter := router.PathPrefix("/api").Subrouter()

	// Auth routes (public)
	apiRouter.HandleFunc("/auth/login", apiHandler.Login).Methods("POST", "OPTIONS")

	// Protected routes (require authentication)
	protectedRouter := apiRouter.PathPrefix("").Subrouter()
	protectedRouter.Use(api.AuthMiddleware(database))

	// Video routes (protected)
	protectedRouter.HandleFunc("/videos", apiHandler.ListVideos).Methods("GET", "OPTIONS")
	protectedRouter.HandleFunc("/videos", apiHandler.CreateVideo).Methods("POST", "OPTIONS")
	protectedRouter.HandleFunc("/videos/{id}", apiHandler.GetVideo).Methods("GET", "OPTIONS")
	protectedRouter.HandleFunc("/videos/{id}/playback-token", apiHandler.CreatePlaybackToken).Methods("POST", "OPTIONS")
	protectedRouter.HandleFunc("/videos/{id}/status", apiHandler.GetVideoStatus).Methods("GET", "OPTIONS")

	// Upload routes (protected)
	protectedRouter.HandleFunc("/uploads/create", apiHandler.CreateDirectUpload).Methods("POST", "OPTIONS")
	protectedRouter.HandleFunc("/uploads/{id}/complete", apiHandler.CompleteDirectUpload).Methods("POST", "OPTIONS")

	// Auth logout route (protected)
	protectedRouter.HandleFunc("/auth/logout", apiHandler.Logout).Methods("POST", "OPTIONS")

	// Register webhook routes
	webhookRouter := router.PathPrefix("/webhooks").Subrouter()
	webhookRouter.HandleFunc("/mux", apiHandler.HandleMuxWebhook).Methods("POST")

	// Health check endpoint
	router.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	}).Methods("GET")

	// Start server
	addr := fmt.Sprintf(":%s", serverPort)
	log.Printf("Server starting on http://localhost%s", addr)
	log.Printf("Frontend URL: %s", frontendURL)
	log.Printf("Database: %s", databasePath)

	if err := http.ListenAndServe(addr, router); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}

// getEnv retrieves an environment variable or returns a default value
func getEnv(key, defaultValue string) string {
	z_slog.FunctionEntry("getEnv")
	z_slog.Values(map[string]any{"key": key, "defaultValue": defaultValue})

	if value := os.Getenv(key); value != "" {
		z_slog.ReturnValues(map[string]any{"value": value, "source": "environment"})
		return value
	}
	z_slog.ReturnValues(map[string]any{"value": defaultValue, "source": "default"})
	return defaultValue
}
