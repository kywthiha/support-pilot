## Run with Docker

You can run the container directly from Docker Hub.

```bash
docker run -p 8080:8080 \
-e AGENT_MODEL="gemini-2.5-flash-native-audio-preview-12-2025" \
-e OBSERVE_MODEL="gemini-3-flash-preview" \
-e GOOGLE_API_KEY="YOUR_GOOGLE_AI_STUDIO_API_KEY" \
-e GOOGLE_GENAI_USE_VERTEXAI=FALSE \
kyawthihadev/support-agent:latest
```

### Environment Variables

| Variable                    | Description                   |
| --------------------------- | ----------------------------- |
| `AGENT_MODEL`               | Model used for the agent      |
| `OBSERVE_MODEL`             | Model used for observation    |
| `GOOGLE_API_KEY`            | API key from Google AI Studio |
| `GOOGLE_GENAI_USE_VERTEXAI` | Set to FALSE for local API key|

Get your API key from Google AI Studio.

---

### Open the Application

After running the container:

```
http://localhost:8080
```

---

### Notes

- Replace `YOUR_GOOGLE_AI_STUDIO_API_KEY` with your real API key.
