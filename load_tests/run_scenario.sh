#!/usr/bin/env bash
# Run a specific load test scenario.
# Usage: ./load_tests/run_scenario.sh <scenario_name> [host]
#   scenario_name: smoke, 30, 50, 70, 100, 150, 200
#   host: default http://localhost:8000
set -euo pipefail

SCENARIO="${1:-70}"
HOST="${2:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT_DIR="$SCRIPT_DIR/reports"
mkdir -p "$REPORT_DIR"

declare -A USERS SPAWN_RATE RUN_TIME
USERS=([smoke]=10 [30]=30 [50]=50 [70]=70 [100]=100 [150]=150 [200]=200)
SPAWN_RATE=([smoke]=2 [30]=5 [50]=10 [70]=14 [100]=20 [150]=30 [200]=40)
RUN_TIME=([smoke]="5m" [30]="10m" [50]="15m" [70]="20m" [100]="30m" [150]="40m" [200]="45m")

U=${USERS[$SCENARIO]}
SR=${SPAWN_RATE[$SCENARIO]}
RT=${RUN_TIME[$SCENARIO]}

if [ -z "$U" ]; then
    echo "Unknown scenario '$SCENARIO'. Valid: ${!USERS[*]}"
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT="$REPORT_DIR/${SCENARIO}users_${TIMESTAMP}"
CSV_REPORT="${REPORT}_stats.csv"
HTML_REPORT="${REPORT}_report.html"

echo "========================================"
echo " Scenario:   $SCENARIO ($U users)"
echo " Spawn rate: $SR / sec"
echo " Run time:   $RT"
echo " Host:       $HOST"
echo " Report:     $HTML_REPORT"
echo "========================================"

poetry run locust \
    --host="$HOST" \
    --users="$U" \
    --spawn-rate="$SR" \
    --run-time="$RT" \
    --headless \
    --csv="$REPORT" \
    --html="$HTML_REPORT" \
    --autostart \
    --autoquit 10 \
    -f "$SCRIPT_DIR/locustfile.py"

echo "Done. Reports saved to:"
echo "  CSV:  ${CSV_REPORT}*"
echo "  HTML: $HTML_REPORT"
