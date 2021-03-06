# Copyright 2018, Oath Inc
# Licensed under the terms of the Apache 2.0 license. See LICENSE file in
# https://github.com/yahoo/ironic-secureboot-driver

import base64
import json
import os

from oslo_utils import fileutils
import requests

from ironic.common import boot_devices
from ironic.common import exception as ironic_exc
from ironic.common import states
from ironic.common import utils
from ironic.conductor import utils as manager_utils
from ironic.conf import CONF
from ironic.drivers import base
from ironic.drivers import ipmi
from ironic.drivers.modules import pxe
from ironic.drivers.modules import iscsi_deploy


class SecurebootIPMIHardware(ipmi.IPMIHardware):
    @property
    def supported_boot_interfaces(self):
        return [Secureboot, pxe.PXEBoot]

    @property
    def supported_deploy_interfaces(self):
        return [pxe.PXERamdiskDeploy, iscsi_deploy.ISCSIDeploy]

    @property
    def supported_power_interfaces(self):
        interfaces = super(SecurebootIPMIHardware,
                           self).supported_power_interfaces
        return interfaces + [HttpmiPower]

    @property
    def supported_management_interfaces(self):
        interfaces = super(SecurebootIPMIHardware,
                           self).supported_management_interfaces
        return interfaces + [HttpmiManagement]


SECUREBOOT_PROPERTIES = {
    'secureboot_key': ('PEM-wrapped encrypted private key for mutual TLS '
                       'authentication to image server. Required.'),
    'secureboot_key_dat': ('Encrypted private key for mutual TLS '
                           'authentication to image server, '
                           'base64-encoded. Required.'),
    'secureboot_certificate': ('Client certificate for mutual TLS '
                               'authentication to image server. Required.'),
}


# TODO(jroll) make this a config?
IMAGES_PATH = '/images'


def _secure_http_root(node_uuid):
    return os.path.join(
        CONF.deploy.http_root,
        'secure',
        node_uuid)


def _insecure_http_root(node_uuid):
    return os.path.join(
        CONF.deploy.http_root,
        'insecure',
        node_uuid)


def _link_images(node):
    http_root = _secure_http_root(node.uuid)
    fileutils.ensure_tree(http_root)
    for key in ('kernel', 'ramdisk', 'squash'):
        source = os.path.join(IMAGES_PATH,
                              node.instance_info[key])
        image_dest = os.path.join(http_root, key)
        os.symlink(source, image_dest)


def _write_key_and_cert(node):
    http_root = _insecure_http_root(node.uuid)
    fileutils.ensure_tree(http_root)

    def _write(data, filename):
        dest = os.path.join(http_root, filename)
        with open(dest, 'wb') as f:
            f.write(data)

    _write(node.driver_info['secureboot_key'], 'key')
    _write(node.driver_info['secureboot_certificate'], 'certificate')
    key_data = base64.b64decode(node.driver_info['secureboot_key_dat'])
    _write(key_data, 'key.dat')


class Secureboot(base.BootInterface):

    capabilities = ['ramdisk_boot']

    def get_properties(self):
        return SECUREBOOT_PROPERTIES

    def validate(self, task):
        # TODO(jroll) validate we can put images in /httpboot?
        # validate image, kernel, ramdisk as UUID
        node = task.node

        missing_keys = []
        for key in SECUREBOOT_PROPERTIES:
            if not node.driver_info.get(key):
                missing_keys.append(key)

        if missing_keys:
            raise ironic_exc.MissingParameterValue(
                'Node %s is missing secureboot configuration data %s' %
                (node.uuid, missing_keys))

    def prepare_ramdisk(self, task, ramdisk_params):
        # no ramdisk involved here
        pass

    def clean_up_ramdisk(self, task):
        # no ramdisk involved here
        pass

    def prepare_instance(self, task):
        # set boot dev to disk
        node = task.node

        # TODO(jroll) clean up if any of this fails?
        # or does ironic handle this?
        # TODO(jroll) do we want some way to be able to do this,
        # without needing the images in the right place on disk?
        # e.g. downloading from glance, etc
        _link_images(node)
        _write_key_and_cert(node)
        manager_utils.node_set_boot_device(task, boot_devices.DISK,
                                           persistent=True)

    def clean_up_instance(self, task):
        node = task.node

        # TODO(jroll) okay to not raise an exception here?
        utils.rmtree_without_raise(_insecure_http_root(node.uuid))
        utils.rmtree_without_raise(_secure_http_root(node.uuid))


def _get_httpmi_credentials(node):
    driver_info = node.driver_info

    credentials = {
        'user': driver_info['ipmi_username'],
        'password': driver_info['ipmi_password'],
        'bmc': driver_info['ipmi_address'],
    }

    port = driver_info.get('ipmi_port')
    if port:
        credentials['port'] = port

    return credentials


def _call_httpmi(node, method, path, **kwargs):
    url = node.driver_info['httpmi_url']
    url += path
    payload = _get_httpmi_credentials(node)
    payload.update(kwargs)
    res = getattr(requests, method)(url, data=payload)
    if res.status_code != 200:
        # TODO log some stuff here
        # TODO add some retries
        raise ironic_exc.IPMIFailure(cmd='httpmi call to to %(url)s '
                                         'with args %(kwargs)s' % {
                                             'url': url, 'kwargs': kwargs})
    return res.json()


class HttpmiPower(base.PowerInterface):
    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def get_power_state(self, task):
        data = _call_httpmi(task.node, 'get', '/power')
        return data['state']

    def set_power_state(self, task, power_state, timeout=None):
        _call_httpmi(task.node, 'post', '/power', state=power_state)

    def reboot(self, task, timeout=None):
        _call_httpmi(task.node, 'post', '/power', state=states.POWER_OFF)
        _call_httpmi(task.node, 'post', '/power', state=states.POWER_ON)


class HttpmiManagement(base.ManagementInterface):
    def get_properties(self):
        return {}

    def validate(self, task):
        pass

    def get_supported_boot_devices(self, task):
        return [boot_devices.PXE, boot_devices.DISK]

    def set_boot_device(self, task, device, persistent=False):
        if device == boot_devices.DISK:
            device = 'hd'
        _call_httpmi(task.node, 'post', '/boot-device', device=device)

    def get_boot_device(self, task):
        res = _call_httpmi(task.node, 'get', '/boot-device')
        return res['device']

    def get_sensors_data(self, task):
        return {}
