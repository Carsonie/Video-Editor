# Mux Video Platform

A full-stack video streaming application using Mux for video infrastructure, with a Golang + SQLite backend and React + Vite + TypeScript + Mantine frontend.

## Project Structure

```
mux-example/
├── backend/                    # Go backend
│   ├── cmd/server/            # Server entry point
│   ├── internal/              # Internal packages
│   │   ├── api/              # HTTP handlers & middleware
│   │   ├── auth/             # JWT token generation
│   │   ├── db/               # SQLite database layer
│   │   └── mux/              # Mux API integration
│   ├── go.mod                # Go dependencies
│   └── .env.example          # Environment variables template
│
└── frontend/                  # React frontend
    ├── src/
    │   ├── components/       # React components
    │   ├── pages/            # Page components
    │   └── api/              # API client
    ├── package.json          # NPM dependencies
    └── .env.example          # Environment variables template
```

## Features

- **Video Upload**: Create video assets from URLs
- **Secure Playback**: JWT-signed playback tokens
- **Video Management**: List, view, and monitor encoding status
- **Analytics**: Video reports and statistics
- **Responsive UI**: Built with Mantine components

## Prerequisites

- Go 1.21 or higher
- Node.js 18 or higher
- Mux account with API credentials

## Setup

### 1. Backend Setup

```bash
cd backend

# Copy environment variables template
cp .env.example .env

# Generate RSA keys for JWT signing
openssl genrsa -out private_key.pem 2048
openssl rsa -in private_key.pem -pubout -out public_key.pem

# Update .env with your values:
# - MUX_TOKEN_ID and MUX_TOKEN_SECRET from Mux dashboard
# - JWT keys from generated PEM files (as single line with \n)

# Install dependencies
go mod tidy

# Run the server
go run ./cmd/server/main.go
```

Backend will start on `http://localhost:8080`

### 2. Frontend Setup

```bash
cd frontend

# Copy environment variables template
cp .env.example .env

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will start on `http://localhost:3000`

## API Endpoints

### Videos
- `GET /api/videos` - List all videos
- `POST /api/videos` - Create video from URL
- `GET /api/videos/:id` - Get video details
- `GET /api/videos/:id/status` - Check encoding status
- `POST /api/videos/:id/playback-token` - Generate JWT token

### Webhooks
- `POST /webhooks/mux` - Receive Mux webhook events

### Health
- `GET /health` - Health check

## Environment Variables

### Backend (.env)
```
MUX_TOKEN_ID=your-mux-token-id
MUX_TOKEN_SECRET=your-mux-token-secret
DATABASE_PATH=./videos.db
JWT_PRIVATE_KEY=your-private-key-pem
JWT_PUBLIC_KEY=your-public-key-pem
SERVER_PORT=8080
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:8080
```

## Usage

1. **Upload Video**: Navigate to Home page and provide a video URL
2. **Monitor Status**: Video status updates from "encoding" to "ready"
3. **Watch Videos**: Go to Knot page to browse and watch videos
4. **View Reports**: Check Reports page for video analytics

## Database

SQLite database is automatically created at `backend/videos.db` with the following tables:
- `videos` - Video metadata and Mux asset information
- `playback_tokens` - JWT tokens for secure playback

## Technologies

### Backend
- Go 1.21
- Gorilla Mux (HTTP router)
- SQLite (Database)
- Mux SDK (Video infrastructure)
- JWT (Authentication)

### Frontend
- React 18
- TypeScript
- Vite (Build tool)
- Mantine (UI library)
- React Router (Navigation)
- Axios (HTTP client)
- Mux Player (Video player)

## Development

### Backend
```bash
cd backend
go run ./cmd/server/main.go
```

### Frontend
```bash
cd frontend
npm run dev
```

### Build for Production

**Backend:**
```bash
cd backend
go build -o server ./cmd/server/main.go
```

**Frontend:**
```bash
cd frontend
npm run build
npm run preview
```

## License

MIT
