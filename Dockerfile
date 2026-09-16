FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get -qq update --fix-missing && apt-get -qq upgrade -y && apt-get install git -y

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash","start.sh"]
