# Travel Duration Finder — Specifications

## 1. Project overview

This is an installable Python package with a command-line interface (CLI). It
calculates estimated travel durations between a start address and a destination
address. The initial geographic scope is France, with priority given to
reliable results in and around Bordeaux.

The application must support these modes of travel:

- Walking
- Cycling
- Car
- Public transport

## 2. Goal

Given two user-provided addresses, return the travel duration for every
supported transport mode. Results should be clear about the route provider,
the time at which the estimate applies, and any unavailable modes.

## 3. Functional requirements

### Inputs

- Start address (required)
- Destination address (required)
- Requested transport mode(s); default: all supported modes
- Departure date and time, particularly for public transport; default: now

### Outputs

For each requested mode, provide at minimum:

- Estimated duration
- Route distance, where available
- Provider used
- Status/error when no route is available

For public transport, also provide when available:

- Departure and arrival time
- Number of transfers
- A concise itinerary summary (for example, walking + tram/bus lines)

### Address handling

- Convert French address text into geographic coordinates through a geocoding
  service.
- Detect and report ambiguous or unresolvable addresses.
- Support addresses in Bordeaux Métropole and elsewhere in France.

## 4. Initial delivery and interface

- The first release is a Python package, with no GUI or web application.
- It exposes an installable `geopathfinder` command and supports
  `python -m geopathfinder`.
- The initial command accepts a start address, destination address, one or more
  modes, and a machine-readable JSON output option.
- The initial use case is personal use, but the architecture should safely
  support substantially higher request volume later through caching, rate-limit
  handling, and replaceable/self-hostable service adapters.

## 5. Provider selection criteria

No provider has been selected yet. The solution should favour a free option
that is legal to use, dependable in France, and suitable for the expected
request volume.

Evaluation criteria:

- Coverage and route quality in Bordeaux and France
- Support for all four travel modes
- Public-transport timetable and real-time-data availability
- Free-tier limits and attribution/licensing obligations
- API stability, Python integration, rate limits, and self-hosting options

Likely provider categories to evaluate:

- OpenStreetMap-based routing for walking, cycling, and driving
- French public-transport open-data sources, especially Bordeaux Métropole / TBM
- A unified routing API, if a genuinely suitable free tier exists

The provider layer should be isolated behind an interface so one service can
be replaced without changing the rest of the application.

### Selected first integrations

- **BAN (Base Adresse Nationale):** geocodes French addresses. It is a free
  French public service and is the initial address provider.
- **openrouteservice (ORS):** calculates walking, cycling, and driving routes
  from coordinates. The initial client uses the hosted API and requires an API
  key configured outside source control.
- **Public transport:** deferred until the target geographic scope is decided.
  For Bordeaux, TBM GTFS/GTFS-Realtime data plus a self-hosted OpenTripPlanner
  instance is the leading free option; it has operational and feed-refresh
  costs despite no per-request API fee.

## 6. Technical requirements

- Python implementation.
- Package code lives under `src/geopathfinder`; provider integrations live
  under `src/geopathfinder/services`.
- Avoid a required runtime dependency where Python's standard library is
  sufficient for an HTTP integration.
- ORS authentication loads its key from the ignored local file
  `api_keys/ORS_API_KEY.key`; secrets must not be committed or printed.
- Optional provider endpoint overrides use CLI arguments rather than requiring
  users to set environment variables.
- Typed, testable provider adapters.
- Time-zone-aware date handling using Europe/Paris for French journeys.
- Structured error handling for network failures, rate limits, invalid input,
  and routes that cannot be calculated.
- Automated tests for address validation, response normalization, and provider
  error handling. External calls should be mocked in unit tests.
- Logging that supports troubleshooting without exposing user addresses beyond
  what is necessary.

## 7. Initial non-goals

- Booking tickets, making payments, or purchasing public-transport fares
- Turn-by-turn navigation
- Live vehicle tracking, unless it becomes a later requirement
- Worldwide routing quality guarantees

## 8. Questions to refine the specification

1. Must public-transport estimates use a chosen future departure time, or is a
   current/typical journey-time estimate sufficient initially?
2. Do you need detailed public-transport itineraries, or only a single total
   duration per mode?
3. Should car results account for live traffic, or is standard route duration
   acceptable?
4. Do you need one provider for every mode, or is combining routing and public
   transport providers acceptable?
5. Will addresses only be typed manually, or should the app accept coordinates,
   CSV files, or batches of origins/destinations too?
6. Are there constraints on where requests/data may be processed or stored?

