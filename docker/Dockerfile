FROM debian:stable

RUN \
   apt update -y && \
   apt install -y wget git
#   wget --output-document /usr/bin/bring https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/bring

COPY bring /usr/bin/bring

RUN \
   chmod +x /usr/bin/bring
