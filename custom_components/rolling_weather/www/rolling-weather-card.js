const ICON_MAP = {
  "clear-night": "mdi:weather-night",
  "cloudy": "mdi:weather-cloudy",
  "fog": "mdi:weather-fog",
  "hail": "mdi:weather-hail",
  "lightning": "mdi:weather-lightning",
  "lightning-rainy": "mdi:weather-lightning-rainy",
  "partlycloudy": "mdi:weather-partly-cloudy",
  "pouring": "mdi:weather-pouring",
  "rainy": "mdi:weather-rainy",
  "snowy": "mdi:weather-snowy",
  "snowy-rainy": "mdi:weather-snowy-rainy",
  "sunny": "mdi:weather-sunny",
  "windy": "mdi:weather-windy",
  "windy-variant": "mdi:weather-windy-variant",
  "exceptional": "mdi:alert-circle-outline",
};

const PREVIEW_SAMPLE_ATTRS = {
  day_minus_6: "cloudy",
  day_minus_5: "sunny",
  day_minus_4: "partlycloudy",
  day_minus_3: "rainy",
  day_minus_2: "partlycloudy",
  day_minus_1: "sunny",
  today: "partlycloudy",
  day_plus_1: "sunny",
  day_plus_2: "cloudy",
  day_plus_3: "rainy",
  day_plus_4: "partlycloudy",
  day_plus_5: "sunny",
  day_plus_6: "cloudy",
};

function buildSlotsForTodayIndex(todayIndex) {
  const zeroBased = Math.min(6, Math.max(0, (Number(todayIndex) || 4) - 1));
  return Array.from({ length: 7 }, (_, i) => {
    const offset = i - zeroBased;
    let key = "today";
    if (offset < 0) key = `day_minus_${Math.abs(offset)}`;
    if (offset > 0) key = `day_plus_${offset}`;
    return { key, offset };
  });
}

class RollingWeatherCard extends HTMLElement {
  static getStubConfig(hass) {
    const detected = hass
      ? Object.keys(hass.states).find((eid) =>
          eid.startsWith("sensor.") && eid.includes("rolling_7_day_weather")
        )
      : null;

    return {
      entity: detected || "sensor.rolling_7_day_weather",
      today_index: 4,
    };
  }

  static getConfigForm() {
    return {
      schema: [
        {
          name: "entity",
          required: true,
          selector: { entity: { domain: "sensor" } },
        },
        {
          name: "today_index",
          required: true,
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: 1, label: "Slot 1 — Leftmost (TODAY, +6d)" },
                { value: 2, label: "Slot 2 (-1d, TODAY, +5d)" },
                { value: 3, label: "Slot 3 (-2d, TODAY, +4d)" },
                { value: 4, label: "Slot 4 — Center (-3d, TODAY, +3d)" },
                { value: 5, label: "Slot 5 (-4d, TODAY, +2d)" },
                { value: 6, label: "Slot 6 (-5d, TODAY, +1d)" },
                { value: 7, label: "Slot 7 — Rightmost (-6d, TODAY)" },
              ],
            },
          },
        },
      ],
      computeLabel: (schema) => {
        if (schema.name === "entity") return "Rolling Weather Sensor";
        if (schema.name === "today_index") return "TODAY Slot Position (1–7)";
        return undefined;
      },
    };
  }

  setConfig(config) {
    let index = 4;
    if (config.today_index !== undefined) {
      index = Math.min(7, Math.max(1, Number(config.today_index) || 4));
    } else if (config.today_position === "left") {
      index = 1;
    }

    this.config = {
      entity: config.entity || "sensor.rolling_7_day_weather",
      today_index: index,
    };
    if (this._lastHass) {
      this.hass = this._lastHass;
    }
  }

  set hass(hass) {
    this._lastHass = hass;
    const stateObj = hass?.states?.[this.config.entity];

    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="row"></div>
        </ha-card>
        <style>
          ha-card {
            padding: 12px 6px;
          }
          .row {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            align-items: center;
            justify-items: center;
            gap: 4px;
          }
          .slot {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 8px 2px;
            border-radius: 10px;
            opacity: 0.65;
            color: var(--primary-text-color);
            width: 100%;
            box-sizing: border-box;
          }
          .slot.today {
            opacity: 1;
            background: rgba(var(--rgb-primary-color, 3, 169, 244), 0.16);
            color: var(--primary-color);
          }
          .day-label {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
          }
          .slot.today .day-label {
            font-weight: 700;
          }
          ha-icon {
            --mdc-icon-size: 24px;
          }
          .slot.today ha-icon {
            --mdc-icon-size: 28px;
          }
        </style>
      `;
      this.content = this.querySelector(".row");
    }

    const slots = buildSlotsForTodayIndex(this.config.today_index);
    const attrs = stateObj?.attributes || PREVIEW_SAMPLE_ATTRS;

    this.content.innerHTML = slots.map(({ key, offset }) => {
      const cond = attrs[key];
      const icon = ICON_MAP[cond] || "mdi:help-circle-outline";
      const isToday = key === "today" ? "today" : "";

      let label = "TODAY";
      if (offset !== 0) {
        const d = new Date();
        d.setDate(d.getDate() + offset);
        const raw = d.toLocaleDateString("en-US", { weekday: "short" });
        label = raw.charAt(0).toUpperCase() + raw.slice(1, 3).toLowerCase();
      }

      return `
        <div class="slot ${isToday}" title="${key}: ${cond || "unknown"}">
          <div class="day-label">${label}</div>
          <ha-icon icon="${icon}"></ha-icon>
        </div>
      `;
    }).join("");
  }

  getCardSize() {
    return 1;
  }
}

customElements.define("rolling-weather-card", RollingWeatherCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "rolling-weather-card",
  name: "Rolling 7-Day Weather Card",
  description: "7-day weather icon strip with configurable TODAY slot position (1–7).",
  preview: true,
});