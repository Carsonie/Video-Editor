package auth

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/yourname/mux-example/z_slog"
)

// TokenManager handles JWT token generation for Mux playback
type TokenManager struct {
	privateKey *rsa.PrivateKey
	publicKey  *rsa.PublicKey
	keyID      string
}

// PlaybackClaims represents the JWT claims for Mux playback
type PlaybackClaims struct {
	jwt.RegisteredClaims
}

// New creates a new TokenManager with RSA key pairs
func New(privateKeyPEM, keyID string) (*TokenManager, error) {
	z_slog.FunctionEntry("New")
	// Parse private key
	privateKey, err := parsePrivateKey(privateKeyPEM)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"tokenManager": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to parse private key: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"tokenManager": "TokenManager", "keyID": keyID})
	return &TokenManager{
		privateKey: privateKey,
		publicKey:  &privateKey.PublicKey,
		keyID:      keyID,
	}, nil
}

// GeneratePlaybackToken generates a signed JWT token for Mux playback
func (tm *TokenManager) GeneratePlaybackToken(videoID, playbackID string, expiresIn time.Duration) (string, error) {
	z_slog.FunctionEntry("GeneratePlaybackToken")
	z_slog.Values(map[string]any{"videoID": videoID, "playbackID": playbackID, "expiresIn": expiresIn.String()})
	token, err := tm.generateTokenWithAudience(playbackID, "v", expiresIn)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"token": "", "error": err.Error()})
	} else {
		z_slog.ReturnValues(map[string]any{"token": "generated", "error": nil})
	}
	return token, err
}

// GenerateThumbnailToken generates a signed JWT token for Mux thumbnails
func (tm *TokenManager) GenerateThumbnailToken(playbackID string, expiresIn time.Duration) (string, error) {
	z_slog.FunctionEntry("GenerateThumbnailToken")
	z_slog.Values(map[string]any{"playbackID": playbackID, "expiresIn": expiresIn.String()})
	token, err := tm.generateTokenWithAudience(playbackID, "t", expiresIn)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"token": "", "error": err.Error()})
	} else {
		z_slog.ReturnValues(map[string]any{"token": "generated", "error": nil})
	}
	return token, err
}

// GenerateStoryboardToken generates a signed JWT token for Mux storyboards
func (tm *TokenManager) GenerateStoryboardToken(playbackID string, expiresIn time.Duration) (string, error) {
	z_slog.FunctionEntry("GenerateStoryboardToken")
	z_slog.Values(map[string]any{"playbackID": playbackID, "expiresIn": expiresIn.String()})
	token, err := tm.generateTokenWithAudience(playbackID, "s", expiresIn)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"token": "", "error": err.Error()})
	} else {
		z_slog.ReturnValues(map[string]any{"token": "generated", "error": nil})
	}
	return token, err
}

// generateTokenWithAudience generates a JWT token with a specific audience
func (tm *TokenManager) generateTokenWithAudience(playbackID, audience string, expiresIn time.Duration) (string, error) {
	z_slog.FunctionEntry("generateTokenWithAudience")
	now := time.Now()
	expiresAt := now.Add(expiresIn)

	// Create claims map manually to have precise control over the format
	claims := jwt.MapClaims{
		"sub": playbackID,       // Mux requires playback ID as subject
		"aud": audience,          // Audience: "v" (video), "t" (thumbnail), "s" (storyboard)
		"exp": expiresAt.Unix(), // Expiration timestamp
		"iat": now.Unix(),       // Issued at timestamp
		"nbf": now.Unix(),       // Not before timestamp
	}

	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	token.Header["kid"] = tm.keyID

	signedToken, err := token.SignedString(tm.privateKey)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"token": "", "error": err.Error()})
		return "", fmt.Errorf("failed to sign token: %w", err)
	}

	z_slog.ReturnValues(map[string]any{"token": "signed", "error": nil})
	return signedToken, nil
}

// ValidateToken validates a JWT token and returns the claims
func (tm *TokenManager) ValidateToken(tokenString string) (*PlaybackClaims, error) {
	z_slog.FunctionEntry("ValidateToken")
	token, err := jwt.ParseWithClaims(tokenString, &PlaybackClaims{}, func(token *jwt.Token) (interface{}, error) {
		// Verify signing method
		if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		return tm.publicKey, nil
	})

	if err != nil {
		z_slog.ReturnValues(map[string]any{"claims": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	claims, ok := token.Claims.(*PlaybackClaims)
	if !ok || !token.Valid {
		z_slog.ReturnValues(map[string]any{"claims": nil, "error": "invalid token claims"})
		return nil, errors.New("invalid token claims")
	}

	z_slog.ReturnValues(map[string]any{"claims": "valid", "error": nil})
	return claims, nil
}

// GetKeyID returns the key ID used for signing
func (tm *TokenManager) GetKeyID() string {
	z_slog.FunctionEntry("GetKeyID")
	z_slog.ReturnValues(map[string]any{"keyID": tm.keyID})
	return tm.keyID
}

// parsePrivateKey parses a PEM-encoded RSA private key
func parsePrivateKey(pemString string) (*rsa.PrivateKey, error) {
	z_slog.FunctionEntry("parsePrivateKey")
	block, _ := pem.Decode([]byte(pemString))
	if block == nil {
		z_slog.ReturnValues(map[string]any{"privateKey": nil, "error": "failed to decode PEM block"})
		return nil, errors.New("failed to decode PEM block containing private key")
	}

	// Try PKCS1 format first
	privateKey, err := x509.ParsePKCS1PrivateKey(block.Bytes)
	if err == nil {
		z_slog.ReturnValues(map[string]any{"privateKey": "parsed (PKCS1)", "error": nil})
		return privateKey, nil
	}

	// Try PKCS8 format
	key, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"privateKey": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to parse private key: %w", err)
	}

	rsaKey, ok := key.(*rsa.PrivateKey)
	if !ok {
		z_slog.ReturnValues(map[string]any{"privateKey": nil, "error": "key is not RSA private key"})
		return nil, errors.New("key is not RSA private key")
	}

	z_slog.ReturnValues(map[string]any{"privateKey": "parsed (PKCS8)", "error": nil})
	return rsaKey, nil
}

// parsePublicKey parses a PEM-encoded RSA public key
func parsePublicKey(pemString string) (*rsa.PublicKey, error) {
	z_slog.FunctionEntry("parsePublicKey")
	block, _ := pem.Decode([]byte(pemString))
	if block == nil {
		z_slog.ReturnValues(map[string]any{"publicKey": nil, "error": "failed to decode PEM block"})
		return nil, errors.New("failed to decode PEM block containing public key")
	}

	// Try PKIX format
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		z_slog.ReturnValues(map[string]any{"publicKey": nil, "error": err.Error()})
		return nil, fmt.Errorf("failed to parse public key: %w", err)
	}

	rsaKey, ok := pub.(*rsa.PublicKey)
	if !ok {
		z_slog.ReturnValues(map[string]any{"publicKey": nil, "error": "key is not RSA public key"})
		return nil, errors.New("key is not RSA public key")
	}

	z_slog.ReturnValues(map[string]any{"publicKey": "parsed", "error": nil})
	return rsaKey, nil
}
