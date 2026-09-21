package z_slog

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// UserLogManager manages per-user log files
type UserLogManager struct {
	mu        sync.RWMutex
	userFiles map[string]*os.File
}

var userLogManager = &UserLogManager{
	userFiles: make(map[string]*os.File),
}

// StartUserLogging opens or creates a log file for the specified user
func StartUserLogging(username string) error {
	FunctionEntry("StartUserLogging")
	Values(map[string]any{
		"username": username,
	})

	userLogManager.mu.Lock()
	defer userLogManager.mu.Unlock()

	// Create user logs directory
	userLogsDir := filepath.Join("z_slog", "logs", "users")
	if err := os.MkdirAll(userLogsDir, 0755); err != nil {
		ReturnValues(map[string]any{
			"error": err.Error(),
		})
		return fmt.Errorf("failed to create user logs directory: %w", err)
	}

	// Create filename with username and date: username-YYYY-MM-DD.ansi
	date := time.Now().Format("2006-01-02")
	filename := fmt.Sprintf("%s-%s.ansi", username, date)
	filePath := filepath.Join(userLogsDir, filename)

	// Open file in append mode
	file, err := os.OpenFile(filePath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		ReturnValues(map[string]any{
			"error": err.Error(),
		})
		return fmt.Errorf("failed to open user log file: %w", err)
	}

	// Close old file if exists
	if oldFile, exists := userLogManager.userFiles[username]; exists {
		oldFile.Close()
	}

	userLogManager.userFiles[username] = file

	// Write session start marker
	sessionStart := fmt.Sprintf("\n%s=== SESSION START ===%s\n", ColorGreen, ColorReset)
	file.WriteString(sessionStart)
	file.Sync() // Flush to ensure real-time output

	ReturnValues(map[string]any{
		"sessionStarted": true,
		"filePath":       filePath,
		"username":       username,
	})

	return nil
}

// LogUserAction logs a message to the user's log file
func LogUserAction(username, msg string) {
	if username == "" {
		return
	}

	userLogManager.mu.RLock()
	file, exists := userLogManager.userFiles[username]
	userLogManager.mu.RUnlock()

	if !exists {
		return
	}

	// Format timestamp with yellow milliseconds: t=02-30-45-123 PM
	now := time.Now()
	timestampBase := now.Format("03-04-05-")
	milliseconds := fmt.Sprintf("%03d", now.Nanosecond()/1e6)
	ampm := now.Format("PM")

	timestamp := fmt.Sprintf("t=%s%s%s%s %s", timestampBase, ColorYellow, milliseconds, ColorReset, ampm)
	logLine := fmt.Sprintf("%s %s\n", timestamp, msg)
	file.WriteString(logLine)
	file.Sync() // Flush to ensure real-time output
}

// StopUserLogging closes the log file for the specified user
func StopUserLogging(username string) {
	FunctionEntry("StopUserLogging")
	Values(map[string]any{
		"username": username,
	})

	userLogManager.mu.Lock()
	defer userLogManager.mu.Unlock()

	if file, exists := userLogManager.userFiles[username]; exists {
		// Write session end marker
		sessionEnd := fmt.Sprintf("%s=== SESSION END ===%s\n\n", ColorRed, ColorReset)
		file.WriteString(sessionEnd)
		file.Sync() // Flush before closing

		file.Close()
		delete(userLogManager.userFiles, username)

		ReturnValues(map[string]any{
			"sessionEnded": true,
			"username":     username,
		})
	} else {
		ReturnValues(map[string]any{
			"sessionEnded": false,
			"reason":       "no active session found for user",
			"username":     username,
		})
	}
}

// CloseAllUserLogs closes all open user log files
func CloseAllUserLogs() {
	userLogManager.mu.Lock()
	defer userLogManager.mu.Unlock()

	for username, file := range userLogManager.userFiles {
		sessionEnd := fmt.Sprintf("%s=== SESSION END ===%s\n\n", ColorRed, ColorReset)
		file.WriteString(sessionEnd)
		file.Sync() // Flush before closing
		file.Close()
		delete(userLogManager.userFiles, username)
	}
}
