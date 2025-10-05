Virgin Modem Status (Home Assistant)

Unofficial custom integration for Home Assistant that polls a Virgin Media modem at http://192.168.100.1/getRouterStatus and exposes simple entities you can use in dashboards and automations (e.g., WAN auto-heal/escalation).

Features

One efficient HTTP poll via a DataUpdateCoordinator

Binary sensor for overall DOCSIS health

Sensor with the latest DOCSIS event and full raw message attributes

Works entirely locally (no cloud)

Installation
Manual (custom_components)

Copy custom_components/virgin_modem_status/ into your Home Assistant config/custom_components/ folder.

Restart Home Assistant.

In HA: Settings → Devices & Services → Add Integration → search “Virgin Modem Status”.

HACS (optional)

Add this repository to HACS as a custom repository, then install and restart HA.

Add the integration from Devices & Services.

Configuration

The config flow asks for:

Host (default: 192.168.100.1)

Options (via Configure on the integration):

Scan interval in seconds (default: 90)

No credentials are required for the status endpoint.

Entities
Entity	Type	Description
binary_sensor.docsis_healthy	Binary Sensor	on when last DOCSIS event does not indicate a fault (partial service, T3/T4, loss of sync, etc.).
sensor.last_docsis_event	Sensor	The last DOCSIS event text. Attributes include maps of recent event times and messages.

Names may be prefixed with your device name in HA. Unique IDs are stable per config entry.

Example: Use in an Auto-Heal Automation
# Example condition for modem cycle vs WAN renew
- choose:
    - conditions:
        - condition: state
          entity_id: binary_sensor.virgin_modem_docsis_healthy
          state: "off"     # modem reporting trouble
      sequence:
        - service: switch.turn_off
          target: { entity_id: switch.virgin_modem_plug }
        - delay: "00:00:20"
        - service: switch.turn_on
          target: { entity_id: switch.virgin_modem_plug }
  default:
    - service: shell_command.opnsense_wan_renew


You can also include the last event text in logs/notifications:

{{ states('sensor.virgin_modem_last_docsis_event') }}

Troubleshooting

Cannot connect / Unknown: Make sure you can open http://192.168.100.1/getRouterStatus from the HA host’s network. Some ISPs/models expose the page only from the WAN/LAN side directly connected to the modem.

No entities: Check Settings → System → Logs for errors from custom_components.virgin_modem_status.

Frequent “unavailable”: Increase the Scan interval in Options (e.g., to 150–180 seconds).

Privacy

All requests are made locally to your modem IP. No data leaves your network.

Disclaimer

This is an unofficial integration, provided as-is. Virgin Media may change or remove the getRouterStatus endpoint without notice.

License

MIT