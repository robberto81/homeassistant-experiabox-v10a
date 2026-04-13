"""Support for ExperiaBox V10A (firmware V10A.C.26+, Sagemcom JSON-RPC API)."""
import json
import logging
from collections import namedtuple

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
})

_SAH_CONTENT_TYPE = 'application/x-sah-ws-4-call+json'


def get_scanner(hass, config):
    """Return an ExperiaBoxV10ADeviceScanner, or None on failure."""
    try:
        return ExperiaBoxV10ADeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


def _best_name(device):
    """Return the best display name (webui > dhcp > mdns > default)."""
    for source in ('webui', 'dhcp', 'mdns'):
        for entry in device.get('Names', []):
            if entry.get('Source') == source and entry.get('Name'):
                return entry['Name']
    return device.get('Name', '')


def _best_ipv4(device):
    """Return the first global IPv4 address for a device."""
    for addr in device.get('IPv4Address', []):
        ip = addr.get('Address', '')
        if ip and ':' not in ip:
            return ip
    ip = device.get('IPAddress', '')
    if ip and ':' not in ip:
        return ip
    return ''


def _collect_active_devices(nodes):
    """Recursively collect active client devices from the topology tree."""
    devices = []
    for node in nodes:
        if node.get('DiscoverySource') == 'selflan':
            # Router interface node — descend into children
            devices.extend(
                _collect_active_devices(node.get('Children', []))
            )
        else:
            if node.get('Active', False):
                devices.append(node)
            devices.extend(
                _collect_active_devices(node.get('Children', []))
            )
    return devices


class ExperiaBoxV10ADeviceScanner(DeviceScanner):
    """Query an Experia Box V10A via its Sagemcom JSON-RPC API."""

    def __init__(self, config):
        """Initialise the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.base_url = 'http://{}'.format(self.host)
        self.last_results = []
        self.success_init = self._update_info()

    def scan_devices(self):
        """Scan for new devices and return a list of found device IDs."""
        self._update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device, or None if unknown."""
        matches = [r.name for r in self.last_results if r.mac == device]
        return matches[0] if matches else None

    def get_extra_attributes(self, device):
        """Return extra attributes for the given device."""
        match = next(
            (r for r in self.last_results if r.mac == device), None
        )
        return {'ip': match.ip} if match else {}

    def _ws_post(self, session, service, method, parameters, auth_header):
        """POST a Sagemcom JSON-RPC call and return the response dict."""
        url = '{}/ws/{}:{}'.format(self.base_url, service, method)
        payload = json.dumps({
            'service': service,
            'method': method,
            'parameters': parameters,
        })
        try:
            resp = session.post(
                url,
                data=payload,
                headers={
                    'authorization': auth_header,
                    'content-type': _SAH_CONTENT_TYPE,
                    'origin': self.base_url,
                    'referer': '{}/'.format(self.base_url),
                },
                timeout=10,
            )
        except requests.exceptions.Timeout:
            _LOGGER.error('Request timed out: %s:%s', service, method)
            return None
        except requests.exceptions.RequestException as exc:
            _LOGGER.error(
                'Request failed (%s:%s): %s', service, method, exc
            )
            return None

        try:
            return resp.json()
        except ValueError:
            _LOGGER.error(
                'Non-JSON response for %s:%s (HTTP %s): %s',
                service,
                method,
                resp.status_code,
                resp.text[:500],
            )
            return None

    def _update_info(self):
        """Fetch active devices from the router. Return True on success."""
        _LOGGER.info('Loading devices...')

        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        # Step 1: Authenticate and obtain a context token
        login_data = self._ws_post(
            session,
            service='sah.Device.Information',
            method='createContext',
            parameters={
                'applicationName': 'webui',
                'username': self.username,
                'password': self.password,
            },
            auth_header='X-Sah-Login',
        )

        if login_data is None:
            return False

        if login_data.get('status') != 0:
            _LOGGER.error('Login failed. Response: %s', login_data)
            return False

        context_id = login_data.get('data', {}).get('contextID')
        if not context_id:
            _LOGGER.error(
                'Login succeeded but no contextID in response: %s',
                login_data,
            )
            return False

        _LOGGER.debug('Authenticated successfully, contextID obtained.')

        # Step 2: Fetch the LAN device topology
        topo_data = self._ws_post(
            session,
            service='Devices.Device.lan',
            method='topology',
            parameters={
                'expression': 'not logical',
                'flags': 'no_recurse|no_actions',
            },
            auth_header='X-Sah {}'.format(context_id),
        )

        if topo_data is None:
            return False

        root_nodes = topo_data.get('status')
        if not isinstance(root_nodes, list):
            _LOGGER.error(
                'Unexpected topology response: %s', str(topo_data)[:500]
            )
            return False

        now = dt_util.now()
        active_devices = _collect_active_devices(root_nodes)

        last_results = []
        for device in active_devices:
            mac = device.get('PhysAddress', '').upper()
            if not mac:
                continue
            name = _best_name(device)
            ip = _best_ipv4(device)
            last_results.append(Device(mac, name, ip, now))
            _LOGGER.debug('Found device: %s (%s) @ %s', name, mac, ip)

        _LOGGER.info('Got %d active devices', len(last_results))
        self.last_results = last_results
        return True
