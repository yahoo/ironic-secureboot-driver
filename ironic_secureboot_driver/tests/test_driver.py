# Copyright 2018, Oath Inc
# Licensed under the terms of the Apache 2.0 license. See LICENSE file in
# https://github.com/yahoo/ironic-secureboot-driver

from ironic.common import exception as ironic_exc
from ironic.conductor import task_manager
from ironic.drivers.modules import pxe
from ironic.tests.unit.db import base as ironic_base
from ironic.tests.unit.objects import utils as ironic_obj_utils

from ironic_secureboot_driver import driver
from ironic_secureboot_driver.tests import base


def setup_configs(self):
    self.config(enabled_hardware_types='secureboot_ipmi')
    self.config(enabled_boot_interfaces='secureboot')
    self.config(enabled_deploy_interfaces='ramdisk')
    self.config(enabled_management_interfaces='ipmitool')
    self.config(enabled_power_interfaces='ipmitool')


class TestHardwareType(base.TestCase):

    def setUp(self):
        super(TestHardwareType, self).setUp()
        self.ht = driver.SecurebootIPMIHardware()

    def test_supported_boot_interfaces(self):
        expected = [driver.Secureboot]
        self.assertEqual(expected, self.ht.supported_boot_interfaces)

    def test_supported_deploy_interfaces(self):
        expected = [pxe.PXERamdiskDeploy]
        self.assertEqual(expected, self.ht.supported_deploy_interfaces)


class TestBootInterface(ironic_base.DbTestCase):
    def setUp(self):
        super(TestBootInterface, self).setUp()
        setup_configs(self)
        node = {
            'driver': 'secureboot_ipmi',
            'deploy_interface': 'ramdisk',
            'boot_interface': 'secureboot',
        }
        self.node = ironic_obj_utils.create_test_node(self.context, **node)

    def test_validate_success(self):
        with task_manager.acquire(self.context, self.node.uuid) as task:
            task.node.driver_info = {
                'secureboot_key': 'PEM-wrapped key data',
                'secureboot_key_dat': 'encrypted key data',
                'secureboot_certificate': 'cert data'
            }
            task.driver.boot.validate(task)

    def test_validate_no_key(self):
        with task_manager.acquire(self.context, self.node.uuid) as task:
            task.node.driver_info = {
                'secureboot_key_dat': 'encrypted key data',
                'secureboot_certificate': 'cert data'
            }
            self.assertRaises(ironic_exc.MissingParameterValue,
                              task.driver.boot.validate, task)

    def test_validate_no_key_dat(self):
        with task_manager.acquire(self.context, self.node.uuid) as task:
            task.node.driver_info = {
                'secureboot_key': 'PEM-wrapped key data',
                'secureboot_certificate': 'cert data'
            }
            self.assertRaises(ironic_exc.MissingParameterValue,
                              task.driver.boot.validate, task)

    def test_validate_no_cert(self):
        with task_manager.acquire(self.context, self.node.uuid) as task:
            task.node.driver_info = {
                'secureboot_key': 'PEM-wrapped key data',
                'secureboot_key_dat': 'encrypted key data',
            }
            self.assertRaises(ironic_exc.MissingParameterValue,
                              task.driver.boot.validate, task)
