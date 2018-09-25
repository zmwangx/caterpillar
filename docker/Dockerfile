# Usage:
#     docker build -t zmwangx/caterpillar:pypi https://github.com/zmwangx/caterpillar.git#master:docker
#     docker run -it --rm -v HOST_DIR:CONTAINER_DIR zmwangx/caterpillar:pypi ARG...

FROM jrottenberg/ffmpeg:4.0-ubuntu

RUN apt-get -yqq update && \
    apt-get install -yq --no-install-recommends software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get -yqq update && \
    apt-get install -yq --no-install-recommends python3.7 python3.7-venv && \
    python3.7 -m venv /venv

ENV PATH /venv/bin:${PATH}

RUN pip3.7 install caterpillar-hls && \
    caterpillar --version

ENTRYPOINT ["caterpillar"]
CMD        ["--help"]
