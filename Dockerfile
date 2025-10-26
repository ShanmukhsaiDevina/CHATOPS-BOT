FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

# Slack deps included for later; harmless now
RUN pip install --no-cache-dir \
  "opsdroid[slack]>=0.30,<0.32" \
  slack-sdk slack-bolt \
  aiohttp==3.9.5 \
  certifi emoji

WORKDIR /home/opsdroid/.config/opsdroid
COPY . /home/opsdroid/.config/opsdroid

CMD ["opsdroid", "start", "-f", "/home/opsdroid/.config/opsdroid/configuration.yaml"]