FROM debian:stable

RUN \
   apt update -y && \
   apt install -y wget git
#   wget --output-document /usr/bin/bring https://s3-eu-west-1.amazonaws.com/dev.dl.frkl.io/linux-gnu/bring

COPY bring-update-context.sh /usr/bin/bring-update-context.sh
COPY bring-update-repo.sh /usr/bin/bring-update-repo.sh
COPY bring /usr/bin/bring

RUN \
   chmod +x /usr/bin/bring && \
   chmod +x /usr/bin/bring-update-context.sh && \
   chmod +x /usr/bin/bring-update-repo.sh
