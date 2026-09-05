package z_slog

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"time"
)

var (
	// DEBUG controls whether debug logging is enabled
	DEBUG bool
	// logFile holds the current log file handle
	logFile *os.File
)

// colorHandler is a custom slog handler that preserves ANSI color codes
type colorHandler struct {
	writer io.Writer
	level  slog.Level
}

// Enabled implements slog.Handler
func (h *colorHandler) Enabled(_ context.Context, level slog.Level) bool {
	return level >= h.level
}

// Handle implements slog.Handler
func (h *colorHandler) Handle(_ context.Context, r slog.Record) error {
	// Format: time=TIMESTAMP level=LEVEL msg=MESSAGE [key=value...]
	buf := make([]byte, 0, 256)

	// Add timestamp (HH-MM-SS-MS PM format with yellow milliseconds)
	buf = append(buf, "t="...)
	buf = r.Time.AppendFormat(buf, "03-04-05-")
	buf = append(buf, ColorYellow...)
	buf = append(buf, fmt.Sprintf("%03d", r.Time.Nanosecond()/1e6)...)
	buf = append(buf, ColorReset...)
	buf = append(buf, ' ')
	buf = r.Time.AppendFormat(buf, "PM")
	buf = append(buf, ' ')

	// Add level with color (no quotes)
	buf = append(buf, "level="...)
	levelStr := ""
	switch r.Level {
	case slog.LevelDebug:
		levelStr = ColorCyan + IconDebug + " DEBUG" + ColorReset
	case slog.LevelInfo:
		levelStr = ColorBlue + IconInfo + "  INFO " + ColorReset
	case slog.LevelWarn:
		levelStr = ColorYellow + IconWarning + "  WARN " + ColorReset
	case slog.LevelError:
		levelStr = ColorRed + IconError + " ERROR" + ColorReset
	default:
		levelStr = r.Level.String()
	}
	buf = append(buf, levelStr...)
	buf = append(buf, ' ')

	// Add message (no quotes, preserve ANSI codes)
	buf = append(buf, "msg="...)
	buf = append(buf, r.Message...)

	// Add attributes
	r.Attrs(func(a slog.Attr) bool {
		buf = append(buf, ' ')
		buf = append(buf, a.Key...)
		buf = append(buf, '=')
		buf = append(buf, fmt.Sprint(a.Value.Any())...)
		return true
	})

	buf = append(buf, '\n')
	_, err := h.writer.Write(buf)

	// Flush to ensure real-time output to file
	if logFile != nil {
		logFile.Sync()
	}

	return err
}

// WithAttrs implements slog.Handler
func (h *colorHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return h
}

// WithGroup implements slog.Handler
func (h *colorHandler) WithGroup(name string) slog.Handler {
	return h
}

// Init initializes the slog logger with emoji support and file logging
func Init(debug bool) {
	DEBUG = debug

	// Close existing log file if open
	if logFile != nil {
		logFile.Close()
	}

	// Create logs directory if it doesn't exist
	logsDir := "z_slog/logs"
	if err := os.MkdirAll(logsDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create logs directory: %v\n", err)
	}

	// Create timestamped log file: output-YYYY-MM-DD-HH-MM.ansi
	timestamp := time.Now().Format("2006-01-02-15-04")
	logFileName := fmt.Sprintf("output-%s.ansi", timestamp)
	logFilePath := filepath.Join(logsDir, logFileName)

	var err error
	logFile, err = os.Create(logFilePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to create log file: %v\n", err)
		logFile = nil
	}

	level := slog.LevelInfo
	if debug {
		level = slog.LevelDebug
	}

	// Create multi-writer to write to both stdout and file
	var writer io.Writer
	if logFile != nil {
		writer = io.MultiWriter(os.Stdout, logFile)
		fmt.Printf("Logging to: %s\n", logFilePath)
	} else {
		writer = os.Stdout
	}

	// Use custom color handler instead of TextHandler
	handler := &colorHandler{
		writer: writer,
		level:  level,
	}

	logger := slog.New(handler)
	slog.SetDefault(logger)
}

// InitFromEnv initializes logger from environment variable DEBUG_MODE
func InitFromEnv() {
	debugMode := strings.ToLower(os.Getenv("DEBUG_MODE")) == "true"
	Init(debugMode)
}

// Close closes the log file if it's open
func Close() {
	if logFile != nil {
		logFile.Close()
		logFile = nil
	}
}

// Convenience logging functions with emojis

// Auth logs authentication-related messages in green
func Auth(msg string, args ...any) {
	slog.Info(ColorGreen + IconAuth + " " + msg + ColorReset, args...)
}

// Video logs video-related messages in magenta
func Video(msg string, args ...any) {
	slog.Info(ColorMagenta + IconVideo + " " + msg + ColorReset, args...)
}

// Token logs token-related messages in cyan
func Token(msg string, args ...any) {
	if DEBUG {
		slog.Debug(ColorCyan + IconToken + " " + msg + ColorReset, args...)
	}
}

// User logs user-related messages in yellow
func User(msg string, args ...any) {
	slog.Info(ColorYellow + IconUser + " " + msg + ColorReset, args...)
}

// Database logs database-related messages in blue
func Database(msg string, args ...any) {
	if DEBUG {
		slog.Debug(ColorBlue + IconDatabase + " " + msg + ColorReset, args...)
	}
}

// API logs API-related messages in cyan
func API(msg string, args ...any) {
	slog.Info(ColorCyan + IconAPI + " " + msg + ColorReset, args...)
}

// Upload logs upload-related messages in green
func Upload(msg string, args ...any) {
	slog.Info(ColorGreen + IconUpload + " " + msg + ColorReset, args...)
}

// Download logs download-related messages in green
func Download(msg string, args ...any) {
	slog.Info(ColorGreen + IconDownload + " " + msg + ColorReset, args...)
}

// Success logs success messages in green
func Success(msg string, args ...any) {
	slog.Info(ColorGreen + IconSuccess + " " + msg + ColorReset, args...)
}

// Failed logs failure messages as errors in red
func Failed(msg string, args ...any) {
	slog.Error(ColorRed + IconError + " " + msg + ColorReset, args...)
}

// Warning logs warning messages in yellow
func Warning(msg string, args ...any) {
	slog.Warn(ColorYellow + IconWarning + " " + msg + ColorReset, args...)
}

// Debug logs debug messages (only if DEBUG is enabled) in cyan
func Debug(msg string, args ...any) {
	if DEBUG {
		slog.Debug(ColorCyan + IconDebug + " " + msg + ColorReset, args...)
	}
}

// Server logs server-related messages in blue
func Server(msg string, args ...any) {
	slog.Info(ColorBlue + IconServer + " " + msg + ColorReset, args...)
}

// Network logs network-related messages in cyan
func Network(msg string, args ...any) {
	slog.Info(ColorCyan + IconNetwork + " " + msg + ColorReset, args...)
}

// Security logs security-related messages in magenta
func Security(msg string, args ...any) {
	slog.Info(ColorMagenta + IconShield + " " + msg + ColorReset, args...)
}

// Critical logs critical error messages in red
func Critical(msg string, args ...any) {
	slog.Error(ColorRed + IconCritical + " " + msg + ColorReset, args...)
}

// Start logs startup messages in green
func Start(msg string, args ...any) {
	slog.Info(ColorGreen + IconStart + " " + msg + ColorReset, args...)
}

// Stop logs shutdown messages in red
func Stop(msg string, args ...any) {
	slog.Info(ColorRed + IconStop + " " + msg + ColorReset, args...)
}

// Config logs configuration messages in yellow
func Config(msg string, args ...any) {
	if DEBUG {
		slog.Debug(ColorYellow + IconConfig + " " + msg + ColorReset, args...)
	}
}

// Report logs report-related messages in blue
func Report(msg string, args ...any) {
	slog.Info(ColorBlue + IconReport + " " + msg + ColorReset, args...)
}

// FunctionEntry logs function entry with cyan color
func FunctionEntry(functionName string) {
	slog.Info(ColorCyan + IconCode + " Function " + IconArrowR + " " + functionName + ColorReset)
}

// Values logs function parameter values in magenta with cyan parameter names and bright magenta values
func Values(params map[string]any) {
	if len(params) == 0 {
		return
	}

	var parts []string
	for key, value := range params {
		var valueStr string

		// Handle different types
		switch v := value.(type) {
		case string:
			valueStr = fmt.Sprintf("\"%s\"", v)
		case nil:
			valueStr = "null"
		case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, float32, float64, bool:
			// Simple types - no JSON formatting needed
			valueStr = fmt.Sprintf("%v", v)
		default:
			// Try to marshal as pretty JSON for complex objects
			jsonBytes, err := json.MarshalIndent(v, "", "  ")
			if err != nil {
				valueStr = fmt.Sprintf("%v", v)
			} else {
				valueStr = string(jsonBytes)
			}
		}

		// Format: cyan parameter name + bright magenta value
		parts = append(parts, fmt.Sprintf("%s%s%s: %s%s%s",
			ColorCyan, key, ColorReset,
			ColorBrightMagenta, valueStr, ColorReset))
	}

	// Join all parameters with newlines if any contain multiline JSON
	paramsStr := strings.Join(parts, "\n")

	// Log with magenta VALUES label and icon
	msg := fmt.Sprintf("%s%s VALUES%s\n%s", ColorMagenta, IconValues, ColorReset, paramsStr)
	slog.Info(msg)
}

// ReturnValues logs function return values with purple (256-color) labels and bright green values
func ReturnValues(returns map[string]any) {
	if len(returns) == 0 {
		return
	}

	var parts []string
	for key, value := range returns {
		var valueStr string

		// Handle different types
		switch v := value.(type) {
		case string:
			valueStr = fmt.Sprintf("\"%s\"", v)
		case nil:
			valueStr = "null"
		case int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64, float32, float64, bool:
			// Simple types - no JSON formatting needed
			valueStr = fmt.Sprintf("%v", v)
		default:
			// Try to marshal as pretty JSON for complex objects
			jsonBytes, err := json.MarshalIndent(v, "", "  ")
			if err != nil {
				valueStr = fmt.Sprintf("%v", v)
			} else {
				valueStr = string(jsonBytes)
			}
		}

		// Format: purple parameter name + bright green value
		parts = append(parts, fmt.Sprintf("%s%s%s: %s%s%s",
			ColorPurple, key, ColorReset,
			ColorBrightGreen, valueStr, ColorReset))
	}

	// Join all return values
	returnsStr := strings.Join(parts, "\n")

	// Log with green RETURNED label and icon
	msg := fmt.Sprintf("%s%s RETURNED%s\n%s", ColorGreen, IconReturn, ColorReset, returnsStr)
	slog.Info(msg)
}
