# FloodGate Walkthrough

## Task 1 — DoS Fundamentals
Understand the difference between legitimate traffic and excessive traffic and how excessive requests can affect service availability.

## Task 2 — Reconnaissance
Inspect the local FloodGate service and identify its HTTP port and important endpoints.

Useful endpoints:
- `/`
- `/dashboard`
- `/stats`
- `/logs`

## Task 3 — Traffic Analysis
Run the controlled traffic simulation and compare successful requests with rate-limited requests.

The lab intentionally limits requests so learners can observe the difference between normal and blocked traffic.

## Task 4 — Detection
Review the dashboard and logs.

Look for:
- Allowed requests
- Blocked requests
- Source address
- HTTP response changes
- Repeated traffic patterns

## Task 5 — Rate Limiting
Study how the request limit protects service availability.

When the configured threshold is exceeded, the application returns HTTP 429.

## Task 6 — Incident Investigation
Use the statistics and logs to reconstruct the simulated event.

Determine:
- Total requests
- Allowed requests
- Blocked requests
- Requests per second
- Whether rate limiting occurred
- What traffic pattern was observed

## Task 7 — Final Challenge
Combine the previous investigation techniques.

Use:
- `/dashboard`
- `/stats`
- `/logs`

Identify the traffic pattern and the defensive mechanism responsible for controlling excessive requests.

## Conclusion
FloodGate demonstrates the defensive lifecycle:

Observe → Analyze → Detect → Investigate → Defend
