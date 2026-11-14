FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN python -m pip install --no-cache-dir .
ENTRYPOINT ["python", "-m", "satqkd_sentinel"]
CMD ["demo", "--output", "/output"]
