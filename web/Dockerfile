FROM python:3.12-slim
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore
WORKDIR /app
COPY requirements.txt /app/
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo && python manage.py runserver 0.0.0.0:${PORT:-8000}"]
