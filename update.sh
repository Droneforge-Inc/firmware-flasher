#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_ROOT="${SCRIPT_DIR}/binaries"

show_help() {
	cat <<EOF
Usage: $(basename "$0") [options] [command]

Sync firmware assets from sibling repos into this repo.

Commands:
  all         Update Betaflight and ELRS assets. This is the default.
  betaflight  Update Betaflight assets only. Use --fc to limit the FC.
  elrs        Update Nimbus and drone ELRS assets.
  nimbus      Update Nimbus ELRS assets only.
  drone       Update drone ELRS assets only.

Defaults:
  Betaflight repo:  $SCRIPT_DIR/../betaflight
  ExpressLRS repo:  $SCRIPT_DIR/../ExpressLRS
  Nimbus build dir: ../ExpressLRS/src/.pio/build/Unified_ESP32S3_2400_TX_via_UART
  Drone build dir:  ../ExpressLRS/src/.pio/build/Unified_ESP8285_2400_RX_via_BetaflightPassthrough

Options:
  -n, --dry-run              Show what would change without writing files
  --fc TYPE                  Betaflight FC filter: betafpv, axis, or all
  --betaflight-dir PATH      Override the sibling Betaflight repo path
  --expresslrs-dir PATH      Override the sibling ExpressLRS repo path
  --nimbus-build-dir PATH    Override the Nimbus ELRS build output directory
  --drone-build-dir PATH     Override the drone ELRS build output directory
  --objcopy PATH             Override the objcopy binary
  -h, --help                 Show this help

Environment overrides:
  BETAFPV_HEX_SOURCE
  AXIS_HEX_SOURCE
  BETAFPV_CONFIG_SOURCE
  AXIS_CONFIG_SOURCE
  NIMBUS_BOOTLOADER_SOURCE
  NIMBUS_PARTITIONS_SOURCE
  NIMBUS_BOOT_APP0_SOURCE
  NIMBUS_FIRMWARE_SOURCE
  DRONE_FIRMWARE_SOURCE
  OBJCOPY

Examples:
  $(basename "$0")
  $(basename "$0") all
  $(basename "$0") --dry-run
  $(basename "$0") betaflight --fc betafpv
  $(basename "$0") betaflight --fc axis
  $(basename "$0") elrs
EOF
}

DRY_RUN=0
declare -a COMPONENTS=()
FC_TYPE="${FC_TYPE:-all}"

BETAFLIGHT_DIR="${BETAFLIGHT_DIR:-}"
EXPRESSLRS_DIR="${EXPRESSLRS_DIR:-}"
NIMBUS_BUILD_DIR="${NIMBUS_BUILD_DIR:-}"
DRONE_BUILD_DIR="${DRONE_BUILD_DIR:-}"
OBJCOPY="${OBJCOPY:-arm-none-eabi-objcopy}"

while [[ $# -gt 0 ]]; do
	case "$1" in
		-n|--dry-run)
			DRY_RUN=1
			shift
			;;
		--fc)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			FC_TYPE="$2"
			shift 2
			;;
		--betaflight-dir)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			BETAFLIGHT_DIR="$2"
			shift 2
			;;
		--expresslrs-dir)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			EXPRESSLRS_DIR="$2"
			shift 2
			;;
		--nimbus-build-dir)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			NIMBUS_BUILD_DIR="$2"
			shift 2
			;;
		--drone-build-dir)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			DRONE_BUILD_DIR="$2"
			shift 2
			;;
		--objcopy)
			[[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 1; }
			OBJCOPY="$2"
			shift 2
			;;
		-h|--help)
			show_help
			exit 0
			;;
		all|betaflight|elrs|nimbus|drone)
			COMPONENTS+=("$1")
			shift
			;;
		*)
			echo "Unknown argument: $1" >&2
			echo "Run with --help for usage." >&2
			exit 1
			;;
	esac
done

case "$FC_TYPE" in
	betafpv|axis|all)
		;;
	*)
		echo "Invalid --fc value: $FC_TYPE" >&2
		echo "Expected betafpv, axis, or all." >&2
		exit 1
		;;
esac

BETAFLIGHT_DIR="${BETAFLIGHT_DIR:-$SCRIPT_DIR/../betaflight}"
EXPRESSLRS_DIR="${EXPRESSLRS_DIR:-$SCRIPT_DIR/../ExpressLRS}"
NIMBUS_BUILD_DIR="${NIMBUS_BUILD_DIR:-$EXPRESSLRS_DIR/src/.pio/build/Unified_ESP32S3_2400_TX_via_UART}"
DRONE_BUILD_DIR="${DRONE_BUILD_DIR:-$EXPRESSLRS_DIR/src/.pio/build/Unified_ESP8285_2400_RX_via_BetaflightPassthrough}"

# The Betaflight .bin names here are derived from the .hex files referenced by
# ../betaflight/utils/scripts/flash_and_config.sh.
BETAFPV_HEX_SOURCE="${BETAFPV_HEX_SOURCE:-$BETAFLIGHT_DIR/obj/betaflight_4.5.2_STM32G47X_BETAFPVG473.hex}"
AXIS_HEX_SOURCE="${AXIS_HEX_SOURCE:-$BETAFLIGHT_DIR/obj/betaflight_4.5.2_STM32F7X2_AXISFLYINGF7AIO.hex}"
BETAFPV_CONFIG_SOURCE="${BETAFPV_CONFIG_SOURCE:-$BETAFLIGHT_DIR/utils/config/whoop-of.txt}"
AXIS_CONFIG_SOURCE="${AXIS_CONFIG_SOURCE:-$BETAFLIGHT_DIR/utils/config/axis-of.txt}"

# Nimbus defaults to the ESP32-S3 TX build documented in ../ExpressLRS/README.md.
NIMBUS_BOOTLOADER_SOURCE="${NIMBUS_BOOTLOADER_SOURCE:-$NIMBUS_BUILD_DIR/bootloader.bin}"
NIMBUS_PARTITIONS_SOURCE="${NIMBUS_PARTITIONS_SOURCE:-$NIMBUS_BUILD_DIR/partitions.bin}"
NIMBUS_BOOT_APP0_SOURCE="${NIMBUS_BOOT_APP0_SOURCE:-$NIMBUS_BUILD_DIR/boot_app0.bin}"
NIMBUS_FIRMWARE_SOURCE="${NIMBUS_FIRMWARE_SOURCE:-$NIMBUS_BUILD_DIR/firmware.bin}"

# Drone flashing only uses a single firmware.bin at address 0x0000, so the
# default source is the ESP8285 Betaflight passthrough build output.
DRONE_FIRMWARE_SOURCE="${DRONE_FIRMWARE_SOURCE:-$DRONE_BUILD_DIR/firmware.bin}"

if [[ ${#COMPONENTS[@]} -eq 0 ]]; then
	COMPONENTS=("all")
fi

INCLUDE_BETAFLIGHT=0
INCLUDE_NIMBUS=0
INCLUDE_DRONE=0

for component in "${COMPONENTS[@]}"; do
	case "$component" in
		all)
			INCLUDE_BETAFLIGHT=1
			INCLUDE_NIMBUS=1
			INCLUDE_DRONE=1
			;;
		betaflight)
			INCLUDE_BETAFLIGHT=1
			;;
		elrs)
			INCLUDE_NIMBUS=1
			INCLUDE_DRONE=1
			;;
		nimbus)
			INCLUDE_NIMBUS=1
			;;
		drone)
			INCLUDE_DRONE=1
			;;
	esac
done

declare -a ASSET_TYPES=()
declare -a ASSET_SOURCES=()
declare -a ASSET_DESTS=()
declare -a ASSET_LABELS=()

add_asset() {
	ASSET_TYPES+=("$1")
	ASSET_SOURCES+=("$2")
	ASSET_DESTS+=("$3")
	ASSET_LABELS+=("$4")
}

if (( INCLUDE_BETAFLIGHT )); then
	if [[ "$FC_TYPE" == "betafpv" || "$FC_TYPE" == "all" ]]; then
		add_asset "hex_to_bin" "$BETAFPV_HEX_SOURCE" "$DEST_ROOT/betaflight/bin/betafpv.bin" "Betaflight BetaFPV firmware"
		add_asset "copy" "$BETAFPV_CONFIG_SOURCE" "$DEST_ROOT/betaflight/config/whoop-of.txt" "Betaflight BetaFPV config"
	fi
	if [[ "$FC_TYPE" == "axis" || "$FC_TYPE" == "all" ]]; then
		add_asset "hex_to_bin" "$AXIS_HEX_SOURCE" "$DEST_ROOT/betaflight/bin/axis.bin" "Betaflight Axis firmware"
		add_asset "copy" "$AXIS_CONFIG_SOURCE" "$DEST_ROOT/betaflight/config/axis-of.txt" "Betaflight Axis config"
	fi
fi

if (( INCLUDE_NIMBUS )); then
	add_asset "copy" "$NIMBUS_BOOTLOADER_SOURCE" "$DEST_ROOT/elrs/nimbus/v1/bootloader.bin" "Nimbus v1 bootloader"
	add_asset "copy" "$NIMBUS_PARTITIONS_SOURCE" "$DEST_ROOT/elrs/nimbus/v1/partitions.bin" "Nimbus v1 partitions"
	add_asset "copy" "$NIMBUS_BOOT_APP0_SOURCE" "$DEST_ROOT/elrs/nimbus/v1/boot_app0.bin" "Nimbus v1 boot app"
	add_asset "copy" "$NIMBUS_FIRMWARE_SOURCE" "$DEST_ROOT/elrs/nimbus/v1/firmware.bin" "Nimbus v1 firmware"
fi

if (( INCLUDE_DRONE )); then
	add_asset "copy" "$DRONE_FIRMWARE_SOURCE" "$DEST_ROOT/elrs/drone/firmware.bin" "Drone ELRS firmware"
fi

if [[ ${#ASSET_TYPES[@]} -eq 0 ]]; then
	echo "No assets selected." >&2
	exit 1
fi

if printf '%s\n' "${ASSET_TYPES[@]}" | grep -qx "hex_to_bin"; then
	if ! command -v "$OBJCOPY" >/dev/null 2>&1; then
		echo "Required tool not found: $OBJCOPY" >&2
		exit 1
	fi
fi

missing=0
for i in "${!ASSET_TYPES[@]}"; do
	if [[ ! -f "${ASSET_SOURCES[$i]}" ]]; then
		echo "Missing source for ${ASSET_LABELS[$i]}:" >&2
		echo "  ${ASSET_SOURCES[$i]}" >&2
		missing=1
	fi
done

if (( missing )); then
	echo "Adjust the source paths with the flags or environment variables listed in --help." >&2
	exit 1
fi

changed_count=0
unchanged_count=0

sync_copy_asset() {
	local source="$1"
	local dest="$2"
	local label="$3"
	local state="create"

	mkdir -p "$(dirname "$dest")"

	if [[ -f "$dest" ]] && cmp -s "$source" "$dest"; then
		printf 'unchanged  %s\n' "$label"
		unchanged_count=$((unchanged_count + 1))
		return
	fi

	if [[ -e "$dest" ]]; then
		state="update"
	fi

	if (( DRY_RUN )); then
		printf 'would %-7s %s\n' "$state" "$label"
	else
		cp "$source" "$dest"
		printf 'updated    %s\n' "$label"
	fi

	changed_count=$((changed_count + 1))
}

sync_hex_asset() {
	local source="$1"
	local dest="$2"
	local label="$3"
	local state="create"
	local tmp_file

	tmp_file="$(mktemp)"
	"$OBJCOPY" -I ihex -O binary "$source" "$tmp_file"
	mkdir -p "$(dirname "$dest")"

	if [[ -f "$dest" ]] && cmp -s "$tmp_file" "$dest"; then
		rm -f "$tmp_file"
		printf 'unchanged  %s\n' "$label"
		unchanged_count=$((unchanged_count + 1))
		return
	fi

	if [[ -e "$dest" ]]; then
		state="update"
	fi

	if (( DRY_RUN )); then
		rm -f "$tmp_file"
		printf 'would %-7s %s\n' "$state" "$label"
	else
		mv "$tmp_file" "$dest"
		printf 'updated    %s\n' "$label"
	fi

	changed_count=$((changed_count + 1))
}

printf 'Syncing assets into %s\n' "$DEST_ROOT"

for i in "${!ASSET_TYPES[@]}"; do
	case "${ASSET_TYPES[$i]}" in
		copy)
			sync_copy_asset "${ASSET_SOURCES[$i]}" "${ASSET_DESTS[$i]}" "${ASSET_LABELS[$i]}"
			;;
		hex_to_bin)
			sync_hex_asset "${ASSET_SOURCES[$i]}" "${ASSET_DESTS[$i]}" "${ASSET_LABELS[$i]}"
			;;
		*)
			echo "Unsupported asset type: ${ASSET_TYPES[$i]}" >&2
			exit 1
			;;
	esac
done

if (( DRY_RUN )); then
	printf 'Dry run complete: %d would change, %d unchanged\n' "$changed_count" "$unchanged_count"
else
	printf 'Done: %d updated, %d unchanged\n' "$changed_count" "$unchanged_count"
fi
