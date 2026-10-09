# GeoPathfinder Roadmap

## Phase 1 — Configure routing services

### 1. Obtain an openrouteservice (ORS) API key

ORS is required for the currently implemented walking, cycling, and driving
route calculations.

1. Create an account or sign in at <https://openrouteservice.org/log-in/>.
2. Verify the account email if prompted.
3. In the developer dashboard, open **API Key** and copy the **Basic Key**.
4. Store the key locally in `api_keys/ORS_API_KEY.key`; never commit it to Git
   or place it in tracked files.

Place the Basic Key as the only content of this file:

```text
api_keys/ORS_API_KEY.key
```

The package uses the current `api.heigit.org` ORS host by default. The former
`api.openrouteservice.org` endpoint is deprecated and has reduced quota during
the migration period.

Validate the setup with:

```powershell
geopathfinder route "10 rue Denfert Rochereau, 33130 Bègles" "2 rue Marc Sangnier, 33130 Bègles" --mode walking
```

### 2. Use BAN geocoding — no API key required

The French Base Adresse Nationale (BAN) / IGN geocoding endpoint used by this
package is publicly available without an API key. No signup or local secret is
required for the initial implementation.

The package defaults to:

```text
https://data.geopf.fr/geocodage/search
```

Respect the public service's limits and cache repeated address lookups before
running large batches.

## Phase 2 — Public transport (not implemented)

Decide whether the first public-transport scope is Bordeaux Métropole only or
all of France. For Bordeaux, evaluate TBM GTFS/GTFS-Realtime data with a
self-hosted OpenTripPlanner instance. This route is expected to use public
open-data feeds rather than an API key, but needs regular data refreshes and
local service operation.

## Phase 3 — Scale safely

- Add local caching for BAN geocoding and ORS route responses.
- Configure retry/back-off handling for temporary provider failures and rate
  limits.
- Move the local key file into a secret manager if the tool is automated; keep
  the secret outside version control.
- If ORS's hosted quota becomes insufficient, evaluate self-hosting ORS or an
  alternate routing provider behind the existing service interface.
