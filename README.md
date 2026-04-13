# homeassistant-experiaboxv10a
ExperiaBox V10A custom device_tracker component for Home-Assistant.io

## Purpose
The purpose of this custom component for [Home-Assistant](https://home-assistant.io) is to track devices that are connected either wired or wirelessly to a Experia Box V10A, including clients connected to the guest network.

## Inspired by
This project was inspired by the nmap device_tracker component and the custom components that allows [Home-Assistant](https://home-assistant.io) to track devices connected to the Experia Box V8 and Experia Box V10:

- [Official Home-Assistant nmap device_tracker](https://www.home-assistant.io/components/nmap_tracker/)
- [Experia V8 device_tracker](https://community.home-assistant.io/t/device-tracker-for-arcadyan-vgv7519-router-experia-box-v8/29362) by [MvdB](https://community.home-assistant.io/u/mvdb)
- [Experia V10 device_tracker](https://github.com/kadima-tech/experia-v10-device-tracker) by [kadima-tech](https://github.com/kadima-tech/)

## Setup instructions
### Copying into custom_components folder
Create a directory `custom_components` in your Home-Assistant configuration directory.
Copy the whole [experiaboxv10a](./experiaboxv10a) folder from this project into the newly created directory `custom_components`.

The result of your copy action(s) should yield a directory structure like so:

```
.homeassistant/
|-- custom_components/
|   |-- experiaboxv10a/
|       |-- __init__.py
|       |-- device_tracker.py
|       |-- manifest.json
```

### Enabling the custom_component
In order to enable this custom device_tracker component, add this code snippet to your Home-Assistant `configuration.yaml` file:

```yaml
device_tracker:
  - platform: experiaboxv10a
    host: mijnmodem.kpn
    username: admin
    password: PASSWORD
```

Please use [secrets](https://www.home-assistant.io/docs/configuration/secrets/) within Home-Assistant to store sensitive data like IPs, usernames and passwords.

## Experia Wifi
This device_tracker queries the Experia Box V10A directly.
If you are using an Experia Wifi access point in conjunction with your Experia Box V10A, the clients connected to the Experia Wifi access point will also be reported by this device_tracker.

## Troubleshooting
**Older firmware (before V10A.C.26):** The original implementation used HTML 
scraping and `GET /cgi/cgi_clients.js`. If you are on an older firmware, 
use version 0.2.1 of this component.

**Newer firmware (V10A.C.26+):** The web interface was replaced with a 
Flutter-based UI using a Sagemcom JSON-RPC API. Version 0.3.0+ of this 
component supports this new API. The router is accessed over plain HTTP 
(no SSL), so the `.pem` certificate file is no longer needed and has been 
removed from the repository.

> **Note:** Credentials are sent in plaintext over HTTP. This is only safe 
> on your local network, which is the intended use case.

If the component fails to authenticate, check your username and password in the router web interface at http://<router_ip>/.
