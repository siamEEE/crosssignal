# Public deployment boundary

The application has not been deployed. Checkpoint `49cf591` remains unchanged.

The API rejects bodies over 32 KiB on upstream-backed endpoints, limits their
combined traffic to 60 requests per minute per process, and allows four concurrent
upstream-backed requests per process. Excess work returns 429. Browser Origin
headers must match the serving origin. Requests without Origin remain supported
for local clients; this is not authentication. Health and static reference
endpoints remain available during throttling.

These are single-process guardrails, not a distributed quota or spending cap.
Before a public release, configure the host's shared rate limits and provider
quotas, restrict trusted proxy/host handling, and serve the UI and API on the
same HTTPS origin. Multiple workers each have their own budget and cache.
No hosting service, paid integration, or deployment has been introduced.

Keep provider credentials server-side. Do not put them in Vite variables, frontend
builds, URLs, or browser storage. Browser storage contains the viewer's taste
profile only. Search links open music services without API access or credentials;
they are artist searches and do not promise an exact catalog match.

Remaining release checks: actual desktop/mobile rendering, keyboard and screen
reader navigation, iOS audio playback, and live recommendation quality. The
production frontend still emits a bundle-size warning (~519 kB before gzip).
