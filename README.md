# Rolling 7-Day Weather for Home Assistant

A custom Home Assistant integration and Lovelace card that displays a 7-day icon-only weather strip with a configurable `TODAY` slot position (`1` through `7`), automatically recording past days at midnight.

## Installation via HACS

1. Open **HACS** in Home Assistant.
2. Click the **⋮** menu in the top right and select **Custom repositories**.
3. Paste your GitHub repository URL (`https://github.com/Tholitz1124/ha-rolling-weather`), select **Integration** as the category, and click **Add**.
4. Find **Rolling 7-Day Weather** in HACS and click **Download**.
5. **Restart Home Assistant**.

## Setup

1. Go to **Settings → Devices & Services → + Add Integration**.
2. Search for **Rolling 7-Day Weather**, select your weather entity (e.g., `weather.forecast_home`), and click **Submit**.
3. Hard-refresh your browser (`Ctrl + Shift + R` or `Cmd + Shift + R`).
4. Edit any dashboard, click **+ Add Card**, search for **Rolling 7-Day Weather Card**, and choose your preferred `TODAY` slot position (`1–7`).
