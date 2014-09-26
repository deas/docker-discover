FROM ubuntu:14.04
# docker build --rm -t deas/cr-docker-discover .
RUN sed -i 's/^# \(.*-backports\s\)/\1/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y python-pip python-dev python-jinja2 libssl-dev libffi-dev && \
    apt-get install -y -t trusty-backports haproxy && \
    sed -i 's/^ENABLED=.*/ENABLED=1/' /etc/default/haproxy && \
    rm -rf /var/lib/apt/lists/*

# RUN apt-get update
# RUN apt-get install -y python-pip python-dev libssl-dev
# WORKDIR /root
# RUN wget http://www.haproxy.org/download/1.5/src/haproxy-1.5.1.tar.gz
# RUN tar -zxvf haproxy-1.5.1.tar.gz
# RUN cd haproxy-1.5.1 && make TARGET=generic && make install

RUN pip install python-etcd
# Jinja2
RUN touch /var/run/haproxy.pid

ADD . /app

WORKDIR /app

# EXPOSE 1936

CMD ["python", "main.py"]

