#!/bin/bash
# Tailscale VPN setup for Raspberry Pi + iPad access

echo "=== Tailscale VPN Setup ==="

# Install Tailscale
if ! command -v tailscale &> /dev/null; then
    echo "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
else
    echo "✅ Tailscale already installed"
fi

# Start Tailscale
echo ""
echo "Starting Tailscale..."
sudo tailscale up

echo ""
echo "=== Tailscale Setup Instructions ==="
echo ""
echo "1. On Raspberry Pi:"
echo "   - Follow the link above to authenticate"
echo "   - This device will appear in your Tailscale network"
echo ""
echo "2. On iPad:"
echo "   - Install Tailscale from App Store"
echo "   - Sign in with same account"
echo "   - Enable Tailscale VPN"
echo ""
echo "3. Find Raspberry Pi IP:"
echo "   - Run: tailscale ip -4"
echo "   - iPad can SSH/access this IP"
echo ""
echo "4. Enable SSH on iPad apps:"
echo "   - Termius: Use Tailscale IP"
echo "   - Blink Shell: Use Tailscale IP"
echo ""
echo "Current Tailscale status:"
tailscale status

echo ""
echo "Your Tailscale IP:"
tailscale ip -4

echo ""
echo "✅ Tailscale setup complete"
echo ""
echo "Test connection from iPad:"
echo "  ssh yashcs@\$(tailscale ip -4)"
