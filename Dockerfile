FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

# Install opsdroid with Slack support + explicit Slack libs and extras
RUN pip install --no-cache-dir "opsdroid[slack]>=0.30,<0.32" slack-sdk slack-bolt certifi emoji

WORKDIR /home/opsdroid/.config/opsdroid
COPY . /home/opsdroid/.config/opsdroid
CMD ["opsdroid", "start", "-f", "/home/opsdroid/.config/opsdroid/configuration.yaml"]