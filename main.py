#!/usr/bin/python
# TODO: Get template passed in
# TODO: Get service (ip) to listen to passed in
# TODO: Get stats address to listen to passed in
#
import etcd
# https://docs.python.org/2/library/argparse.html
import argparse
import signal
import logging
from jinja2 import Environment, PackageLoader
import os
from subprocess import call
import sys
import time

env = Environment(loader=PackageLoader('haproxy', 'templates'))

# def parse_args():
#
#    # etcd_host = os.environ["ETCD_HOST"] if "ETCD_HOST" in os.environ else False
#    # reload_cmd  = os.environ['RELOAD_CMD'] if 'RELOAD_CMD' in os.environ else "./reload-haproxy.sh"
#    # haproxy_cfg = os.environ['HAPROXY_CFG'] if 'HAPROXY_CFG' in os.environ else  "/etc/haproxy/haproxy.cfg"
#    # service_names = os.environ['SERVICE_NAMES'].split(",") if 'SERVICE_NAMES' in os.environ else []
#    # service_map = {}
#    # poll_timeout = int(os.environ['POLL_TIMEOUT']) if 'POLL_TIMEOUT' in os.environ else 5
#
#    parser = argparse.ArgumentParser(description="HA Proxy + Docker Discover")
#    # parser.add_argument("--directory", required=True, help="Directory to backup")
#    parser.add_argument("--gzip", required=False, help="Use tar with gzip compression", action="store_true")
#    parser.add_argument("--basename", required=True, help="Backup base filename")
#    parser.add_argument("--basedir", required=True, help="Backup base directory")
#    parser.add_argument("--metadir", required=True, help="Backup metadata")
#    parser.add_argument("--exclude", action="append", help="tar excludes passthrough")
#    parser.add_argument("--levels", type=int)
#    parser.add_argument('paths', metavar='path', nargs='+', help='Paths to backup')
#
#    return parser.parse_args()

def logenv():
    for key in os.environ.keys():
        logger.info("%30s %s" % (key,os.environ[key]))

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

def generate_config(model, cfg):
    template = env.get_template('haproxy.cfg.tmpl')
    with open(cfg, "w") as f:
        f.write(template.render(model))

def key_hashes(srvs):
    srvhashes = []
    for k in srvs:
        srvhashes += [v["addr"] + v["name"] for v in srvs[k]["backends"]]
    return set(srvhashes)

if __name__ == "__main__":
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    logging.basicConfig(level=logging.WARN,# DEBUG - used by other modules ,
                        format='%(asctime)s %(levelname)s %(message)s')
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    # args = parse_args()
    # os.environ['ETCD_HOST'] = 'localhost:4001'# Test
    # os.environ['RELOAD_CMD'] = '/bin/true'
    # os.environ['HAPROXY_CFG'] = './haproxy.cfg'
    # os.environ['SERVICE_NAMES'] = 'cr-wordpress:80'# image:port which port in container ? :80'
    etcd_host = os.environ["ETCD_HOST"] if "ETCD_HOST" in os.environ else False
    # reload_cmd  = [ os.environ['RELOAD_CMD'] ] if 'RELOAD_CMD' in os.environ else ["./reload-haproxy.sh"]
    service_ip = os.environ['SERVICE_IP'] if 'SERVICE_IP' in os.environ else  "0.0.0.0"
    # explicitely in docker command line already -p 127.0.0.1:1936:1936
    # stats_port = os.environ['PORT'] if 'STATS_PORT' in os.environ else  "1936"
    stats_auth = os.environ['STATS_AUTH'] if 'STATS_AUTH' in os.environ else  "banane:pflaume"
    haproxy_cfg = os.environ['HAPROXY_CFG'] if 'HAPROXY_CFG' in os.environ else  "/etc/haproxy/haproxy.cfg"
    service_names = os.environ['SERVICE_NAMES'].split(",") if 'SERVICE_NAMES' in os.environ else []
    service_map = {}
    poll_timeout = int(os.environ['POLL_TIMEOUT']) if 'POLL_TIMEOUT' in os.environ else 5

    logenv()

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

            # if not services or services == current_services:
            #    time.sleep(poll_timeout)
            #    continue

            if not (key_hashes(services) - key_hashes(current_services)):
               time.sleep(poll_timeout)
               continue

            # for k in services:
            #    srvhashes += [v["addr"] + v["name"] for v in services[k]["backends"]]

            # for k in current_services:
            #    srvhashes += [v["addr"] + v["name"] for v in current_services[k]["backends"]]


            logger.info("Config changed. Reload haproxy.")
            generate_config({'services':services,
                             'service_ip':service_ip,
                             # 'stats_port':stats_port,
                             'stats_auth':stats_auth
                            },
                            haproxy_cfg)

            pid_fname = '/var/run/haproxy.pid'
            reload_cmd = ['/usr/sbin/haproxy', '-f', '/etc/haproxy/haproxy.cfg', '-p', pid_fname ]

            if os.path.isfile(pid_fname):
                with open (pid_fname, "r") as myfile:
                    pid = myfile.read().replace('\n', '')
                    if pid:
                        reload_cmd + ['-sf ', pid  ]
            # [ALERT] 310/150316 (12) : Starting proxy contentreich-web: cannot bind socket [0.0.0.0:80]
            # /usr/sbin/haproxy -f /etc/haproxy/haproxy.cfg -p /var/run/haproxy.pid -sf $(cat /var/run/haproxy.pid)
            # ret = call([reload_cmd ])
            logger.info(reload_cmd)
            ret = call(reload_cmd)

            if ret != 0:
                logger.info("Reloading haproxy returned: "  + str(ret))
                time.sleep(poll_timeout)
                continue

            current_services = services

        except Exception, e:
            logger.error("Error:" + str(e))
            logging.exception(e)

        time.sleep(poll_timeout)