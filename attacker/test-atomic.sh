#!/bin/bash
# Quick test script to verify Atomic Red Team works
# Run this after SSH'ing into the attacker machine

echo "Testing Atomic Red Team installation..."
echo "========================================"

# Test PowerShell
echo "1. Checking PowerShell..."
pwsh --version

# Test Atomic Red Team
echo ""
echo "2. Testing Atomic Red Team module..."
pwsh -Command "Import-Module invoke-atomicredteam; Write-Host 'Module loaded successfully!'"

# Show a sample test
echo ""
echo "3. Showing sample test details..."
pwsh -Command "Import-Module invoke-atomicredteam; Invoke-AtomicTest T1003.001 -ShowDetails"

echo ""
echo "========================================"
echo "If you see test details above, Atomic Red Team is working!"