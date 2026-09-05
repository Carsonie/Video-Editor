package api

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/yourname/mux-example/internal/db"
	"github.com/yourname/mux-example/z_slog"
)

// LoggingMiddleware logs HTTP requests
func LoggingMiddleware(next http.Handler) http.Handler {
	z_slog.FunctionEntry("LoggingMiddleware")
	z_slog.ReturnValues(map[string]any{"handler": "http.HandlerFunc"})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		// Create a response wrapper to capture status code
		wrapper := &responseWrapper{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		// Call the next handler
		next.ServeHTTP(wrapper, r)

		// Log the request
		duration := time.Since(start)
		log.Printf(
			"%s %s %d %s",
			r.Method,
			r.RequestURI,
			wrapper.statusCode,
			duration,
		)
	})
}

// CORSMiddleware handles CORS headers
func CORSMiddleware(frontendURL string) func(http.Handler) http.Handler {
	z_slog.FunctionEntry("CORSMiddleware")
	z_slog.Values(map[string]any{"frontendURL": frontendURL})
	z_slog.ReturnValues(map[string]any{"handler": "middleware func"})
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Set CORS headers
			w.Header().Set("Access-Control-Allow-Origin", frontendURL)
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
			w.Header().Set("Access-Control-Allow-Credentials", "true")

			// Handle preflight requests
			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusOK)
				return
			}

			// Call the next handler
			next.ServeHTTP(w, r)
		})
	}
}

// ErrorHandlingMiddleware provides centralized error handling
func ErrorHandlingMiddleware(next http.Handler) http.Handler {
	z_slog.FunctionEntry("ErrorHandlingMiddleware")
	z_slog.ReturnValues(map[string]any{"handler": "http.HandlerFunc"})
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("Panic recovered: %v", err)
				http.Error(w, "Internal server error", http.StatusInternalServerError)
			}
		}()

		next.ServeHTTP(w, r)
	})
}

// responseWrapper wraps http.ResponseWriter to capture status code
type responseWrapper struct {
	http.ResponseWriter
	statusCode int
}

// WriteHeader captures the status code
func (rw *responseWrapper) WriteHeader(code int) {
	z_slog.FunctionEntry("WriteHeader")
	z_slog.Values(map[string]any{
		"code": code,
	})
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
	z_slog.ReturnValues(map[string]any{
		"statusCode": code,
	})
}

// contextKey is a custom type for context keys
type contextKey string

const (
	userContextKey contextKey = "user"
)

// AuthMiddleware validates session tokens and adds user to context
func AuthMiddleware(database *db.Database) func(http.Handler) http.Handler {
	z_slog.FunctionEntry("AuthMiddleware")
	z_slog.ReturnValues(map[string]any{"handler": "middleware func"})
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Extract token from Authorization header
			token := extractTokenFromRequest(r)
			if token == "" {
				http.Error(w, "Unauthorized: No token provided", http.StatusUnauthorized)
				return
			}

			// Get session and user from database
			_, user, err := database.GetSessionByToken(token)
			if err != nil {
				log.Printf("Invalid session token: %v", err)
				http.Error(w, "Unauthorized: Invalid or expired token", http.StatusUnauthorized)
				return
			}

			// Add user to request context
			ctx := context.WithValue(r.Context(), userContextKey, user)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// GetUserFromContext retrieves the user from the request context
func GetUserFromContext(r *http.Request) *db.User {
	z_slog.FunctionEntry("GetUserFromContext")
	z_slog.Values(map[string]any{})
	user, ok := r.Context().Value(userContextKey).(*db.User)
	if !ok {
		z_slog.ReturnValues(map[string]any{
			"user": nil,
		})
		return nil
	}
	z_slog.ReturnValues(map[string]any{
		"user": user,
	})
	return user
}

// extractTokenFromRequest extracts the token from Authorization header
func extractTokenFromRequest(r *http.Request) string {
	z_slog.FunctionEntry("extractTokenFromRequest")
	z_slog.Values(map[string]any{})
	bearerToken := r.Header.Get("Authorization")
	if bearerToken == "" {
		z_slog.ReturnValues(map[string]any{
			"token": "",
		})
		return ""
	}

	// Format: "Bearer <token>"
	if len(bearerToken) > 7 && bearerToken[:7] == "Bearer " {
		token := bearerToken[7:]
		z_slog.ReturnValues(map[string]any{
			"token": token,
		})
		return token
	}

	z_slog.ReturnValues(map[string]any{
		"token": "",
	})
	return ""
}
