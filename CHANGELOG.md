# Changelog

All notable changes to this project are documented in this file. This project
adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-06-09

Initial release.

### Added
- **Climate entity** per unit: power, HVAC mode (auto / cool / heat / fan / dry),
  current and target temperature, fan speed, and louvre **swing** — vertical and/or
  horizontal depending on what each unit reports.
- **Diagnostic sensors**: outdoor temperature, Wi-Fi signal, outdoor-unit current,
  and air quality (PM1 / PM2.5 / PM10) — added only when the hardware reports them.
- **Binary sensors**: connectivity, problem, and temperature-sensor problem.
- **Live, cloud-push updates** over the DKN Cloud NA service (no polling).
- **UI configuration**: sign in with your DKN Cloud NA account; all installations
  and units are discovered automatically.
- **°F / °C** following each unit's own temperature setting.

[0.1.0]: https://github.com/Suds-Lab/hass-daikin-dkn-na/releases/tag/v0.1.0
