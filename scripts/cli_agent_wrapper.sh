#!/bin/bash
# CLI Agent Launcher
# Cline と ollama code を Ollama ローカルLLMで使用するためのラッパー

set -e

OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
DEFAULT_MODEL="${DEFAULT_MODEL:-qwen3.6-35b-a3b}"

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "Usage: $0 [clinetype] [task]"
    echo ""
    echo "Agents:"
    echo "  cline       - Cline with local Ollama"
    echo "  ollamacode  - ollama code (official CLI agent)"
    echo ""
    echo "Examples:"
    echo "  $0 cline      # Start Cline with Ollama"
    echo "  $0 ollamacode # Start ollama code"
    echo ""
    echo "Environment:"
    echo "  OLLAMA_BASE_URL - Ollama server URL (default: http://localhost:11434)"
    echo "  DEFAULT_MODEL  - Model to use (default: qwen3.6-35b-a3b)"
}

# Ollama接続確認
check_ollama() {
    echo -e "${BLUE}[*] Checking Ollama connection...${NC}"
    
    if ! curl -s "${OLLAMA_BASE_URL}/api/tags" > /dev/null 2>&1; then
        echo -e "${RED}[✗] Ollama is not responding at ${OLLAMA_BASE_URL}${NC}"
        echo -e "${YELLOW}[!] Please start Ollama: ollama serve${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}[✓] Ollama is running${NC}"
    
    # 利用可能モデル表示
    echo -e "${BLUE}[*] Available models:${NC}"
    curl -s "${OLLAMA_BASE_URL}/api/tags" | jq -r '.models[].name' 2>/dev/null || echo "  (jq not available for formatting)"
}

# 利用可能モデル一覧
list_models() {
    echo -e "${BLUE}[*] Installed models:${NC}"
    curl -s "${OLLAMA_BASE_URL}/api/tags" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for m in data.get('models', []):
        print(f\"  - {m.get('name', 'unknown')}\")
except:
    print('  Error parsing models')
" 2>/dev/null || curl -s "${OLLAMA_BASE_URL}/api/tags"
}

# Cline起動
launch_cline() {
    echo -e "${GREEN}[*] Launching Cline with Ollama (${DEFAULT_MODEL})${NC}"
    
    # Claude系API互換なので、OPENAI_BASE_URLとしてollamaを向かせる
    export OPENAI_BASE_URL="${OLLAMA_BASE_URL}/v1"
    export OPENAI_API_KEY="ollama"
    export OPENAI_MODEL="${DEFAULT_MODEL}"
    
    # Anthropic系を使う場合はClineの設定で上書き
    # ClineはAnthropic/OpenAI双方対応
    echo -e "${YELLOW}[!] Configure Cline settings:${NC}"
    echo "  API Provider: OpenAI Compatible"
    echo "  Base URL: ${OLLAMA_BASE_URL}/v1"
    echo "  API Key: ollama"
    echo "  Model: ${DEFAULT_MODEL}"
    
    # Clineを起動（設定は手動）
    echo -e "${GREEN}[*] Opening Cline settings...${NC}"
    
    # Cline設定ファイルを開く
    if command -v cline &> /dev/null; then
        cline
    else
        # VSCode/Cursorが開いていればClineパレットを開く
        echo -e "${YELLOW}[!] Please configure Cline in your editor${NC}"
        echo "  1. Open Command Palette (Cmd+Shift+P)"
        echo "  2. Type 'Cline: Open Settings'"
        echo "  3. Set API Provider to 'OpenAI Compatible'"
        echo "  4. Set Base URL to: ${OLLAMA_BASE_URL}/v1"
        echo "  5. Set API Key to: ollama"
        echo "  6. Set Model to: ${DEFAULT_MODEL}"
    fi
}

# ollama code起動
launch_ollamacode() {
    echo -e "${GREEN}[*] Launching ollama code with model: ${DEFAULT_MODEL}${NC}"
    
    if ! command -v ollama &> /dev/null; then
        echo -e "${RED}[✗] ollama command not found${NC}"
        echo -e "${YELLOW}[!] Install ollama: https://ollama.com/download${NC}"
        exit 1
    fi
    
    # ollama code 플러그인 확인
    if command -v ollama-code &> /dev/null; then
        ollama-code --model "${DEFAULT_MODEL}" "$@"
    else
        echo -e "${YELLOW}[!] ollama code not installed${NC}"
        echo "  Install with: ollama install code"
        echo ""
        echo -e "${BLUE}[*] Checking if ollama run command works as fallback...${NC}"
        
        # ollama codeがない場合、ollama runで直接対話
        echo -e "${GREEN}[*] Starting chat with ${DEFAULT_MODEL}${NC}"
        ollama run "${DEFAULT_MODEL}" "$@"
    fi
}

# メイン
case "${1:-help}" in
    cline|clinetype)
        check_ollama
        list_models
        echo ""
        launch_cline
        ;;
    ollamacode|ollama)
        check_ollama
        list_models
        echo ""
        launch_ollamacode "${@:2}"
        ;;
    list|l)
        check_ollama
        list_models
        ;;
    check|c)
        check_ollama
        ;;
    --help|help|-h)
        usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        usage
        exit 1
        ;;
esac
