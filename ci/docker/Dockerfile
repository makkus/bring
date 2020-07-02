FROM debian:stable

RUN \
   apt update -y && \
   apt install -y wget git

COPY bring /usr/bin/bring

RUN \
   chmod +x /usr/bin/bring
