# HeyGen API — Missing Endpoints Addendum
# Source: HeyGen API Reference sidebar (screenshots reviewed June 23, 2026)
# These endpoints were missing from heygen_api.md — merge into that file.
# All endpoints are v3 unless noted.

---

## 2. VIDEO AGENT — Additional Endpoints

### 2.4 List Video Agent Sessions
- **Endpoint:** `GET /v3/video-agents`
- **Ref:** https://developers.heygen.com/reference/list-video-agent-sessions
- **Description:**

### 2.5 List Video Agent Styles
- **Endpoint:** `GET /v3/video-agents/styles`
- **Ref:** https://developers.heygen.com/reference/list-video-agent-styles
- **Description:**

### 2.6 Send Message or Request Revision
- **Endpoint:** `POST /v3/video-agents/{session_id}/messages`
- **Ref:** https://developers.heygen.com/reference/send-message-or-request-revision
- **Description:**

### 2.7 Get Session Resource
- **Endpoint:** `GET /v3/video-agents/{session_id}/resources`
- **Ref:** https://developers.heygen.com/reference/get-session-resource
- **Description:**

### 2.8 List Session Videos
- **Endpoint:** `GET /v3/video-agents/{session_id}/videos`
- **Ref:** https://developers.heygen.com/reference/list-session-videos
- **Description:**

### 2.9 Stop Video Agent Session
- **Endpoint:** `POST /v3/video-agents/{session_id}/stop`
- **Ref:** https://developers.heygen.com/reference/stop-video-agent-session
- **Description:**

---

## 4. AVATARS — Additional Endpoints

### 4.5 Create Avatar
- **Endpoint:** `POST /v3/avatars`
- **Ref:** https://developers.heygen.com/reference/create-avatar
- **Description:**

### 4.6 Get Avatar Group
- **Endpoint:** `GET /v3/avatars/{group_id}`
- **Ref:** https://developers.heygen.com/reference/get-avatar-group
- **Description:**

### 4.7 Delete Avatar Group
- **Endpoint:** `DELETE /v3/avatars/{group_id}`
- **Ref:** https://developers.heygen.com/reference/delete-avatar-group
- **Description:**

### 4.8 Create Avatar Consent
- **Endpoint:** `POST /v3/avatars/{group_id}/consent`
- **Ref:** https://developers.heygen.com/reference/create-avatar-consent
- **Description:**

### 4.9 List Avatar Looks
- **Endpoint:** `GET /v3/avatars/looks`
- **Ref:** https://developers.heygen.com/reference/list-avatar-looks
- **Description:**

### 4.10 Delete Avatar Look
- **Endpoint:** `DELETE /v3/avatars/looks/{look_id}`
- **Ref:** https://developers.heygen.com/reference/delete-avatar-look
- **Description:**

### 4.11 Update Avatar Look
- **Endpoint:** `PATCH /v3/avatars/looks/{look_id}`
- **Ref:** https://developers.heygen.com/reference/update-avatar-look
- **Description:**

---

## 6. VOICES — Additional Endpoints

### 6.3 Design a Voice
- **Endpoint:** `POST /v3/voices/design`
- **Ref:** https://developers.heygen.com/reference/design-a-voice
- **Description:**

### 6.4 Clone a Voice
- **Endpoint:** `POST /v3/voices/clone`
- **Ref:** https://developers.heygen.com/reference/clone-a-voice
- **Description:**

### 6.5 Get Voice
- **Endpoint:** `GET /v3/voices/{voice_id}`
- **Ref:** https://developers.heygen.com/reference/get-voice
- **Description:**

### 6.6 Delete a Voice
- **Endpoint:** `DELETE /v3/voices/{voice_id}`
- **Ref:** https://developers.heygen.com/reference/delete-a-voice
- **Description:**

---

## 8. VIDEO TRANSLATE — Additional Endpoints

### 8.4 List Video Translations
- **Endpoint:** `GET /v3/video-translations`
- **Ref:** https://developers.heygen.com/reference/list-video-translations
- **Description:**

### 8.5 Delete Video Translation
- **Endpoint:** `DELETE /v3/video-translations/{video_translate_id}`
- **Ref:** https://developers.heygen.com/reference/delete-video-translation
- **Description:**

### 8.6 Update Video Translation
- **Endpoint:** `PATCH /v3/video-translations/{video_translate_id}`
- **Ref:** https://developers.heygen.com/reference/update-video-translation
- **Description:**

### 8.7 Create Proofread Session
- **Endpoint:** `POST /v3/video-translations/proofreads`
- **Ref:** https://developers.heygen.com/reference/create-proofread-session
- **Description:**

### 8.8 Get Proofread Session
- **Endpoint:** `GET /v3/video-translations/proofreads/{proofread_id}`
- **Ref:** https://developers.heygen.com/reference/get-proofread-session
- **Description:**

### 8.9 Download Proofread SRT
- **Endpoint:** `GET /v3/video-translations/proofreads/{proofread_id}/srt`
- **Ref:** https://developers.heygen.com/reference/download-proofread-srt
- **Description:**

### 8.10 Upload Proofread SRT
- **Endpoint:** `PUT /v3/video-translations/proofreads/{proofread_id}/srt`
- **Ref:** https://developers.heygen.com/reference/upload-proofread-srt
- **Description:**

### 8.11 Generate Video from Proofread
- **Endpoint:** `POST /v3/video-translations/proofreads/{proofread_id}/generate`
- **Ref:** https://developers.heygen.com/reference/generate-video-from-proofread
- **Description:**

---

## 9. LIPSYNC — Additional Endpoints

### 9.3 List Lipsyncs
- **Endpoint:** `GET /v3/lipsyncs`
- **Ref:** https://developers.heygen.com/reference/list-lipsyncs
- **Description:**

### 9.4 Delete Lipsync
- **Endpoint:** `DELETE /v3/lipsyncs/{lipsync_id}`
- **Ref:** https://developers.heygen.com/reference/delete-lipsync
- **Description:**

### 9.5 Update Lipsync
- **Endpoint:** `PATCH /v3/lipsyncs/{lipsync_id}`
- **Ref:** https://developers.heygen.com/reference/update-lipsync
- **Description:**

---

## 11. ASSETS — Additional Endpoints

### 11.4 Get Asset
- **Endpoint:** `GET /v3/assets/{asset_id}`
- **Ref:** https://developers.heygen.com/reference/get-asset
- **Description:**

### 11.5 Create Asset Upload
- **Endpoint:** `POST /v3/assets/uploads`
- **Ref:** https://developers.heygen.com/reference/create-asset-upload
- **Description:**

### 11.6 Complete Asset Upload
- **Endpoint:** `POST /v3/assets/uploads/{upload_id}/complete`
- **Ref:** https://developers.heygen.com/reference/complete-asset-upload
- **Description:**

---

## 13. WEBHOOKS — Additional Endpoints

### 13.4 List Webhook Event Types
- **Endpoint:** `GET /v3/webhooks/events/types`
- **Ref:** https://developers.heygen.com/reference/list-webhook-event-types
- **Description:**

### 13.5 Update Webhook Endpoint
- **Endpoint:** `PATCH /v3/webhooks/endpoints/{endpoint_id}`
- **Ref:** https://developers.heygen.com/reference/update-webhook-endpoint
- **Description:** NOTE: PATCH performs a FULL REPLACEMENT of the event types array —
  include ALL desired events in a single call, not just the ones you want to add.

### 13.6 Rotate Webhook Signing Secret
- **Endpoint:** `POST /v3/webhooks/endpoints/{endpoint_id}/secret/rotate`
- **Ref:** https://developers.heygen.com/reference/rotate-webhook-signing-secret
- **Description:**

### 13.7 List Webhook Events
- **Endpoint:** `GET /v3/webhooks/events`
- **Ref:** https://developers.heygen.com/reference/list-webhook-events
- **Description:**

---

## 16. AUDIO (NEW SECTION)

### 16.1 Search Audio Music or Sound Effects
- **Endpoint:** `GET /v3/audio/search`
- **Ref:** https://developers.heygen.com/reference/search-audio-music-or-sound-effects
- **Description:**

---

## 17. BRAND (NEW SECTION)

### 17.1 List Brand Glossaries
- **Endpoint:** `GET /v3/brand-kits/glossaries`
- **Ref:** https://developers.heygen.com/reference/list-brand-glossaries
- **Description:**

### 17.2 List Brand Kits
- **Endpoint:** `GET /v3/brand-kits`
- **Ref:** https://developers.heygen.com/reference/list-brand-kits
- **Description:**

---

## 18. AVATAR REALTIME (NEW SECTION — replaces legacy Streaming)

### 18.1 Create Avatar Realtime Session
- **Endpoint:** `POST /v3/avatars/realtime/sessions`
- **Ref:** https://developers.heygen.com/reference/create-avatar-realtime-session
- **Description:**

### 18.2 Get Avatar Realtime Session
- **Endpoint:** `GET /v3/avatars/realtime/sessions/{session_id}`
- **Ref:** https://developers.heygen.com/reference/get-avatar-realtime-session
- **Description:**

### 18.3 Stream Avatar Realtime Word Timestamps
- **Endpoint:** `GET /v3/avatars/realtime/sessions/{session_id}/words`
- **Ref:** https://developers.heygen.com/reference/stream-avatar-realtime-word-timestamps
- **Description:**

### 18.4 Append Avatar Realtime Text
- **Endpoint:** `POST /v3/avatars/realtime/sessions/{session_id}/text`
- **Ref:** https://developers.heygen.com/reference/append-avatar-realtime-text
- **Description:**

### 18.5 Cancel Avatar Realtime Session
- **Endpoint:** `POST /v3/avatars/realtime/sessions/{session_id}/cancel`
- **Ref:** https://developers.heygen.com/reference/cancel-avatar-realtime-session
- **Description:**
