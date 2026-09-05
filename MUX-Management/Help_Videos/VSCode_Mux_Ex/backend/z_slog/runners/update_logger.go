package main

// FROM A MAC TERMINAL
// RUN WITH: go run backend/z_slog/runners/update_logger.go
import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// RUN WITH: go run backend/z_slog/runners/update_logger.go

// FunctionInfo holds info about a single function
type FunctionInfo struct {
	Name             string
	FilePath         string
	LineNumber       int
	HasFunctionEntry bool
	HasReturnValues  bool
}

// FunctionCount holds the count data for a directory
type FunctionCount struct {
	Directory               string
	GoFunctions             []FunctionInfo
	TsFunctions             []FunctionInfo
	TotalFiles              int
	GoFiles                 int
	TsFiles                 int
	EntryCompliantCount     int
	EntryNonCompliantCount  int
	ReturnCompliantCount    int
	ReturnNonCompliantCount int
}

// Go function patterns
var goFuncRegex = regexp.MustCompile(`^func\s+(\([^)]*\)\s*)?(\w+)\s*\(`)

// Pattern to detect FunctionEntry logging
var functionEntryRegex = regexp.MustCompile(`z_slog\.FunctionEntry\s*\(|FunctionEntry\s*\(`)

// Pattern to detect ReturnValues logging
var returnValuesRegex = regexp.MustCompile(`z_slog\.ReturnValues\s*\(|ReturnValues\s*\(`)

// TypeScript/JavaScript function patterns
var tsFuncPatterns = []*regexp.Regexp{
	regexp.MustCompile(`^(?:export\s+)?function\s+(\w+)\s*\(`),                        // function declarations
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*\([^)]*\)\s*=>`),           // arrow functions
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*async\s*\([^)]*\)\s*=>`),   // async arrow functions
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*function\s*\(`),            // function expressions
	regexp.MustCompile(`^(?:export\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\(`),     // generator/async functions
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+):\s*React\.FC`),                   // React FC components
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*React\.memo`),              // React.memo components
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*React\.forwardRef`),        // React.forwardRef
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*\(\s*\{[^}]*\}\s*\)\s*=>`), // destructured params arrow
	regexp.MustCompile(`^(?:export\s+)?const\s+(\w+)\s*=\s*\(\s*props\s*\)\s*=>`),     // props arrow function
}

// Infrastructure functions that intentionally don't log (add to this list as needed)
var infrastructureFunctions = map[string]bool{
	// Response helpers
	"respondWithJSON":  true,
	"respondWithError": true,

	// Entry points
	"main": true,
	"init": true,

	// slog.Handler interface methods
	"Enabled":   true,
	"Handle":    true,
	"WithAttrs": true,
	"WithGroup": true,

	// z_slog core functions (they ARE the logging - can't log themselves)
	"Init":        true,
	"InitFromEnv": true,
	"Close":       true,

	// z_slog semantic logging functions (they ARE the logging)
	"Auth":          true,
	"Video":         true,
	"Token":         true,
	"User":          true,
	"Database":      true,
	"API":           true,
	"Upload":        true,
	"Download":      true,
	"Success":       true,
	"Failed":        true,
	"Warning":       true,
	"Debug":         true,
	"Server":        true,
	"Network":       true,
	"Security":      true,
	"Critical":      true,
	"Start":         true,
	"Stop":          true,
	"Config":        true,
	"Report":        true,
	"Values":        true,
	"ReturnValues":  true,
	"FunctionEntry": true,

	// z_slog user logging (thin wrappers)
	"LogUserAction":    true,
	"CloseAllUserLogs": true,

	// api/user_logging.go helpers (thin wrappers that forward to z_slog)
	"LogUserActionWithDetails": true,

	// Runner utility functions (tooling, not application code)
	"countFunctionsInDir":  true,
	"countFunctionsInRoot": true,
	"analyzeGoFile":        true,
	"analyzeTsFile":        true,
	"printResults":         true,
}

func main() {
	fmt.Println("\n" + strings.Repeat("=", 80))
	fmt.Println("                PROJECT FUNCTION COUNTER & COMPLIANCE CHECKER")
	fmt.Println(strings.Repeat("=", 80))

	// Get the project root
	execPath, err := os.Getwd()
	if err != nil {
		fmt.Println("Error getting current directory:", err)
		return
	}

	// Navigate to project root based on current location
	// If in backend/z_slog/runners, go up 3 levels
	if filepath.Base(execPath) == "runners" {
		execPath = filepath.Dir(filepath.Dir(filepath.Dir(execPath)))
	} else if filepath.Base(execPath) == "z_slog" {
		execPath = filepath.Dir(filepath.Dir(execPath))
	} else if filepath.Base(execPath) == "backend" {
		execPath = filepath.Dir(execPath)
	}

	projectRoot := execPath
	fmt.Printf("\nScanning project: %s\n", projectRoot)

	// Count functions in each area
	backendCount := countFunctionsInDir(filepath.Join(projectRoot, "backend"), true)
	frontendCount := countFunctionsInDir(filepath.Join(projectRoot, "frontend", "src"), false)
	rootCount := countFunctionsInRoot(projectRoot)

	// Print results
	printResults("BACKEND (Go)", backendCount, true)
	printResults("FRONTEND (TypeScript/React)", frontendCount, false)
	printResults("ROOT", rootCount, true)

	fmt.Println(strings.Repeat("=", 80) + "\n")
}

func countFunctionsInDir(dir string, isGo bool) FunctionCount {
	count := FunctionCount{Directory: dir}

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // Skip errors
		}

		// Skip node_modules, .git, and other common excludes
		if info.IsDir() {
			base := info.Name()
			if base == "node_modules" || base == ".git" || base == "vendor" || base == "dist" || base == "build" || base == "examples" {
				return filepath.SkipDir
			}
			return nil
		}

		ext := strings.ToLower(filepath.Ext(path))

		// Analyze Go files
		if ext == ".go" {
			count.GoFiles++
			count.TotalFiles++
			funcs := analyzeGoFile(path)
			count.GoFunctions = append(count.GoFunctions, funcs...)
		}

		// Analyze TypeScript/JavaScript files
		if ext == ".ts" || ext == ".tsx" || ext == ".js" || ext == ".jsx" {
			count.TsFiles++
			count.TotalFiles++
			funcs := analyzeTsFile(path)
			count.TsFunctions = append(count.TsFunctions, funcs...)
		}

		return nil
	})

	if err != nil {
		fmt.Printf("Error walking directory %s: %v\n", dir, err)
	}

	// Calculate compliance for Go functions
	for _, f := range count.GoFunctions {
		if f.HasFunctionEntry || infrastructureFunctions[f.Name] {
			count.EntryCompliantCount++
		} else {
			count.EntryNonCompliantCount++
		}
		if f.HasReturnValues || infrastructureFunctions[f.Name] {
			count.ReturnCompliantCount++
		} else {
			count.ReturnNonCompliantCount++
		}
	}

	return count
}

func countFunctionsInRoot(projectRoot string) FunctionCount {
	count := FunctionCount{Directory: projectRoot + " (root only)"}

	entries, err := os.ReadDir(projectRoot)
	if err != nil {
		return count
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		ext := strings.ToLower(filepath.Ext(entry.Name()))
		path := filepath.Join(projectRoot, entry.Name())

		if ext == ".go" {
			count.GoFiles++
			count.TotalFiles++
			funcs := analyzeGoFile(path)
			count.GoFunctions = append(count.GoFunctions, funcs...)
		}

		if ext == ".ts" || ext == ".tsx" || ext == ".js" || ext == ".jsx" {
			count.TsFiles++
			count.TotalFiles++
			funcs := analyzeTsFile(path)
			count.TsFunctions = append(count.TsFunctions, funcs...)
		}
	}

	// Calculate compliance for Go functions
	for _, f := range count.GoFunctions {
		if f.HasFunctionEntry || infrastructureFunctions[f.Name] {
			count.EntryCompliantCount++
		} else {
			count.EntryNonCompliantCount++
		}
		if f.HasReturnValues || infrastructureFunctions[f.Name] {
			count.ReturnCompliantCount++
		} else {
			count.ReturnNonCompliantCount++
		}
	}

	return count
}

func analyzeGoFile(path string) []FunctionInfo {
	file, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer file.Close()

	// Read the entire file to analyze function bodies
	var lines []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}

	var functions []FunctionInfo

	for i := 0; i < len(lines); i++ {
		trimmedLine := strings.TrimSpace(lines[i])

		// Check for function declaration
		if matches := goFuncRegex.FindStringSubmatch(trimmedLine); len(matches) > 2 {
			funcName := matches[2]
			funcInfo := FunctionInfo{
				Name:             funcName,
				FilePath:         path,
				LineNumber:       i + 1,
				HasFunctionEntry: false,
				HasReturnValues:  false,
			}

			// Find the opening brace and scan the function body
			braceDepth := 0
			foundOpenBrace := false

			for j := i; j < len(lines); j++ {
				line := lines[j]

				// Count braces
				for _, ch := range line {
					if ch == '{' {
						braceDepth++
						foundOpenBrace = true
					} else if ch == '}' {
						braceDepth--
					}
				}

				// Check for FunctionEntry in function body
				if functionEntryRegex.MatchString(line) {
					funcInfo.HasFunctionEntry = true
				}

				// Check for ReturnValues in function body
				if returnValuesRegex.MatchString(line) {
					funcInfo.HasReturnValues = true
				}

				// Function ended
				if foundOpenBrace && braceDepth == 0 {
					break
				}
			}

			functions = append(functions, funcInfo)
		}
	}

	return functions
}

func analyzeTsFile(path string) []FunctionInfo {
	file, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer file.Close()

	var functions []FunctionInfo
	scanner := bufio.NewScanner(file)
	lineNumber := 0
	seenFunctions := make(map[string]bool)

	for scanner.Scan() {
		lineNumber++
		line := scanner.Text()
		trimmedLine := strings.TrimSpace(line)

		// Skip comments
		if strings.HasPrefix(trimmedLine, "//") || strings.HasPrefix(trimmedLine, "*") || strings.HasPrefix(trimmedLine, "/*") {
			continue
		}

		for _, pattern := range tsFuncPatterns {
			if matches := pattern.FindStringSubmatch(trimmedLine); len(matches) > 1 {
				funcName := matches[1]
				// Avoid counting the same function twice
				if !seenFunctions[funcName] && funcName != "" && funcName != "if" && funcName != "for" && funcName != "while" && funcName != "switch" {
					seenFunctions[funcName] = true
					functions = append(functions, FunctionInfo{
						Name:             funcName,
						FilePath:         path,
						LineNumber:       lineNumber,
						HasFunctionEntry: false, // Frontend doesn't use z_slog
						HasReturnValues:  false,
					})
				}
				break
			}
		}
	}

	return functions
}

func printResults(title string, count FunctionCount, checkCompliance bool) {
	fmt.Println("\n" + strings.Repeat("-", 80))
	fmt.Printf("  %s\n", title)
	fmt.Println(strings.Repeat("-", 80))
	fmt.Printf("  Directory:      %s\n", count.Directory)
	fmt.Printf("  Files Scanned:  %d\n", count.TotalFiles)

	totalFuncs := len(count.GoFunctions) + len(count.TsFunctions)

	if count.GoFiles > 0 {
		fmt.Printf("  Go Files:       %d\n", count.GoFiles)
		fmt.Printf("  Go Functions:   %d\n", len(count.GoFunctions))
	}

	if count.TsFiles > 0 {
		fmt.Printf("  TS/JS Files:    %d\n", count.TsFiles)
		fmt.Printf("  TS/JS Functions:%d\n", len(count.TsFunctions))
	}

	fmt.Printf("  TOTAL:          %d functions\n", totalFuncs)

	// Show compliance box for frontend (TS/JS functions don't use z_slog)
	if !checkCompliance && len(count.TsFunctions) > 0 {
		tsFuncCount := len(count.TsFunctions)
		fmt.Println()
		fmt.Printf("  ┌─ LOGGING COMPLIANCE ─────────────────────────────────────────────────────┐\n")
		fmt.Printf("  │  FunctionEntry:  WITH:   0 ✅   WITHOUT: %3d ❌  (frontend n/a)          │\n", tsFuncCount)
		fmt.Printf("  │  ReturnValues:   WITH:   0 ✅   WITHOUT: %3d ❌  (frontend n/a)          │\n", tsFuncCount)
		fmt.Printf("  └──────────────────────────────────────────────────────────────────────────┘\n")
	}

	// Check compliance for Go files (backend/root)
	if checkCompliance {
		fmt.Println()
		fmt.Printf("  ┌─ LOGGING COMPLIANCE ─────────────────────────────────────────────────────┐\n")
		fmt.Printf("  │  FunctionEntry:  WITH: %3d ✅   WITHOUT: %3d ❌                          │\n", count.EntryCompliantCount, count.EntryNonCompliantCount)
		fmt.Printf("  │  ReturnValues:   WITH: %3d ✅   WITHOUT: %3d ❌                          │\n", count.ReturnCompliantCount, count.ReturnNonCompliantCount)
		fmt.Printf("  └──────────────────────────────────────────────────────────────────────────┘\n")

		// Only show detailed compliance info if there are Go functions
		if len(count.GoFunctions) > 0 {
			// List functions missing FunctionEntry
			var missingEntry []FunctionInfo
			for _, f := range count.GoFunctions {
				if !f.HasFunctionEntry && !infrastructureFunctions[f.Name] {
					missingEntry = append(missingEntry, f)
				}
			}

			if len(missingEntry) > 0 {
				fmt.Println()
				fmt.Println("  ⚠️  FUNCTIONS MISSING z_slog.FunctionEntry:")
				fmt.Println("  " + strings.Repeat("─", 76))
				for _, f := range missingEntry {
					relPath := f.FilePath
					if idx := strings.Index(relPath, "backend/"); idx >= 0 {
						relPath = relPath[idx:]
					}
					fmt.Printf("  ❌ %-30s  %s:%d\n", f.Name, relPath, f.LineNumber)
				}
			} else {
				fmt.Println()
				fmt.Println("  ✅ ALL FUNCTIONS HAVE FunctionEntry!")
			}

			// List functions missing ReturnValues
			var missingReturn []FunctionInfo
			for _, f := range count.GoFunctions {
				if !f.HasReturnValues && !infrastructureFunctions[f.Name] {
					missingReturn = append(missingReturn, f)
				}
			}

			if len(missingReturn) > 0 {
				fmt.Println()
				fmt.Println("  ⚠️  FUNCTIONS MISSING z_slog.ReturnValues:")
				fmt.Println("  " + strings.Repeat("─", 76))
				for _, f := range missingReturn {
					relPath := f.FilePath
					if idx := strings.Index(relPath, "backend/"); idx >= 0 {
						relPath = relPath[idx:]
					}
					fmt.Printf("  ❌ %-30s  %s:%d\n", f.Name, relPath, f.LineNumber)
				}
			} else {
				fmt.Println()
				fmt.Println("  ✅ ALL FUNCTIONS HAVE ReturnValues!")
			}

			// List infrastructure functions (intentionally not logged)
			var infraFuncs []FunctionInfo
			for _, f := range count.GoFunctions {
				if infrastructureFunctions[f.Name] {
					infraFuncs = append(infraFuncs, f)
				}
			}

			if len(infraFuncs) > 0 {
				fmt.Println()
				fmt.Println("  ℹ️  INFRASTRUCTURE FUNCTIONS (intentionally not logged):")
				fmt.Println("  " + strings.Repeat("─", 76))
				for _, f := range infraFuncs {
					relPath := f.FilePath
					if idx := strings.Index(relPath, "backend/"); idx >= 0 {
						relPath = relPath[idx:]
					}
					fmt.Printf("  ⚙️  %-30s  %s:%d\n", f.Name, relPath, f.LineNumber)
				}
			}
		}
	}
}
