from re import findall
from requests import Session


async def recaptchaV3(
    ANCHOR_URL="https://www.google.com/recaptcha/api2/anchor?ar=1&k=6Lcr1ncUAAAAAH3cghg6cOTPGARa8adOf-y9zv2x&co=aHR0cHM6Ly9vdW8ucHJlc3M6NDQz&hl=en&v=pCoGBhjs9s8EhFOHJFe8cqis&size=invisible&cb=ahgyd1gkfkhe",
):
    rs = Session()
    rs.headers.update({"content-type": "application/x-www-form-urlencoded"})
    matches = findall(r"([api2|enterprise]+)/anchor\?(.*)", ANCHOR_URL)[0]
    url_base = "https://www.google.com/recaptcha/" + matches[0] + "/"
    params = matches[1]
    res = rs.get(url_base + "anchor", params=params)
    token = findall(r'"recaptcha-token" value="(.*?)"', res.text)[0]
    params = dict(pair.split("=") for pair in params.split("&"))
    res = rs.post(
        url_base + "reload",
        params=f'k={params["k"]}',
        data=f"v={params['v']}&reason=q&c={token}&k={params['k']}&co={params['co']}",
    )
    return findall(r'"rresp","(.*?)"', res.text)[0]
