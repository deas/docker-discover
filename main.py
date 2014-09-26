#!/usr/bin/python

import etcd
# https://docs.python.org/2/library/argparse.html
# import argparse
import logging
from jinja2 import Environment, PackageLoader
import os
from subprocess import call
import sys
import time

env = Environment(loader=PackageLoader('haproxy', 'templates'))

def get_etcd_addr():

    if not etcd_host:
        logger.info("ETCD_HOST not set")
        sys.exit(1)

    port = 4001
    host = etcd_host

    if ":" in etcd_host:
        host, port = etcd_host.split(":")

    return host, port

def get_services(service_map):

    host, port = get_etcd_addr()
    client = etcd.Client(host=host, port=int(port))
    backends = client.read('/services', recursive = True)
    # backends = client.read('/backends', recursive = True)
    services = {}

    for i in backends.children:

        if i.key[1:].count("/") != 2:
            continue

        ignore, service, container = i.key[1:].split("/")
        #  <hostname>:<container-name>:<internal-port>[:udp if udp]
        # "/services/crwp/bruce:desperate_pare:80"
        if service in service_map:
            endpoints = services.setdefault(service, dict(port="", backends=[]))
            endpoints["port"] = service_map[service]
            # if container == "port":
            #    endpoints["port"] = i.value
            #    continue
            endpoints["backends"].append(dict(name=container, addr=i.value))
    return services

def generate_config(services, cfg):
    template = env.get_template('haproxy.cfg.tmpl')
    with open(cfg, "w") as f:
        f.write(template.render(services=services))

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARN,# DEBUG - used by other modules ,
                        format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # os.environ['ETCD_HOST'] = 'localhost:4001'# Test
    # os.environ['RELOAD_CMD'] = '/bin/true'
    # os.environ['HAPROXY_CFG'] = './haproxy.cfg'
    # os.environ['SERVICE_NAMES'] = 'crwp:80'# image:port which port in container ? :80'
    etcd_host = os.environ["ETCD_HOST"] if "ETCD_HOST" in os.environ else False
    reload_cmd  = os.environ['RELOAD_CMD'] if 'RELOAD_CMD' in os.environ else "./reload-haproxy.sh"
    haproxy_cfg = os.environ['HAPROXY_CFG'] if 'HAPROXY_CFG' in os.environ else  "/etc/haproxy/haproxy.cfg"
    service_names = os.environ['SERVICE_NAMES'].split(",") if 'SERVICE_NAMES' in os.environ else []
    service_map = {}
    poll_timeout = int(os.environ['POLL_TIMEOUT']) if 'POLL_TIMEOUT' in os.environ else 5

    for s in service_names:
        srv,prt = s.split(":")
        service_map[srv] = prt

    if len(service_names) == 0:
        logger.error("Got no services")
        sys.exit(1)

    current_services = {}

    while True:
        try:
            services = get_services(service_map)

            if not services or services == current_services:
                time.sleep(poll_timeout)
                continue

            logger.info("Config changed. Reload haproxy.")
            generate_config(services, haproxy_cfg)
            ret = call([reload_cmd ])
            if ret != 0:
                logger.info("Reloading haproxy returned: "  + str(ret))
                time.sleep(poll_timeout)
                continue
            current_services = services

        except Exception, e:
            logger.error("Error:" + str(e))

        time.sleep(poll_timeout)