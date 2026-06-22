FROM python:3.10-slim
WORKDIR /code
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY upper.py .
EXPOSE 5000
ENV FLASK_APP=upper
CMD ["flask", "run", "--host=0.0.0.0"]
