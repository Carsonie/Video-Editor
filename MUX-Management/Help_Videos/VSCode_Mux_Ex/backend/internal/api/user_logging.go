package api

import (
	"fmt"
	"net/http"

	"github.com/yourname/mux-example/z_slog"
)

// LogUserAction logs an action to the user's specific log file if user is authenticated
func LogUserAction(r *http.Request, functionName string) {
	user := GetUserFromContext(r)
	if user == nil {
		return
	}
	msg := fmt.Sprintf("%s%s Function %s %s%s", z_slog.ColorCyan, z_slog.IconCode, z_slog.IconArrowR, functionName, z_slog.ColorReset)
	z_slog.LogUserAction(user.Name, msg)
}

// LogUserActionWithDetails logs an action with additional details to the user's log file
func LogUserActionWithDetails(r *http.Request, functionName string, details string) {
	user := GetUserFromContext(r)
	if user == nil {
		return
	}
	msg := fmt.Sprintf("%s%s Function %s %s | %s%s", z_slog.ColorCyan, z_slog.IconCode, z_slog.IconArrowR, functionName, details, z_slog.ColorReset)
	z_slog.LogUserAction(user.Name, msg)
}
