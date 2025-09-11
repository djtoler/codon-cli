#!/bin/bash

# Script to compile key backend files for SSE streaming implementation
# Run this from your base_agent directory

OUTPUT_FILE="backend_files_compiled.txt"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Array of files to compile
FILES=(
    "api/routes.py"
    "api/wrapper.py"
    "app.py"
    "langgraph/langgraph_executor.py"
    "langgraph/agent_factory.py"
    "agent2agent/a2a_tasks.py"
    "config/agent_config.py"
    "api/auth.py"
    "telemetry/_telemetry.py"
    "telemetry/langgraph_trace_utils.py"
)

# Start the output file
echo "# Backend Files Compilation for SSE Streaming Implementation" > "$OUTPUT_FILE"
echo "# Generated on: $TIMESTAMP" >> "$OUTPUT_FILE"
echo "# Working directory: $(pwd)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Function to add a file to the compilation
add_file() {
    local file_path="$1"
    
    if [ -f "$file_path" ]; then
        echo "Adding $file_path..."
        echo "# ============================================================================" >> "$OUTPUT_FILE"
        echo "# FILE: $file_path" >> "$OUTPUT_FILE"
        echo "# ============================================================================" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        cat "$file_path" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    else
        echo "Warning: File $file_path not found, skipping..."
        echo "# ============================================================================" >> "$OUTPUT_FILE"
        echo "# FILE: $file_path (NOT FOUND)" >> "$OUTPUT_FILE"
        echo "# ============================================================================" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
    fi
}

echo "Compiling backend files for SSE streaming implementation..."
echo "Output file: $OUTPUT_FILE"
echo ""

# Add each file to the compilation
for file in "${FILES[@]}"; do
    add_file "$file"
done

# Add summary at the end
echo "# ============================================================================" >> "$OUTPUT_FILE"
echo "# COMPILATION SUMMARY" >> "$OUTPUT_FILE"
echo "# ============================================================================" >> "$OUTPUT_FILE"
echo "# Total files processed: ${#FILES[@]}" >> "$OUTPUT_FILE"
echo "# Generated on: $TIMESTAMP" >> "$OUTPUT_FILE"
echo "# Working directory: $(pwd)" >> "$OUTPUT_FILE"

echo "Compilation complete!"
echo "Output saved to: $OUTPUT_FILE"
echo ""
echo "You can now share this file for backend SSE streaming implementation help."