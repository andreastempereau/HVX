#!/bin/bash
# Fix keyboard input permissions for Qt application

echo "Adding user to 'input' group for keyboard access..."
sudo usermod -a -G input $USER

echo ""
echo "========================================="
echo "User added to 'input' group successfully!"
echo "========================================="
echo ""
echo "IMPORTANT: You must REBOOT for this change to take effect."
echo ""
echo "After reboot, the P key will work in the visor UI."
echo ""
echo "To reboot now, run: sudo reboot"
echo ""
