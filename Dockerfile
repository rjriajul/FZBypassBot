FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get -qq update --fix-missing && apt-get -qq upgrade -y && apt-get install git -y

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt uvloop

COPY . .

# Optional: uncomment to enable playwright for JS-rendered bypasses (vplink, vcloud, etc.)
# WARNING: adds ~280MB to image and exceeds free-tier RAM on Render/Koyeb
# RUN pip3 install playwright && playwright install chromium && playwright install-deps chromium

CMD ["python3", "-m", "FZBypass"]
