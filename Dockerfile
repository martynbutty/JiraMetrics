FROM python:3.6-alpine
# can't use 3.7 yet - fails to install pytaml dependancy - seems like a known bug

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY getJiraMetrics.py .
COPY getJiraMetricsConfig.yaml .

