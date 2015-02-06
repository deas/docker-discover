FROM ubuntu:14.10
# docker build --rm -t deas/cr-docker-discover .
RUN sed -i 's/^# \(.*-backports\s\)/\1/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y python-pip python-dev python-jinja2 libssl-dev libffi-dev && \
    apt-get install -y -t utopic-backports haproxy && \
    sed -i 's/^ENABLED=.*/ENABLED=1/' /etc/default/haproxy && \
    rm -rf /var/lib/apt/lists/*

RUN pip install python-etcd
# Jinja2
RUN touch /var/run/haproxy.pid

ADD . /app

WORKDIR /app

# EXPOSE 1936

CMD ["python", "main.py"]

