.PHONY: kill-ports kill-frontend kill-backend launch-logger launch-backend launch-frontend tail-logs open-logs help

# Kill both frontend (3000) and backend (8080) ports
kill-ports:
	@echo "Killing processes on ports 3000 and 8080..."
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "No process on port 3000"
	@lsof -ti:8080 | xargs kill -9 2>/dev/null || echo "No process on port 8080"
	@echo "Done!"

# Kill only frontend port (3000)
kill-frontend:
	@echo "Killing process on port 3000..."
	@lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "No process on port 3000"
	@echo "Done!"

# Kill only backend port (8080)
kill-backend:
	@echo "Killing process on port 8080..."
	@lsof -ti:8080 | xargs kill -9 2>/dev/null || echo "No process on port 8080"
	@echo "Done!"

# Launch full stack with logger - kills existing, starts servers, opens Terminal with live logs
launch-logger: kill-ports
	@echo "🚀 Starting frontend in background..."
	@cd frontend && npm run dev > /dev/null 2>&1 &
	@echo "🖥️  Starting Go backend in background..."
	@cd "$(CURDIR)/backend" && go run ./cmd/server > /dev/null 2>&1 &
	@echo "⏳ Waiting for log file to be created..."
	@sleep 3
	@LATEST=$$(ls -t "$(CURDIR)/backend/z_slog/logs"/output-*.ansi 2>/dev/null | head -1); \
	if [ -n "$$LATEST" ]; then \
		echo "📺 Opening Terminal window (140x65) with live logs..."; \
		osascript \
			-e "tell application \"Terminal\"" \
			-e "do script \"clear && echo '📋 Live Logger Output - z_slog' && echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' && tail -f \\\"$$LATEST\\\"\"" \
			-e "set currentTab to selected tab of front window" \
			-e "set number of columns of currentTab to 140" \
			-e "set number of rows of currentTab to 65" \
			-e "set current settings of currentTab to settings set \"Pro\"" \
			-e "activate" \
			-e "end tell"; \
		echo "✅ Opened: $$LATEST"; \
		echo "✅ Frontend: http://localhost:3000"; \
		echo "✅ Backend:  http://localhost:8080"; \
		echo "🌐 Opening browser..."; \
		open http://localhost:3000; \
	else \
		echo "❌ No log file created. Check backend for errors."; \
	fi

# Launch only backend with colored output
launch-backend: kill-backend
	@echo "🖥️  Starting Go backend with colored logger..."
	@cd backend && go run ./cmd/server

# Launch only frontend
launch-frontend: kill-frontend
	@echo "🌐 Starting frontend..."
	@cd frontend && npm run dev

# Tail the latest log file with colors
tail-logs:
	@echo "📋 Tailing latest log file..."
	@LATEST=$$(ls -t backend/z_slog/logs/output-*.ansi 2>/dev/null | head -1); \
	if [ -n "$$LATEST" ]; then \
		echo "Reading: $$LATEST"; \
		tail -f "$$LATEST"; \
	else \
		echo "No log files found in backend/z_slog/logs/"; \
	fi

# Open a new dark Terminal window (140x65) with live log output
open-logs:
	@echo "📺 Opening Terminal window (140x65) with live logs..."
	@LATEST=$$(ls -t "$(CURDIR)/backend/z_slog/logs"/output-*.ansi 2>/dev/null | head -1); \
	if [ -n "$$LATEST" ]; then \
		osascript \
			-e "tell application \"Terminal\"" \
			-e "do script \"clear && echo '📋 Live Logger Output - z_slog' && echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━' && tail -f \\\"$$LATEST\\\"\"" \
			-e "set currentTab to selected tab of front window" \
			-e "set number of columns of currentTab to 140" \
			-e "set number of rows of currentTab to 65" \
			-e "set current settings of currentTab to settings set \"Pro\"" \
			-e "activate" \
			-e "end tell"; \
		echo "✅ Opened: $$LATEST"; \
	else \
		echo "❌ No log files found. Run 'make launch-logger' first to create logs."; \
	fi

# Show help
help:
	@echo "Available commands:"
	@echo "  make launch-logger  - Kill ports, start servers, open Terminal (140x65) with live logs"
	@echo "  make launch-backend - Kill backend port, run backend with colored logs"
	@echo "  make launch-frontend- Kill frontend port, run frontend"
	@echo "  make tail-logs      - Tail the latest .ansi log file in current terminal"
	@echo "  make open-logs      - Open new dark Terminal window with live log output"
	@echo "  make kill-ports     - Kill both frontend (3000) and backend (8080)"
	@echo "  make kill-frontend  - Kill only frontend (port 3000)"
	@echo "  make kill-backend   - Kill only backend (port 8080)"
	@echo "  make help           - Show this help message"
