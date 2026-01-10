ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python, ffmpeg, ImageMagick, and dependencies
RUN apk add --no-cache python3 py3-pip ffmpeg imagemagick
RUN pip3 install --no-cache-dir --break-system-packages openai requests jinja2

# Copy add-on files
COPY run.sh /
COPY generator.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
