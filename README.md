# ARCHIVED 


# ironic-secureboot-driver

> An Ironic plugin to provide a boot driver and hardware type for secureboot
  deployments.

## Background

Oath needs to securely boot hardware in locations all around the world. To do this we
use GRUB with iPXE that is verified via registers in the TPM; this has access
to a secure key that's accessible only when the system configuration and boot
components match the sealed values. iPXE will fetch an encrypted key and
certificate; if the proper registers are set, the key can be unencrypted with
the secure key. The key and certificate are then used for mutual TLS
authentication to a trusted server that provides a bootable image. This image can be
booted as a ramdisk, and iPXE will chainload to this image.

This driver provides a boot interface that works in tandem with the 'ramdisk'
deploy interface to skip the agent ramdisk process and boot directly to the
instance. It does this by booting to disk and laying down files for the image server to
provide to the baremetal nodes.

## Install

Install with pip into the virtualenv or system where ironic is installed:

    $ git clone git@github.com:yahoo/ironic-secureboot-driver
    $ pip install ironic-secureboot-driver

This driver also requires a web server on the same host as the conductor. The
host should serve from `$httpboot/insecure` without mutual TLS auth, and
from `$httpboot/secure` with mutual TLS auth, where `$httpboot` is configured
in ironic at `[deploy]/http_root`.

Images should be placed in `/images`, and are reference in the nodes'
`instance_info` field relative to that location.

## Usage

Enable the hardware type and interfaces in ironic.conf:

    enabled_boot_interfaces = pxe,secureboot
    enabled_hardware_types = ipmi,secureboot_ipmi
    enabled_deploy_interfaces = direct,ramdisk

Restart ironic to pick up the config changes.

Register a node using the right interfaces and hardware type:

    $ openstack baremetal node create \
        --driver secureboot_ipmi \
        --boot-interface secureboot \
        --deploy-interface ramdisk

Set the certificate and key data on the node:

    $ openstack baremetal node set \
        --driver-info secureboot_key=$(cat $uuid.key) \
        --driver-info secureboot_key_dat=$(base64 -w 0 $uuid.key.dat) \
        --driver-info secureboot_certificate=$(cat $uuid.cert) \
        $uuid

Note that generating the keys and certificates is up to the user, as the
encryption and boot process may be different between deployments. In general:

* $uuid.key is a PEM-wrapped encrypted private key for the node
* $uuid.key.dat is an encrypted blob of the private key for the node
* $uuid.cert is the client certificate for the node

Set the image info for the deployment:

    $ openstack baremetal node set \
        --instance-info kernel=vmlinuz-ramdisk-ssh \
        --instance-info ramdisk=initrd-ramdisk-ssh.img \
        --instance-info squash=squashfs-ramdisk-ssh.img \
        $uuid

And finally, deploy the node:

    $ openstack baremetal node deploy $uuid

## Contribute

* Free software: Apache license
* Source: https://github.com/yahoo/ironic-secureboot-driver
* Bugs: https://github.com/yahoo/ironic-secureboot-driver/issues

Please refer to [the contributing.md file](Contributing.md) for information
about how to get involved. We welcome issues, questions, and pull requests.
Please be sure to follow our [code of conduct](Code-of-Conduct.md).

## License

Copyright 2018 Oath Inc.

This project is licensed under the terms of the Apache 2.0 open source license.
Please refer to [LICENSE](LICENSE) for the full terms.
