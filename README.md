# 🌡️ hass-daikin-dkn-na - Control your Daikin unit with ease

[![](https://img.shields.io/badge/Download-Latest_Release-blue.svg)](https://github.com/evannc4022/hass-daikin-dkn-na/releases)

This integration connects your Daikin or Airzone DKN Cloud NA air conditioner to Home Assistant. Once connected, you manage your home climate settings directly from your Home Assistant dashboard. You gain the ability to adjust temperatures, change fan speeds, and set schedules without using the original manufacturer app.

## 📋 Requirements

Before you begin, ensure your system meets these needs:

*   A Windows PC running Home Assistant.
*   Your Daikin or Airzone DKN hardware is installed and visible in the DKN Cloud North America mobile app.
*   The DKN Cloud account credentials you use to log into the mobile app.
*   A stable home Wi-Fi connection for both your air conditioner and your Home Assistant server.
*   The HACS (Home Assistant Community Store) platform installed within your Home Assistant instance.

## 💾 Installation Steps

You perform the installation through the HACS interface. Follow these steps to prepare your software.

1.  Visit the official release page to download the latest files. [Download here](https://github.com/evannc4022/hass-daikin-dkn-na/releases).
2.  Open your Home Assistant dashboard in a web browser.
3.  Select the HACS icon from the left sidebar.
4.  Click the three dots located in the top right corner.
5.  Select Custom Repositories.
6.  Paste this repository URL into the text field: `https://github.com/evannc4022/hass-daikin-dkn-na`.
7.  Select Integration from the category dropdown menu.
8.  Click Add.
9.  Find the new entry in your HACS list and click Download.
10. Restart your Home Assistant server to finalize the process. Navigate to Settings, then System, then Power, and click Restart.

## ⚙️ Configuration

After you restart your system, you must authenticate the integration with your cloud account.

1.  Navigate to Settings in the Home Assistant menu.
2.  Select Devices and Services.
3.  Click the Add Integration button in the bottom right corner.
4.  Type Daikin DKN into the search box and select it from the list.
5.  Enter your DKN Cloud North America username and password when the window appears.
6.  Click Submit.
7.  The system identifies your connected air conditioner units automatically. 
8.  Assign each unit to a specific room or area in your home when prompted.
9.  Click Finish to complete the setup.

## 🛠️ Frequently Asked Questions

**Will this replace my remote control?**
This software provides a digital interface. You still use your physical remote for manual adjustments if you prefer. Both methods function simultaneously.

**What happens if my internet goes down?**
The integration relies on the DKN Cloud service. If your internet connection stops, you cannot control your unit through Home Assistant. You must use the physical remote until your internet service returns.

**How do I update the software?**
When a new version becomes available, HACS notifies you with an update icon. Select the update button within the HACS menu to apply the fixes or features automatically. Always restart your system after an update.

**Can I control multiple units?**
Yes. If your DKN Cloud account manages multiple zones or units, this integration detects every unit linked to that account.

**Is my data secure?**
The integration uses your credentials only to establish a link to your cloud account. It does not store your password in plain text. Your control remains local to your Home Assistant server after the initial handshake.

## 💡 Troubleshooting

If you encounter issues during installation or operation, review these common fixes:

*   Verify your login credentials. Use the same details that work in the DKN Cloud North America app.
*   Check your Wi-Fi signal. If the unit struggles to communicate with the cloud, the integration shows as unavailable in Home Assistant.
*   Ensure your HACS installation is current. Outdated versions of HACS cause errors during the repository addition process.
*   Delete the integration and try the configuration again if the system fails to discover your hardware.
*   Consult the logs in Settings, System, and Logs to view specific error messages if the integration does not load.

## 🚀 Usage Tips

Once your units appear on your dashboard, you utilize Home Assistant features to automate your comfort.

*   Create climate schedules using the Home Assistant Automation tab. You trigger changes based on the time of day or your arrival at home.
*   Group your units into an Area to control multiple rooms with one click.
*   Use voice assistants if your Home Assistant instance connects to Alexa or Google Home.
*   Monitor your temperature history through the History tab to track usage patterns.