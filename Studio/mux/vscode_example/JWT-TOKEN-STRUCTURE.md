# JWT Token Structure for Mux Signed Playback

## Overview
JWT (JSON Web Token) tokens are used to secure Mux video playback. Each token is signed with your private RSA key and verified by Mux using your registered public key.

---

## Token Structure

A JWT token consists of three parts separated by dots (`.`):

```
HEADER.PAYLOAD.SIGNATURE
```

Example:
```
eyJhbGciOiJSUzI1NiIsImtpZCI6IjJiQ29wWnowMGNteTdDV21wTzAxZzR6aElrY2NOSmdUaXcyWHJIbUdDOUQ1RSIsInR5cCI6IkpXVCJ9
.
eyJhdWQiOiJ2IiwiZXhwIjoxNzY5MTE2NDk5LCJpYXQiOjE3NjkxMTI4OTksIm5iZiI6MTc2OTExMjg5OSwic3ViIjoiMlBVb2EzVk5qYmZlSmdrS05DekFEQk9iN3pMcloxMDFsdU9BbEhDenRQeW8ifQ
.
kqsiRKGMU1BZq3JXbJL5ThQX8MiexdXIFFd6a8ZLvlDrXQiKoP...
```

---

## Part 1: HEADER

The header specifies the algorithm and key used to sign the token.

```json
{
  "alg": "RS256",
  "kid": "2bCopZz00cmy7CWmpO01g4zhIkccNJgTiw2XrHmGC9D5E",
  "typ": "JWT"
}
```

### Fields:
- **alg** (Algorithm): `RS256` = RSA Signature with SHA-256
  - This is an asymmetric signing algorithm
  - Requires a private key for signing
  - Requires a public key for verification

- **kid** (Key ID): Your Mux signing key identifier
  - This tells Mux which public key to use for verification
  - Must match the key ID registered in your Mux account

- **typ** (Type): `JWT` = JSON Web Token standard

---

## Part 2: PAYLOAD (Claims)

The payload contains the claims - information about the token and authorization.

```json
{
  "aud": "v",
  "sub": "2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo",
  "iat": 1769112899,
  "nbf": 1769112899,
  "exp": 1769116499
}
```

### Standard JWT Claims:

#### **aud** (Audience)
Specifies what this token can be used for:
- `"v"` = Video playback (streaming)
- `"t"` = Thumbnail images
- `"s"` = Storyboard (scrubbing preview)
- `"g"` = GIF generation (optional)

**Important**: Mux validates the audience. A video playback token (`aud: v`) cannot be used to access thumbnails.

#### **sub** (Subject)
The Mux playback ID that this token authorizes access to:
- Format: 22-character alphanumeric string
- Example: `2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo`
- This MUST be the **signed playback ID**, not the public one

#### **iat** (Issued At)
Unix timestamp when the token was created:
- Example: `1769112899` = 2026-01-22 15:14:59 UTC
- Used to determine token age

#### **nbf** (Not Before)
Unix timestamp before which the token is not valid:
- Usually the same as `iat`
- Prevents tokens from being used before they're issued

#### **exp** (Expires At)
Unix timestamp when the token expires:
- Example: `1769116499` = 2026-01-22 16:14:59 UTC (1 hour after iat)
- After this time, Mux will reject the token
- **Default**: 1 hour from issuance
- **Recommended**: 1-24 hours depending on use case

### Token Lifespan Calculation:
```
exp - iat = 3600 seconds = 1 hour
```

---

## Part 3: SIGNATURE

The signature is created by:
1. Taking the encoded header and payload: `base64(header).base64(payload)`
2. Signing it with your RSA private key using SHA-256
3. Base64-encoding the signature

```
signature = RSA-SHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  privateKey
)
```

Example signature (truncated):
```
kqsiRKGMU1BZq3JXbJL5ThQX8MiexdXIFFd6a8ZLvlDrXQiKoP...
```

### Verification Process:
1. Mux receives the token
2. Extracts the `kid` from the header
3. Retrieves the corresponding public key from their database
4. Verifies the signature using the public key
5. Checks `exp`, `nbf`, `aud`, and `sub` claims
6. Grants or denies access

---

## Three Token Types

Your application generates three tokens for each video request:

### 1. Playback Token (aud: "v")
Used for: Video streaming (HLS .m3u8 files)

**URL Example:**
```
https://stream.mux.com/{playback_id}.m3u8?token={playback_token}
```

**Payload:**
```json
{
  "aud": "v",
  "sub": "2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo",
  "exp": 1769116499,
  "iat": 1769112899,
  "nbf": 1769112899
}
```

### 2. Thumbnail Token (aud: "t")
Used for: Static thumbnail images

**URL Example:**
```
https://image.mux.com/{playback_id}/thumbnail.png?token={thumbnail_token}&width=640&time=1.0
```

**Payload:**
```json
{
  "aud": "t",
  "sub": "2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo",
  "exp": 1769116499,
  "iat": 1769112899,
  "nbf": 1769112899
}
```

### 3. Storyboard Token (aud: "s")
Used for: Video scrubbing preview (VTT files)

**URL Example:**
```
https://image.mux.com/{playback_id}/storyboard.vtt?token={storyboard_token}
```

**Payload:**
```json
{
  "aud": "s",
  "sub": "2PUoa3VNjbfeJgkKNCzADBOb7zLrZ101luOAlHCztPyo",
  "exp": 1769116499,
  "iat": 1769112899,
  "nbf": 1769112899
}
```

---

## Security Features

### 1. Asymmetric Cryptography (RSA)
- **Private Key**: Kept secret on your server, used to sign tokens
- **Public Key**: Registered with Mux, used to verify tokens
- Even if someone intercepts a token, they can't create new ones without your private key

### 2. Time-Based Expiration
- Tokens are only valid for 1 hour (configurable)
- If a token is leaked, it becomes useless after expiration
- Users must request new tokens to continue watching

### 3. Audience Restriction
- Each token is limited to a specific use case (video, thumbnail, or storyboard)
- A video token cannot be used to access other resources

### 4. Playback ID Binding
- Each token is tied to a specific video (playback ID)
- A token for video A cannot be used to access video B

---

## Token Generation Code

In your backend (`backend/internal/auth/tokens.go`):

```go
func (tm *TokenManager) generateToken(playbackID, audience string, expiresIn time.Duration) (string, error) {
    now := time.Now()
    claims := jwt.MapClaims{
        "sub": playbackID,    // Signed playback ID
        "aud": audience,      // "v", "t", or "s"
        "exp": now.Add(expiresIn).Unix(),  // Expiration time
        "iat": now.Unix(),    // Issued at
        "nbf": now.Unix(),    // Not before
    }

    token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
    token.Header["kid"] = tm.keyID  // Add key ID to header

    tokenString, err := token.SignedString(tm.privateKey)
    if err != nil {
        return "", fmt.Errorf("failed to sign token: %w", err)
    }

    return tokenString, nil
}
```

---

## Token Usage Flow

```
1. User clicks "Watch Video"
   ↓
2. Frontend requests playback token from backend
   GET /api/videos/{id}/playback-token
   ↓
3. Backend generates three JWT tokens:
   - Playback token (aud: v)
   - Thumbnail token (aud: t)
   - Storyboard token (aud: s)
   ↓
4. Frontend receives tokens and passes to Mux Player
   ↓
5. Mux Player makes requests to Mux CDN:
   - https://stream.mux.com/{playback_id}.m3u8?token={playback_token}
   - https://image.mux.com/{playback_id}/thumbnail.png?token={thumbnail_token}
   - https://image.mux.com/{playback_id}/storyboard.vtt?token={storyboard_token}
   ↓
6. Mux CDN verifies each token:
   - Checks signature with public key
   - Validates expiration
   - Verifies audience matches request type
   - Confirms playback ID matches
   ↓
7. If valid: Stream video content
   If invalid: Return 400/403 error
```

---

## Token Expiration Handling

### Frontend Behavior:
When a token expires after 1 hour:
1. Video playback stops
2. Frontend detects the error
3. Automatically requests new tokens from backend
4. Resumes playback with fresh tokens

### Backend Considerations:
- Tokens are generated on-demand (not stored)
- No database lookup needed for token generation
- Can generate thousands of tokens per second
- Each user gets unique tokens

---

## Debugging JWT Tokens

### Online Decoder:
Visit https://jwt.io and paste your token to see the decoded header and payload.

### Command Line:
```bash
# Decode token header
echo "eyJhbGc..." | base64 -d

# Decode token payload
echo "eyJhdWQ..." | base64 -d
```

### Verify Token in Browser Console:
```javascript
// Split token into parts
const parts = token.split('.');

// Decode header
const header = JSON.parse(atob(parts[0]));
console.log('Header:', header);

// Decode payload
const payload = JSON.parse(atob(parts[1]));
console.log('Payload:', payload);

// Check expiration
const now = Math.floor(Date.now() / 1000);
console.log('Expired:', payload.exp < now);
console.log('Time until expiry:', (payload.exp - now) / 60, 'minutes');
```

---

## Common Issues

### 1. Token Expired (403 Forbidden)
**Cause**: Token's `exp` timestamp has passed
**Solution**: Request new token from backend

### 2. Invalid Signature (400 Bad Request)
**Cause**: Public key doesn't match private key, or wrong key ID
**Solution**: Verify `kid` matches Mux account, check key registration

### 3. Wrong Audience (400 Bad Request)
**Cause**: Using playback token for thumbnails or vice versa
**Solution**: Use correct token type for each resource

### 4. Wrong Playback ID (404 Not Found)
**Cause**: Token `sub` doesn't match requested playback ID
**Solution**: Ensure token is generated for the correct video

---

## Security Best Practices

### ✅ DO:
- Keep private key secret (never commit to git)
- Store private key in environment variables
- Use 1-hour expiration for tokens
- Generate tokens on-demand for each request
- Use signed playback IDs for all videos
- Rotate signing keys periodically (every 6-12 months)

### ❌ DON'T:
- Expose private key in frontend code
- Use same token for multiple users
- Set expiration longer than 24 hours
- Store tokens in database
- Use public playback IDs with signed tokens
- Share tokens between different videos

---

## Summary

**JWT tokens provide secure, time-limited access to Mux videos** by:
1. Using RSA signatures to prevent tampering
2. Setting expiration times to limit token lifetime
3. Binding tokens to specific resources (playback IDs)
4. Restricting token usage by audience type

Your backend generates tokens on-demand, and Mux verifies them automatically. Users get seamless video playback with enterprise-grade security.
