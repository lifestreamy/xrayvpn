#!/usr/bin/env bash
set -euo pipefail

VERSION="v2026-09-04" # YYYY-MM-DD
LICENSE="AGPL-3.0 + commercial-use restriction"
AUTHOR="Tim Korelov"
CONTACT_URL="https://korelov.dev"

show_banner() {
    echo "=== Xray VPN Provisioning Script (Clash Verge, FlClash, Amnezia) (${VERSION}) ==="
    echo "Author: ${AUTHOR}  |  ${CONTACT_URL}"
    echo "License: ${LICENSE}"
    echo "Tip: Run '$(basename "$0") --help' to see the project description, all options, and examples."
    echo
}

show_help() {
    cat << 'EOF'
provision-vpn.sh - Provision and configure an Xray VLESS + REALITY VPN server via Ansible.

Usage:
  provision-vpn.sh [OPTIONS]

This script:
  - Sets up a temporary workspace with your Ansible project.
  - Ensures required packages (python3, python3-venv, ansible, sshpass) are installed.
  - Runs the Ansible playbook (deploy.yml) against the target VPS.
  - Copies generated client configs from /root/vpn-configs on the VPS into a local
    downloaded-clients directory (or the directory you pass via --clients-dir).

Parameter modes:
  --use-inventory
      Use values from `inventory.yml` in the project root instead of CLI parameters.
      Validates that the inventory file has all required fields.
      Ignores any CLI connection/auth parameters provided.
      If `inventory.yml` does not exist, create it:
        cp inventory.yml.example inventory.yml
      and fill in ansible_host, ansible_user, ansible_port and ONE auth method
      (ansible_ssh_private_key_file or ansible_ssh_pass).
  -I, --inventory PATH
      Same as --use-inventory but with an explicit inventory file path
      (anywhere on disk). Overrides --use-inventory's default location.
  (Default) CLI mode
       parameters required via flags.
      No inventory.yml is needed: the working inventory is generated from
      CLI parameters and never touches your personal inventory.yml.

Connection options (CLI mode):
  -H, --host VALUE     VPS IP / hostname (required in CLI mode).
  -u, --user VALUE     SSH user (default: root).
  -p, --port VALUE     SSH port (default: 22).

Authentication options (CLI mode):
  --pkey PATH          Path to SSH private key for key-based auth.
  --pass PASSWORD      SSH password for password-based auth (plain text).
      If neither --pkey nor --pass is provided, you will be interactively
      prompted for a hidden SSH password.
      --pkey and --pass are mutually exclusive.

Client config output:
  --clients-dir PATH   Directory to store generated client configs.
                       If omitted, a 'downloaded-clients' directory is created next to this script.

Ansible verbosity options:
  --debug              Enable Ansible -vvv and pass xray_debug=true into the playbook.
  --verbose            Enable Ansible -vvvv and pass xray_debug=true into the playbook.
      These options are mutually exclusive. If both are provided, the script fails.

Cleanup options:
  --cleanup            (Default). Remove only the temporary workspace after run.
  --full-cleanup       Remove temporary workspace AND any packages installed by this script.
  --no-cleanup         Keep the temporary workspace for debugging/inspection.

Rotation options:
  --rotate             Regenerate the REALITY identity (xray_reality_rotate=true);
                       the old state is backed up on the server before rotation.
  --no-rotate          Explicitly keep the existing REALITY identity (default behavior).

Deployment options (override config/settings.yml):
  --runtime VALUE      xray_runtime: native | docker.
  --warp               Force-enable the Cloudflare WARP outbound (warp_enabled=true).
  --no-warp            Force-disable the Cloudflare WARP outbound (warp_enabled=false).
  --xray-port VALUE    VLESS inbound TCP port (default: 443).
  --num-clients VALUE  Number of client configs to generate.
  --camouflage-domain VALUE  REALITY SNI camouflage domain.

Other:
  -h, --help           Show this help message and exit.
  --dry-run            Simulate actions without changing the system.
                       Shows what would be done but does not install packages,
                       run Ansible, or remove anything.

Examples:
  # CLI mode (default)
  provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa
  provision-vpn.sh -H vps.example.com -u root --pass secret --clients-dir /tmp/vpn-clients
  provision-vpn.sh -H 1.2.3.4 -u root  # (prompts for SSH password interactively)
  provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa --no-cleanup

  # Debug levels
  provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa --debug
  provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa --verbose

  # All options
  provision-vpn.sh -H 192.168.1.100 -u admin -p 2222 --pkey ~/.ssh/vps_key \
    --clients-dir ~/vpn-configs --full-cleanup --dry-run --verbose
  provision-vpn.sh -H 1.2.3.4 --pkey ~/.ssh/id_rsa \
    --runtime docker --no-warp --xray-port 8443 --num-clients 5 --camouflage-domain www.lovelive.anime.moe

  # Inventory mode
  provision-vpn.sh --use-inventory --full-cleanup --clients-dir ~/vpn-configs
  provision-vpn.sh --inventory ~/secrets/vps-inventory.yml   # same, explicit file
EOF
}

# Extract value from an inventory file (keys are indented under all.hosts.<host>)
get_inventory_value() {
    local key="$1"
    local file="${2:-$INVENTORY_FILE}"
    { grep -E "^[[:space:]]*${key}[[:space:]]*:" "$file" 2>/dev/null || true; } | head -1 | sed "s/.*${key}[[:space:]]*:[[:space:]]*//" | tr -d '\r\n' | xargs
}

# Validate the inventory file has all required fields
validate_inventory() {
    local inv_host=$(get_inventory_value "ansible_host")
    local inv_user=$(get_inventory_value "ansible_user")
    local inv_port=$(get_inventory_value "ansible_port")
    local inv_key=$(get_inventory_value "ansible_ssh_private_key_file")
    local inv_pass=$(get_inventory_value "ansible_ssh_pass")

    local missing=()

    [[ -z "$inv_host" ]] && missing+=("ansible_host")
    [[ -z "$inv_user" ]] && missing+=("ansible_user")
    [[ -z "$inv_port" ]] && missing+=("ansible_port")
    [[ -z "$inv_key" && -z "$inv_pass" ]] && missing+=("auth (ansible_ssh_private_key_file or ansible_ssh_pass)")

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Error: $INVENTORY_FILE is missing required fields:" >&2
        for field in "${missing[@]}"; do
            echo "  - $field" >&2
        done
        echo "Fill them under all.hosts.<host> as in the template:" >&2
        echo "  $REPO_ROOT/inventory.yml.example" >&2
        echo "Or pass another inventory file: --inventory PATH" >&2
        return 1
    fi

    if [[ ! "$inv_port" =~ ^[0-9]+$ ]]; then
        echo "Error: $INVENTORY_FILE has non-numeric ansible_port: '"$inv_port"'" >&2
        echo "Expected an integer, e.g. 22" >&2
        return 1
    fi

    if [[ -n "$inv_key" && -n "$inv_pass" ]]; then
        echo "Error: $INVENTORY_FILE defines both a private key and a password." >&2
        echo "Leave only one (ansible_ssh_private_key_file OR ansible_ssh_pass)." >&2
        return 1
    fi

    return 0
}

# Emit the error for a missing inventory file (with OS-neutral + cp hints)
missing_inventory_message() {
    echo "Error: inventory file not found: $INVENTORY_FILE" >&2
    echo "Create it from the template and fill in your values:" >&2
    echo "  cp \"$REPO_ROOT/inventory.yml.example\" \"$REPO_ROOT/inventory.yml\"" >&2
    echo "or point to your own file: --inventory PATH" >&2
}

# YAML-quote a value for the generated inventory (escape backslash and dquote)
yaml_quote() {
    local raw="$1"
    local esc="${raw//\\/\\\\}"
    esc="${esc//\"/\\\"}"
    printf '"%s"' "$esc"
}

CLEANUP_MODE="cleanup"
DRY_RUN=0
USE_INVENTORY=0
INVENTORY_FILE=""
CLI_CONN_FLAG=0
ANSIBLE_VERBOSE_LEVEL=0
ANSIBLE_VERBOSITY_LABEL="default"
Xray_DEBUG=0
ROTATE=""
RUNTIME=""
WARP=""
XRAY_PORT_VALUE=""
NUM_CLIENTS=""
CAMOUFLAGE=""

CLIENTS_DIR=""
HOST=""
USER_NAME="root"
PORT="22"
PKEY=""
PASS=""
PROVISION_FAILED=0

show_banner

while [[ $# -gt 0 ]]; do
    case $1 in
        --cleanup)
            CLEANUP_MODE="cleanup"
            shift
            ;;
        --full-cleanup)
            CLEANUP_MODE="full-cleanup"
            shift
            ;;
        --no-cleanup)
            CLEANUP_MODE="no-cleanup"
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --use-inventory)
            USE_INVENTORY=1
            shift
            ;;
        -I|--inventory)
            USE_INVENTORY=1
            INVENTORY_FILE="$2"
            shift 2
            ;;
        --debug)
            if [[ "$ANSIBLE_VERBOSE_LEVEL" -ne 0 ]]; then
                echo "Error: --debug and --verbose are mutually exclusive; use only one." >&2
                exit 1
            fi
            ANSIBLE_VERBOSE_LEVEL=3
            ANSIBLE_VERBOSITY_LABEL="debug"
            Xray_DEBUG=1
            shift
            ;;
        --verbose)
            if [[ "$ANSIBLE_VERBOSE_LEVEL" -ne 0 ]]; then
                echo "Error: --debug and --verbose are mutually exclusive; use only one." >&2
                exit 1
            fi
            ANSIBLE_VERBOSE_LEVEL=4
            ANSIBLE_VERBOSITY_LABEL="verbose"
            Xray_DEBUG=1
            shift
            ;;
        --rotate)
            ROTATE="true"
            shift
            ;;
        --no-rotate)
            ROTATE="false"
            shift
            ;;
        --runtime)
            RUNTIME="$2"
            if [[ "$RUNTIME" != native && "$RUNTIME" != docker ]]; then
                echo "Error: --runtime must be 'native' or 'docker'." >&2
                exit 1
            fi
            shift 2
            ;;
        --warp)
            WARP="true"
            shift
            ;;
        --no-warp)
            WARP="false"
            shift
            ;;
        --xray-port)
            XRAY_PORT_VALUE="$2"
            if ! [[ "$XRAY_PORT_VALUE" =~ ^[0-9]+$ ]]; then
                echo "Error: --xray-port expects a TCP port number." >&2
                exit 1
            fi
            shift 2
            ;;
        --num-clients)
            NUM_CLIENTS="$2"
            if ! [[ "$NUM_CLIENTS" =~ ^[1-9][0-9]*$ ]]; then
                echo "Error: --num-clients expects a positive integer." >&2
                exit 1
            fi
            shift 2
            ;;
        --camouflage-domain)
            CAMOUFLAGE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -H|--host)
            HOST="$2"
            CLI_CONN_FLAG=1
            shift 2
            ;;
        -u|--user)
            USER_NAME="$2"
            CLI_CONN_FLAG=1
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            CLI_CONN_FLAG=1
            shift 2
            ;;
        --pkey)
            PKEY="$2"
            CLI_CONN_FLAG=1
            shift 2
            ;;
        --pass)
            PASS="$2"
            CLI_CONN_FLAG=1
            shift 2
            ;;
        --clients-dir)
            CLIENTS_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown flag: $1" >&2
            echo "Use '--help' to see available options."
            exit 1
            ;;
    esac
done

echo "Cleanup mode: $CLEANUP_MODE"
if [[ "$ANSIBLE_VERBOSE_LEVEL" -ne 0 ]]; then
    echo "Ansible verbosity level: $ANSIBLE_VERBOSITY_LABEL"
    echo "Xray debug fact enabled: $Xray_DEBUG"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ "$USE_INVENTORY" -eq 1 ]]; then
    : "${INVENTORY_FILE:=$REPO_ROOT/inventory.yml}"
    echo "Mode: Using inventory file for parameters: $INVENTORY_FILE"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] Would check that $INVENTORY_FILE exists and has all required fields"
    else
        if [[ ! -f "$INVENTORY_FILE" ]]; then
            missing_inventory_message
            exit 1
        fi
        INVENTORY_FILE="$(realpath "$INVENTORY_FILE")"
        if ! validate_inventory; then
            exit 1
        fi
        echo "[OK] Inventory validation passed (all fields present, pkey and pass are mutually exclusive)"
    fi

    if [[ "$CLI_CONN_FLAG" -eq 1 ]]; then
        echo "Warning: inventory mode; ignoring CLI connection/auth parameters" >&2
    fi
    HOST=""
    PKEY=""
    PASS=""
    PORT=""
    USER_NAME=""

    HOST=$(get_inventory_value "ansible_host")
    PKEY=$(get_inventory_value "ansible_ssh_private_key_file")
    PASS=$(get_inventory_value "ansible_ssh_pass")
    PORT=$(get_inventory_value "ansible_port")
    USER_NAME=$(get_inventory_value "ansible_user")

    echo "[DEBUG] After extraction:"
    echo "HOST=[$HOST]"
    echo "PORT=[$PORT]"
    echo "USER_NAME=[$USER_NAME]"
    echo "PKEY=[$PKEY]"
    echo "PASS=[$(printf '%*s' ${#PASS} | tr ' ' '*')]"
else
    echo "Mode: Using CLI parameters"

    if [[ -z "$HOST" ]]; then
        echo "Error: --host is required in CLI mode." >&2
        echo "Use '--help' to see usage or --use-inventory to use inventory.yml."
        exit 1
    fi

    if [[ -n "$PKEY" && -n "$PASS" ]]; then
        echo "Error: --pkey and --pass are mutually exclusive; use only one." >&2
        exit 1
    fi

    if [[ -z "$PKEY" && -z "$PASS" ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo "[dry-run] No --pkey or --pass provided. In a real run, you would be prompted for a hidden SSH password."
        else
            read -s -p "SSH password: " PASS
            echo
        fi
    fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    WORK_DIR="/tmp/provision-vpn-DRYRUN"
    echo "[dry-run] Would create workspace under: $WORK_DIR"
else
    WORK_DIR="$(mktemp -d)"
    echo "Workspace: $WORK_DIR"
fi

MARKER="$WORK_DIR/.installed_by_provision"
if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would create marker file: $MARKER"
else
    touch "$MARKER"
fi

install_if_missing() {
    local pkg="$1"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] Would check and possibly install package: $pkg"
        return
    fi

    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        echo "Installing $pkg..."
        sudo apt-get update -y
        sudo apt-get install -y "$pkg"
        echo "$pkg" >> "$MARKER"
    else
        echo "$pkg already present, not recording for removal."
    fi
}

echo "Checking prerequisites..."
install_if_missing "python3"
install_if_missing "python3-venv"
install_if_missing "ansible"
install_if_missing "sshpass"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would rsync project from: $REPO_ROOT/ to: $WORK_DIR/"
    echo "[dry-run] Would change directory to: $WORK_DIR"
else
    rsync -a \
        --exclude='.venv/' \
        --exclude='.ansible/' \
        --exclude='__pycache__/' \
        --exclude='.git/' \
        --exclude='downloaded-configs/' \
        --exclude='.llm_context/' \
        --exclude='.kilo/' \
        "$REPO_ROOT/" "$WORK_DIR/"

    cd "$WORK_DIR"
fi

if [[ "$USE_INVENTORY" -eq 1 ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] Would use $INVENTORY_FILE as-is (no modifications or backup)"
    else
        echo "Using existing inventory values from: $INVENTORY_FILE"
    fi
else
    CLI_INVENTORY="$WORK_DIR/inventory.yml"
    EXTRA_IGNORED=""
    if [[ -f "$REPO_ROOT/inventory.yml" ]]; then
        EXTRA_IGNORED=$( { grep -E '^[[:space:]]*[A-Za-z0-9_]+:[[:space:]]*[^[:space:]]' "$REPO_ROOT/inventory.yml" || true; } | { grep -Ev '^[[:space:]]*(ansible_host|ansible_user|ansible_port|ansible_ssh_private_key_file|ansible_ssh_pass):' || true; } | sed 's/^[[:space:]]*//; s/:.*//' | sort -u | tr '\n' ' ')
    fi
    if [[ -n "$EXTRA_IGNORED" ]]; then
        echo "Warning: CLI mode ignores non-connection keys in your inventory.yml: ${EXTRA_IGNORED}" >&2
        echo "         Put them in config/settings.yml or run with --use-inventory instead." >&2
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "[dry-run] Preparing to run Ansible with provided parameters..."
        echo "[dry-run] Would generate working inventory at: $CLI_INVENTORY"
        echo "          ansible_host: $HOST"
        echo "          ansible_user: $USER_NAME"
        echo "          ansible_port: $PORT"
        [[ -n "$PKEY" ]] && echo "          ansible_ssh_private_key_file: $PKEY" || true
        [[ -n "$PASS" ]] && echo "          ansible_ssh_pass: (hidden)" || true
    else
        echo "Preparing to run Ansible with provided parameters..."
        if [[ -n "$PKEY" ]]; then
            SAFE_PKEY="$WORK_DIR/safe_private_key"
            cp "$PKEY" "$SAFE_PKEY"
            chmod 600 "$SAFE_PKEY"
            PKEY="$SAFE_PKEY"
        fi
        {
            echo "all:"
            echo "  hosts:"
            echo "    vpn:"
            echo "      ansible_host: $(yaml_quote "$HOST")"
            echo "      ansible_user: $(yaml_quote "$USER_NAME")"
            echo "      ansible_port: $(yaml_quote "$PORT")"
            if [[ -n "$PKEY" ]]; then
                echo "      ansible_ssh_private_key_file: $(yaml_quote "$PKEY")"
            elif [[ -n "$PASS" ]]; then
                echo "      ansible_ssh_pass: $(yaml_quote "$PASS")"
            fi
        } > "$CLI_INVENTORY"
        chmod 600 "$CLI_INVENTORY"
        echo "Generated working inventory: $CLI_INVENTORY (personal inventory.yml untouched)"
    fi
fi

export ANSIBLE_HOST_KEY_CHECKING=False

ANSIBLE_CMD=(ansible-playbook)
if [[ "$ANSIBLE_VERBOSE_LEVEL" -eq 3 ]]; then
    ANSIBLE_CMD+=(-vvv)
elif [[ "$ANSIBLE_VERBOSE_LEVEL" -eq 4 ]]; then
    ANSIBLE_CMD+=(-vvvv)
fi
if [[ "$Xray_DEBUG" -eq 1 ]]; then
    ANSIBLE_CMD+=(-e "xray_debug=true")
fi
if [[ -n "$ROTATE" ]]; then
    ANSIBLE_CMD+=(-e "xray_reality_rotate=$ROTATE")
fi
if [[ -n "$RUNTIME" ]]; then
    ANSIBLE_CMD+=(-e "xray_runtime=$RUNTIME")
fi
# Boolean goes as JSON: the string "false" would be truthy in the config template.
if [[ -n "$WARP" ]]; then
    ANSIBLE_CMD+=(-e "{\"warp_enabled\": $WARP}")
fi
if [[ -n "$XRAY_PORT_VALUE" ]]; then
    ANSIBLE_CMD+=(-e "xray_port=$XRAY_PORT_VALUE")
fi
if [[ -n "$NUM_CLIENTS" ]]; then
    ANSIBLE_CMD+=(-e "num_clients=$NUM_CLIENTS")
fi
if [[ -n "$CAMOUFLAGE" ]]; then
    ANSIBLE_CMD+=(-e "reality_camouflage_domain=$CAMOUFLAGE")
fi
if [[ "$USE_INVENTORY" -eq 1 ]]; then
    ANSIBLE_CMD+=(-i "$INVENTORY_FILE" deploy.yml)
else
    ANSIBLE_CMD+=(-i "$WORK_DIR/inventory.yml" deploy.yml)
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would run: ${ANSIBLE_CMD[*]}"
else
    set +e
    "${ANSIBLE_CMD[@]}"
    ANSIBLE_RC=$?
    set -e

    if [[ $ANSIBLE_RC -ne 0 ]]; then
        echo "Error: Ansible playbook failed!" >&2
        PROVISION_FAILED=1
    else
        PROVISION_FAILED=0
    fi
fi

if [[ -n "$CLIENTS_DIR" ]]; then
    TARGET_DIR="$CLIENTS_DIR"
else
    TARGET_DIR="$REPO_ROOT/downloaded-clients"
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Would create target directory: $TARGET_DIR"
    echo "[dry-run] Would fetch /root/vpn-configs/*.{json,yaml} from VPS via scp"
else
    mkdir -p "$TARGET_DIR"

    if [[ "${PROVISION_FAILED:-0}" -eq 0 ]]; then
        echo "Fetching client configs from VPS..."

        fetch_success=0

        if [[ -n "$PKEY" ]]; then
            set +e
            scp -i "$PKEY" -P "$PORT" -o StrictHostKeyChecking=no \
                "$USER_NAME@$HOST:/root/vpn-configs/*.json" "$TARGET_DIR/" 2>/dev/null
            json_rc=$?
            scp -i "$PKEY" -P "$PORT" -o StrictHostKeyChecking=no \
                "$USER_NAME@$HOST:/root/vpn-configs/*.yaml" "$TARGET_DIR/" 2>/dev/null
            yaml_rc=$?
            set -e
        elif [[ -n "$PASS" ]]; then
            export SSHPASS="$PASS"
            set +e
            sshpass -e scp -P "$PORT" -o StrictHostKeyChecking=no \
                "$USER_NAME@$HOST:/root/vpn-configs/*.json" "$TARGET_DIR/" 2>/dev/null
            json_rc=$?
            sshpass -e scp -P "$PORT" -o StrictHostKeyChecking=no \
                "$USER_NAME@$HOST:/root/vpn-configs/*.yaml" "$TARGET_DIR/" 2>/dev/null
            yaml_rc=$?
            set -e
            unset SSHPASS
        fi

        [[ "$json_rc" == "0" ]] && { echo "  [JSON] downloaded successfully"; fetch_success=1; }
        [[ "$yaml_rc" == "0" ]] && { echo "  [YAML] downloaded successfully"; fetch_success=1; }

        if [[ "$fetch_success" == "1" ]]; then
            echo "Client configs saved to: $TARGET_DIR"
        else
            echo "Warning: no client configs were downloaded. Check VPS connection or auth."
        fi
    fi
fi

case "$CLEANUP_MODE" in
    cleanup)
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo "[dry-run] Would remove temp workspace: $WORK_DIR"
        else
            echo "Cleanup: removing temp workspace..."
            rm -rf "$WORK_DIR"
        fi
        ;;
    full-cleanup)
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo "[dry-run] Would remove temp workspace and any packages listed in: $MARKER"
        else
            echo "Full cleanup: removing temp workspace and packages we installed..."
            if [[ -s "$MARKER" ]]; then
                mapfile -t pkgs < <(sort -u "$MARKER")
                echo "Removing packages: ${pkgs[*]}"
                sudo apt-get remove -y "${pkgs[@]}" || true
                sudo apt-get autoremove -y || true
            else
                echo "No packages recorded as installed by script; nothing to remove."
            fi
            echo "Cleanup: removing temp workspace..."
            rm -rf "$WORK_DIR"
        fi
        ;;
    no-cleanup)
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo "[dry-run] Would leave workspace at: $WORK_DIR"
        else
            echo "No cleanup: workspace left at $WORK_DIR"
        fi
        ;;
esac

if [[ "${PROVISION_FAILED:-0}" -eq 1 ]]; then
    echo "Provisioning script FAILED." >&2
    exit 1
elif [[ "$DRY_RUN" -eq 1 ]]; then
    echo "[dry-run] Done (no changes applied)."
else
    echo "Provisioning script completed successfully."
fi