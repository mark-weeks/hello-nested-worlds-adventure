# Infrastructure Stack

| Layer | Service | Notes |
|-------|---------|-------|
| Frontend | React + PixiJS | Scene rendering + UI shell |
| Backend | FastAPI + WebSockets | Python-primary, existing |
| Image generation | fal.ai (Flux Schnell) | Pay-as-you-go, no commitment |
| Cache | Redis (Railway or Render free tier) | Scene hash + session state |
| Image storage | Cloudflare R2 | Free tier 10 GB, zero egress |
| Multiplayer state | FastAPI WebSockets | Room-based, Python-native |
