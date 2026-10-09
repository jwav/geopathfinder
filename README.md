# GeoPathfinder

GeoPathfinder is a Python package and command-line tool for finding travel
durations between two French addresses.

The initial implementation uses the French Base Adresse Nationale (BAN) to
geocode addresses and openrouteservice (ORS) for walking, cycling, and driving
routes. Public-transport routing is planned but not implemented yet.

## Install for development

```powershell
python -m pip install -e .
```

## Configure

Create `api_keys/ORS_API_KEY.key` and place the ORS **Basic Key** on its only
line. The key is loaded internally; you do not need to set an environment
variable.

The `api_keys/` directory is ignored by Git.

For testing against compatible local services, use `--ban-base-url` and
`--ors-base-url`.

## Use

```powershell
geopathfinder route "18 rue Savariau, 33130 Bègles" "156 Rue Marcel Sembat, 33130 Bègles"
geopathfinder route "18 rue Savariau, 33130 Bègles" "156 Rue Marcel Sembat, 33130 Bègles" --mode walking --json
```

Use `geopathfinder --help` for the complete command reference.

