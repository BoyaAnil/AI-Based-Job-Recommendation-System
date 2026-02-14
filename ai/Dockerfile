FROM python:3.12-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore
WORKDIR /app
COPY requirements.txt /app/
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV FLASK_APP=app
EXPOSE 5000
CMD ["sh", "-c", "flask --app app run --host=0.0.0.0 --port=${PORT:-5000}"]
